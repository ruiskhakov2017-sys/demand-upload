from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.control_center.rules import rule_kill_switch_active
from app.control_center.service import (
    campaign_payload,
    matches_rule_condition,
    tag_map_for_accounts,
)
from app.core.security import generate_token, hash_token, utcnow
from app.db.models import (
    ControlCenterActionItem,
    ControlCenterActionRequest,
    ControlCenterCampaign,
    ControlCenterEvent,
    ControlCenterRule,
    ControlCenterRuleEvaluation,
    ControlCenterSavedView,
    CustomerAccount,
    GoogleConnection,
    Notification,
)

MUTATING_RULE_ACTIONS = {
    "PAUSE": "PAUSE",
    "PROPOSE_PAUSE": "PAUSE",
    "ENABLE": "ENABLE",
    "PROPOSE_ENABLE": "ENABLE",
    "SET_BUDGET": "SET_BUDGET",
    "PROPOSE_BUDGET": "SET_BUDGET",
}


@dataclass
class RuleEngineResult:
    rules: int = 0
    evaluated: int = 0
    matched: int = 0
    proposed_actions: int = 0
    notifications: int = 0
    queued_actions: int = 0
    skipped: int = 0
    action_request_ids: list[UUID] = field(default_factory=list)
    skip_reasons: dict[str, int] = field(default_factory=dict)

    def add_skip(self, reason: str) -> None:
        self.skipped += 1
        self.skip_reasons[reason] = self.skip_reasons.get(reason, 0) + 1

    def payload(self) -> dict[str, Any]:
        return {
            "rules": self.rules,
            "evaluated": self.evaluated,
            "matched": self.matched,
            "proposed_actions": self.proposed_actions,
            "notifications": self.notifications,
            "queued_actions": self.queued_actions,
            "mutation_performed": False,
            "skip_reasons": self.skip_reasons,
        }


@dataclass(frozen=True)
class PlannedRuleAction:
    action_type: str
    requested_value: int | str | None
    dimension: str
    original: dict[str, Any]


def evaluate_rules(
    db: Session,
    rules: list[ControlCenterRule],
    *,
    force: bool = False,
    now: datetime | None = None,
) -> RuleEngineResult:
    evaluated_at = now or utcnow()
    ordered_rules = sorted(rules, key=lambda item: (item.priority, item.name.casefold()))
    result = RuleEngineResult(rules=len(ordered_rules))
    if not ordered_rules:
        return result
    if rule_kill_switch_active(db):
        for rule in ordered_rules:
            _record_rule_skip(
                db,
                rule,
                "GLOBAL_KILL_SWITCH_ACTIVE",
                "BEFORE_EVALUATION",
                evaluated_at,
            )
            rule.last_evaluated_at = evaluated_at
            result.add_skip("GLOBAL_KILL_SWITCH_ACTIVE")
        return result

    campaigns = list(
        db.scalars(
            select(ControlCenterCampaign)
            .order_by(ControlCenterCampaign.account_id, ControlCenterCampaign.id)
            .limit(10_000)
        ).all()
    )
    account_ids = {campaign.account_id for campaign in campaigns}
    accounts = {
        account.id: account
        for account in db.scalars(
            select(CustomerAccount).where(CustomerAccount.id.in_(account_ids))
        ).all()
    }
    tags = tag_map_for_accounts(db, list(accounts))
    claimed_dimensions: dict[tuple[UUID, str], tuple[int, str, UUID]] = {}

    for rule in ordered_rules:
        if not force and (not rule.enabled or not _rule_schedule_due(rule, evaluated_at)):
            continue
        if rule.circuit_open_until and rule.circuit_open_until > evaluated_at:
            _record_rule_skip(
                db,
                rule,
                "CIRCUIT_BREAKER_OPEN",
                "BEFORE_EVALUATION",
                evaluated_at,
            )
            rule.last_evaluated_at = evaluated_at
            result.add_skip("CIRCUIT_BREAKER_OPEN")
            continue
        saved_view = _saved_view_for_rule(db, rule)
        actions_this_run = 0
        actions_today = _rule_actions_today(db, rule.id, evaluated_at)
        for campaign in campaigns:
            account = accounts.get(campaign.account_id)
            if not account or not _scope_matches(
                rule.scope,
                account,
                tags.get(account.id, []),
                saved_view,
            ):
                continue
            result.evaluated += 1
            candidate = {
                "account": {
                    "id": str(account.id),
                    "work_status": account.work_status,
                    "google_status": account.status,
                    "activity_status": account.activity_status,
                    "sync_error": account.sync_error,
                    "geo_id": str(account.geo_override_id or account.geo_id or ""),
                    "mcc_id": str(account.primary_mcc_id or ""),
                },
                "campaign": campaign_payload(campaign, account),
            }
            condition_results = [_matches_condition_node(candidate, condition) for condition in (rule.conditions or [])]
            condition_match = (
                all(condition_results)
                if rule.condition_logic == "AND"
                else any(condition_results)
            ) if condition_results else False
            if not condition_match:
                _record_evaluation(
                    db,
                    rule,
                    account,
                    campaign,
                    matched=False,
                    status="DRY_RUN" if rule.mode == "DRY_RUN" else "NO_MATCH",
                    details={"condition_results": condition_results},
                    proposed_actions=[],
                )
                continue

            result.matched += 1
            skip_reason = _safeguard_skip_reason(
                db,
                rule,
                account,
                campaign,
                evaluated_at,
                actions_this_run,
                actions_today,
            )
            if skip_reason:
                _record_evaluation(
                    db,
                    rule,
                    account,
                    campaign,
                    matched=True,
                    status="SKIPPED",
                    details={"condition_results": condition_results},
                    proposed_actions=rule.actions,
                    skip_reason=skip_reason,
                )
                result.add_skip(skip_reason)
                continue

            planned_actions, planning_error = _plan_actions(rule, campaign)
            if planning_error:
                _record_evaluation(
                    db,
                    rule,
                    account,
                    campaign,
                    matched=True,
                    status="SKIPPED",
                    details={"condition_results": condition_results},
                    proposed_actions=rule.actions,
                    skip_reason=planning_error,
                )
                result.add_skip(planning_error)
                continue
            if not planned_actions:
                _record_evaluation(
                    db,
                    rule,
                    account,
                    campaign,
                    matched=True,
                    status="SKIPPED",
                    details={"condition_results": condition_results},
                    proposed_actions=[],
                    skip_reason="NO_ACTIONS_CONFIGURED",
                )
                result.add_skip("NO_ACTIONS_CONFIGURED")
                continue

            actionable: list[PlannedRuleAction] = []
            conflict_reason: str | None = None
            for planned in planned_actions:
                claim_key = (campaign.id, planned.dimension)
                claimed = claimed_dimensions.get(claim_key)
                requested = str(planned.requested_value)
                if claimed and (claimed[1] != requested or claimed[2] != rule.id):
                    conflict_reason = "LOWER_PRIORITY_CONFLICT"
                    break
                claimed_dimensions[claim_key] = (rule.priority, requested, rule.id)
                actionable.append(planned)
            if conflict_reason:
                _record_evaluation(
                    db,
                    rule,
                    account,
                    campaign,
                    matched=True,
                    status="SKIPPED",
                    details={"condition_results": condition_results},
                    proposed_actions=rule.actions,
                    skip_reason=conflict_reason,
                )
                result.add_skip(conflict_reason)
                continue

            idempotency_key = _evaluation_key(rule, campaign, actionable)
            if db.scalar(
                select(ControlCenterRuleEvaluation.id).where(
                    ControlCenterRuleEvaluation.idempotency_key == idempotency_key
                )
            ):
                result.add_skip("IDEMPOTENT_REPLAY")
                continue

            result.proposed_actions += len(actionable)
            if rule.mode == "DRY_RUN":
                _record_evaluation(
                    db,
                    rule,
                    account,
                    campaign,
                    matched=True,
                    status="DRY_RUN",
                    details={
                        "condition_results": condition_results,
                        "safeguards_passed": True,
                    },
                    proposed_actions=[item.original for item in actionable],
                    idempotency_key=idempotency_key,
                )
                continue
            if rule.mode != "LIVE" or not rule.live_confirmed_at:
                _record_evaluation(
                    db,
                    rule,
                    account,
                    campaign,
                    matched=True,
                    status="SKIPPED",
                    details={"condition_results": condition_results},
                    proposed_actions=[item.original for item in actionable],
                    skip_reason="LIVE_NOT_CONFIRMED",
                    idempotency_key=idempotency_key,
                )
                result.add_skip("LIVE_NOT_CONFIRMED")
                continue
            if rule_kill_switch_active(db):
                _record_evaluation(
                    db,
                    rule,
                    account,
                    campaign,
                    matched=True,
                    status="SKIPPED_KILL_SWITCH",
                    details={
                        "condition_results": condition_results,
                        "phase": "BEFORE_ACTION_CREATION",
                    },
                    proposed_actions=[item.original for item in actionable],
                    skip_reason="GLOBAL_KILL_SWITCH_ACTIVE",
                    idempotency_key=idempotency_key,
                )
                result.add_skip("GLOBAL_KILL_SWITCH_ACTIVE")
                continue

            evaluation = _record_evaluation(
                db,
                rule,
                account,
                campaign,
                matched=True,
                status="LIVE_MATCH",
                details={
                    "condition_results": condition_results,
                    "safeguards_passed": True,
                },
                proposed_actions=[item.original for item in actionable],
                idempotency_key=idempotency_key,
            )
            for planned in actionable:
                if planned.action_type == "NOTIFY":
                    _create_rule_notification(
                        db,
                        rule,
                        account,
                        campaign,
                        planned,
                        evaluated_at,
                    )
                    evaluation.status = "NOTIFIED"
                    result.notifications += 1
                    actions_this_run += 1
                    actions_today += 1
                    continue
                connection = db.get(GoogleConnection, account.connection_id)
                if not connection or connection.connection_mode != "GOOGLE_TEST":
                    evaluation.status = "SKIPPED_PRODUCTION_GUARD"
                    evaluation.skip_reason = "PRODUCTION_MUTATE_BLOCKED"
                    result.add_skip("PRODUCTION_MUTATE_BLOCKED")
                    continue
                action_request = _create_rule_action_request(
                    db,
                    rule,
                    evaluation,
                    account,
                    campaign,
                    planned,
                    evaluated_at,
                )
                result.action_request_ids.append(action_request.id)
                result.queued_actions += 1
                actions_this_run += 1
                actions_today += 1
            if actions_this_run:
                rule.last_action_at = evaluated_at
        rule.last_evaluated_at = evaluated_at
    return result


def _record_rule_skip(
    db: Session,
    rule: ControlCenterRule,
    reason: str,
    phase: str,
    now: datetime,
) -> None:
    db.add(
        ControlCenterRuleEvaluation(
            rule_id=rule.id,
            matched=False,
            status="SKIPPED_KILL_SWITCH" if "KILL_SWITCH" in reason else "SKIPPED",
            evaluation={"phase": phase, "reason": reason},
            proposed_actions=[],
            mutation_performed=False,
            skip_reason=reason,
        )
    )
    db.add(
        ControlCenterEvent(
            event_type="RULE_SKIPPED",
            source="RULE_ENGINE",
            summary=f"Правило «{rule.name}» пропущено: {reason}",
            details={"rule_id": str(rule.id), "phase": phase, "reason": reason},
            occurred_at=now,
        )
    )


def _record_evaluation(
    db: Session,
    rule: ControlCenterRule,
    account: CustomerAccount,
    campaign: ControlCenterCampaign,
    *,
    matched: bool,
    status: str,
    details: dict[str, Any],
    proposed_actions: list[dict[str, Any]],
    skip_reason: str | None = None,
    idempotency_key: str | None = None,
) -> ControlCenterRuleEvaluation:
    evaluation = ControlCenterRuleEvaluation(
        rule_id=rule.id,
        account_id=account.id,
        campaign_id=campaign.id,
        matched=matched,
        status=status,
        evaluation=details,
        proposed_actions=proposed_actions,
        mutation_performed=False,
        skip_reason=skip_reason,
        idempotency_key=idempotency_key,
    )
    db.add(evaluation)
    return evaluation


def _scope_matches(
    scope: dict[str, Any],
    account: CustomerAccount,
    tags: list[dict],
    saved_view: ControlCenterSavedView | None,
) -> bool:
    account_ids = {str(item) for item in scope.get("account_ids") or []}
    if account_ids and str(account.id) not in account_ids:
        return False
    customer_ids = {
        "".join(character for character in str(item) if character.isdigit())
        for item in scope.get("customer_ids") or []
    }
    if customer_ids and account.customer_id not in customer_ids:
        return False
    connection_ids = {str(item) for item in scope.get("connection_ids") or []}
    if connection_ids and str(account.connection_id) not in connection_ids:
        return False
    statuses = {str(item).upper() for item in scope.get("work_statuses") or []}
    if statuses and account.work_status not in statuses:
        return False
    geo_ids = {str(item) for item in scope.get("geo_ids") or []}
    effective_geo = str(account.geo_override_id or account.geo_id or "")
    if geo_ids and effective_geo not in geo_ids:
        return False
    mcc_ids = {str(item) for item in scope.get("mcc_ids") or []}
    if mcc_ids and str(account.primary_mcc_id or "") not in mcc_ids:
        return False
    required_tags = {str(item).casefold() for item in scope.get("tags") or []}
    required_tag_ids = {str(item) for item in scope.get("tag_ids") or []}
    current_names = {str(tag["name"]).casefold() for tag in tags}
    current_ids = {str(tag["id"]) for tag in tags}
    if required_tags and not required_tags.intersection(current_names):
        return False
    if required_tag_ids and not required_tag_ids.intersection(current_ids):
        return False
    return _saved_view_matches(saved_view, account)


def _saved_view_for_rule(
    db: Session,
    rule: ControlCenterRule,
) -> ControlCenterSavedView | None:
    value = (rule.scope or {}).get("saved_view_id")
    if not value:
        return None
    try:
        return db.get(ControlCenterSavedView, UUID(str(value)))
    except ValueError:
        return None


def _saved_view_matches(
    view: ControlCenterSavedView | None,
    account: CustomerAccount,
) -> bool:
    if view is None:
        return True
    config = view.config or {}
    quick_filter = str(config.get("quickFilter") or "")
    if quick_filter == "working" and account.work_status != "WORKING":
        return False
    if quick_filter == "paused" and account.work_status != "MANUAL_PAUSE":
        return False
    if quick_filter == "archive" and account.work_status != "ARCHIVED":
        return False
    checks = {
        "connectionId": str(account.connection_id),
        "geoId": str(account.geo_override_id or account.geo_id or ""),
        "mccId": str(account.primary_mcc_id or ""),
        "currency": str(account.currency_code or ""),
        "googleStatus": str(account.status or ""),
        "workStatus": account.work_status,
        "activityStatus": account.activity_status,
    }
    return all(
        not config.get(key) or str(config[key]) == value
        for key, value in checks.items()
    )


def _rule_schedule_due(rule: ControlCenterRule, now: datetime) -> bool:
    schedule = rule.schedule or {}
    interval = max(1, int(schedule.get("interval_minutes", 15)))
    if rule.last_evaluated_at and now - rule.last_evaluated_at < timedelta(minutes=interval):
        return False
    weekdays = {int(value) for value in schedule.get("weekdays") or []}
    if weekdays and now.weekday() not in weekdays:
        return False
    return True


def _rule_actions_today(db: Session, rule_id: UUID, now: datetime) -> int:
    start = datetime.combine(now.date(), datetime.min.time(), tzinfo=UTC)
    return int(
        db.scalar(
            select(func.count(ControlCenterRuleEvaluation.id)).where(
                ControlCenterRuleEvaluation.rule_id == rule_id,
                ControlCenterRuleEvaluation.created_at >= start,
                ControlCenterRuleEvaluation.status.in_(
                    ["ACTION_QUEUED", "NOTIFIED", "MUTATED"]
                ),
            )
        )
        or 0
    )


def _safeguard_skip_reason(
    db: Session,
    rule: ControlCenterRule,
    account: CustomerAccount,
    campaign: ControlCenterCampaign,
    now: datetime,
    actions_this_run: int,
    actions_today: int,
) -> str | None:
    safeguards = rule.safeguards or {}
    max_age = timedelta(hours=max(1, int(safeguards.get("max_data_age_hours", 24))))
    if not campaign.last_synced_at or now - campaign.last_synced_at > max_age:
        return "STALE_DATA"
    if account.sync_error or campaign.sync_error:
        return "SYNC_ERROR"
    minimum_runtime = timedelta(
        hours=max(0, int(safeguards.get("minimum_runtime_hours", 0)))
    )
    if minimum_runtime and now - campaign.created_at < minimum_runtime:
        return "MINIMUM_RUNTIME"
    conversion_fields = {
        str(condition.get("field") or "")
        for condition in _leaf_conditions(rule.conditions or [])
        if any(
            token in str(condition.get("field") or "").casefold()
            for token in ("conversion", "registration", "deposit", "cpa", "roas")
        )
    }
    conversion_lag = timedelta(
        hours=max(0, int(safeguards.get("conversion_lag_hours", 0)))
    )
    last_material_change = campaign.last_change_at or campaign.created_at
    if conversion_fields and conversion_lag and now - last_material_change < conversion_lag:
        return "CONVERSION_DELAY"
    if actions_this_run >= rule.max_actions_per_run:
        return "RUN_ACTION_LIMIT"
    if actions_today >= rule.max_actions_per_day:
        return "DAILY_ACTION_LIMIT"
    cooldown_start = now - timedelta(minutes=rule.cooldown_minutes)
    recent = db.scalar(
        select(ControlCenterRuleEvaluation.id).where(
            ControlCenterRuleEvaluation.rule_id == rule.id,
            ControlCenterRuleEvaluation.campaign_id == campaign.id,
            ControlCenterRuleEvaluation.created_at >= cooldown_start,
            ControlCenterRuleEvaluation.status.in_(
                ["ACTION_QUEUED", "NOTIFIED", "MUTATED"]
            ),
        )
    )
    if recent:
        return "COOLDOWN"
    return None


def _matches_condition_node(candidate: dict[str, Any], condition: dict[str, Any]) -> bool:
    children = condition.get("conditions")
    if isinstance(children, list):
        results = [_matches_condition_node(candidate, child) for child in children if isinstance(child, dict)]
        if not results:
            return False
        return all(results) if str(condition.get("logic") or "AND").upper() == "AND" else any(results)
    return matches_rule_condition(candidate, condition)


def _leaf_conditions(conditions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    leaves: list[dict[str, Any]] = []
    for condition in conditions:
        children = condition.get("conditions")
        if isinstance(children, list):
            leaves.extend(_leaf_conditions([child for child in children if isinstance(child, dict)]))
        else:
            leaves.append(condition)
    return leaves


def _plan_actions(
    rule: ControlCenterRule,
    campaign: ControlCenterCampaign,
) -> tuple[list[PlannedRuleAction], str | None]:
    planned: list[PlannedRuleAction] = []
    for raw in rule.actions or []:
        action = dict(raw)
        raw_type = str(action.get("type") or "").upper()
        if raw_type == "NOTIFY":
            planned.append(
                PlannedRuleAction(
                    action_type="NOTIFY",
                    requested_value=action.get("message"),
                    dimension=f"notification:{rule.id}",
                    original=action,
                )
            )
            continue
        action_type = MUTATING_RULE_ACTIONS.get(raw_type)
        if not action_type:
            return [], "UNSUPPORTED_ACTION"
        if action_type == "ENABLE" and campaign.manually_paused and (
            rule.safeguards or {}
        ).get("block_manual_paused_enable", True):
            return [], "MANUAL_PAUSE_GUARD"
        if action_type == "SET_BUDGET":
            amount = _budget_amount(rule, campaign, action)
            if amount is None:
                return [], "INVALID_BUDGET_ACTION"
            planned.append(
                PlannedRuleAction(
                    action_type=action_type,
                    requested_value=amount,
                    dimension="budget",
                    original={**action, "amount_micros": amount},
                )
            )
            continue
        target = "PAUSED" if action_type == "PAUSE" else "ENABLED"
        planned.append(
            PlannedRuleAction(
                action_type=action_type,
                requested_value=target,
                dimension="status",
                original=action,
            )
        )
    return planned, None


def _budget_amount(
    rule: ControlCenterRule,
    campaign: ControlCenterCampaign,
    action: dict[str, Any],
) -> int | None:
    current = campaign.budget_micros
    if action.get("amount_micros") is not None:
        amount = int(action["amount_micros"])
    elif action.get("change_percent") is not None and current:
        percent = Decimal(str(action["change_percent"]))
        amount = int(Decimal(current) * (Decimal("1") + percent / Decimal("100")))
    else:
        return None
    if amount <= 0:
        return None
    limit = rule.max_budget_change_percent
    if limit is not None and current:
        change = abs(Decimal(amount - current) / Decimal(current) * Decimal("100"))
        if change > Decimal(limit):
            return None
    return amount


def _evaluation_key(
    rule: ControlCenterRule,
    campaign: ControlCenterCampaign,
    actions: list[PlannedRuleAction],
) -> str:
    value = {
        "rule_id": str(rule.id),
        "campaign_id": str(campaign.id),
        "last_synced_at": (
            campaign.last_synced_at.isoformat()
            if campaign.last_synced_at
            else None
        ),
        "actions": [
            {
                "type": action.action_type,
                "requested": action.requested_value,
            }
            for action in actions
        ],
    }
    digest = hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()
    ).hexdigest()
    return f"rule-eval:{digest}"


def _create_rule_notification(
    db: Session,
    rule: ControlCenterRule,
    account: CustomerAccount,
    campaign: ControlCenterCampaign,
    action: PlannedRuleAction,
    now: datetime,
) -> None:
    message = str(
        action.original.get("message")
        or f"Правило «{rule.name}» сработало для кампании «{campaign.name}»."
    )
    db.add(
        Notification(
            user_id=rule.created_by_id,
            severity=str(action.original.get("severity") or "WARNING").upper(),
            title=f"Автоправило: {rule.name}",
            message=message,
            entity_type="control_center_campaign",
            entity_id=str(campaign.id),
        )
    )
    db.add(
        ControlCenterEvent(
            account_id=account.id,
            campaign_id=campaign.id,
            actor_user_id=rule.live_confirmed_by_id or rule.created_by_id,
            event_type="RULE_NOTIFICATION",
            source="RULE_ENGINE",
            summary=message,
            details={"rule_id": str(rule.id), "action": action.original},
            occurred_at=now,
        )
    )


def _create_rule_action_request(
    db: Session,
    rule: ControlCenterRule,
    evaluation: ControlCenterRuleEvaluation,
    account: CustomerAccount,
    campaign: ControlCenterCampaign,
    planned: PlannedRuleAction,
    now: datetime,
) -> ControlCenterActionRequest:
    db.flush()
    previous_state = {
        "campaign_id": str(campaign.id),
        "google_campaign_id": campaign.campaign_id,
        "resource_name": campaign.resource_name,
        "status": campaign.status,
        "budget_resource_name": campaign.budget_resource_name,
        "budget_micros": campaign.budget_micros,
        "budget_shared": campaign.budget_shared,
        "source": "LOCAL_RULE_SNAPSHOT",
    }
    field_name = (
        "budget_micros"
        if planned.action_type == "SET_BUDGET"
        else "status"
    )
    payload: dict[str, Any] = {
        "campaign_ids": [str(campaign.id)],
        "action_type": planned.action_type,
        "execution_mode": "GOOGLE_TEST",
        "rule_id": str(rule.id),
    }
    if planned.action_type == "SET_BUDGET":
        payload["amount_micros"] = planned.requested_value
    action_digest = hashlib.sha256(
        f"{evaluation.id}:{planned.action_type}:{planned.requested_value}".encode()
    ).hexdigest()
    action_request = ControlCenterActionRequest(
        account_id=account.id,
        campaign_id=campaign.id,
        requested_by_id=rule.live_confirmed_by_id or rule.created_by_id,
        action_type=planned.action_type,
        execution_mode="GOOGLE_TEST",
        status="QUEUED",
        requested_payload=payload,
        pre_state={"campaigns": [previous_state]},
        preview={
            "changes": [
                {
                    "campaign_id": str(campaign.id),
                    "field": field_name,
                    "before": previous_state.get(field_name),
                    "after": planned.requested_value,
                }
            ],
            "warnings": (
                [
                    {
                        "code": "SHARED_BUDGET",
                        "message": "Изменение общего бюджета может затронуть другие кампании.",
                    }
                ]
                if planned.action_type == "SET_BUDGET" and campaign.budget_shared
                else []
            ),
        },
        validation={
            "ok": True,
            "validate_only": False,
            "validate_only_pending_worker": True,
            "execution_mode": "GOOGLE_TEST",
            "automated_rule": True,
            "rule_id": str(rule.id),
        },
        readback={},
        confirmation_token_hash=hash_token(generate_token("rule_confirm")),
        confirmation_expires_at=now + timedelta(minutes=15),
        confirmed_at=rule.live_confirmed_at or now,
        idempotency_key=f"rule-action:{action_digest}",
        request_ids=[],
    )
    db.add(action_request)
    db.flush()
    db.add(
        ControlCenterActionItem(
            action_request_id=action_request.id,
            account_id=account.id,
            campaign_id=campaign.id,
            status="VALIDATED",
            previous_state=previous_state,
            result={},
        )
    )
    evaluation.status = "ACTION_QUEUED"
    evaluation.action_request_id = action_request.id
    db.add(
        ControlCenterEvent(
            account_id=account.id,
            campaign_id=campaign.id,
            actor_user_id=rule.live_confirmed_by_id or rule.created_by_id,
            event_type="RULE_ACTION_QUEUED",
            source="RULE_ENGINE",
            summary=f"Правило «{rule.name}» поставило действие {planned.action_type} в очередь",
            details={
                "rule_id": str(rule.id),
                "action_request_id": str(action_request.id),
                "requested_value": planned.requested_value,
            },
            occurred_at=now,
        )
    )
    return action_request
