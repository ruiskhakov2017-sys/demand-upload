from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.google_ads.client_factory import google_ads_client, normalize_customer_id
from app.google_ads.errors import GoogleAdsAdapterError
from app.google_ads.interface import (
    AdapterCheckResult,
    CustomerAccountInfo,
    CustomerHierarchyResult,
    GoogleAdsConnectionConfig,
    PlanExecutionResult,
    YouTubeUploadResult,
)
from app.google_ads.request_metadata import unary_call_with_request_id

MCC_CUSTOMER_QUERY = """
    SELECT
      customer.id,
      customer.descriptive_name,
      customer.status,
      customer.manager,
      customer.test_account,
      customer.currency_code,
      customer.time_zone
    FROM customer
    LIMIT 1
"""


class GoogleAdsV242Adapter:
    def __init__(self, config: GoogleAdsConnectionConfig) -> None:
        self.config = config
        self._recent_request_ids: list[str] = []

    def test_connection(self) -> AdapterCheckResult:
        customer_id = normalize_customer_id(self.config.login_customer_id)
        self._recent_request_ids = []
        try:
            with google_ads_client(self.config) as client:
                rows, request_ids = self._search_rows(client, customer_id, MCC_CUSTOMER_QUERY)
                row = rows[0] if rows else None
        except Exception as exc:
            return _connection_check_failure(exc, customer_id, self.config.api_version)

        if row is None:
            return AdapterCheckResult(
                ok=False,
                status="ERROR",
                message=f"Google Ads не вернул данные MCC {customer_id} на безопасный запрос чтения.",
                api_version=self.config.api_version,
            )

        customer = row.customer
        if normalize_customer_id(str(customer.id)) != customer_id:
            return AdapterCheckResult(
                ok=False,
                status="ERROR",
                message=f"Google Ads вернул другой Customer ID: {customer.id} вместо {customer_id}.",
                api_version=self.config.api_version,
            )
        if not bool(customer.manager):
            return AdapterCheckResult(
                ok=False,
                status="ERROR",
                message=f"Аккаунт {customer_id} доступен, но Google Ads не считает его управляющим MCC.",
                api_version=self.config.api_version,
            )

        name = customer.descriptive_name or customer_id
        return AdapterCheckResult(
            ok=True,
            status="VERIFIED",
            message=(f"MCC подтверждён: {name} ({customer_id}), {customer.currency_code}, {customer.time_zone}."),
            api_version=self.config.api_version,
            request_id=request_ids[-1] if request_ids else None,
        )

    def list_customer_accounts(self) -> list[CustomerAccountInfo]:
        return list(self.discover_customer_hierarchy().accounts)

    def discover_customer_hierarchy(self) -> CustomerHierarchyResult:
        root_customer_id = normalize_customer_id(self.config.login_customer_id)
        self._recent_request_ids = []
        query = """
            SELECT
              customer_client.client_customer,
              customer_client.descriptive_name,
              customer_client.currency_code,
              customer_client.time_zone,
              customer_client.manager,
              customer_client.test_account,
              customer_client.hidden,
              customer_client.status,
              customer_client.level
            FROM customer_client
            WHERE customer_client.level <= 1
        """
        accounts: dict[str, CustomerAccountInfo] = {}
        try:
            with google_ads_client(self.config) as client:
                accessible_ids, accessible_request_ids = self._list_accessible_customers(client)
                if root_customer_id not in accessible_ids:
                    raise GoogleAdsAdapterError(
                        f"ListAccessibleCustomers не подтвердил доступ к MCC {root_customer_id}."
                    )
                root_state, root_request_ids = self._read_customer_state(client, root_customer_id)
                root = CustomerAccountInfo(
                    customer_id=root_customer_id,
                    manager_customer_id=None,
                    descriptive_name=root_state.get("descriptive_name"),
                    currency_code=root_state.get("currency_code"),
                    time_zone=root_state.get("time_zone"),
                    can_manage_clients=bool(root_state.get("manager")),
                    is_test_account=bool(root_state.get("test_account")),
                    is_hidden=False,
                    status=root_state.get("status"),
                    parent_customer_id=None,
                    hierarchy_level=0,
                    account_type="MANAGER",
                    request_ids=tuple(root_request_ids),
                    access_paths=((root_customer_id,),),
                )
                queue: list[tuple[str, tuple[str, ...]]] = [(root_customer_id, (root_customer_id,))]
                visited_paths: set[tuple[str, tuple[str, ...]]] = set()
                children_cache: dict[str, tuple[list, list[str]]] = {}
                customer_state_cache: dict[str, tuple[dict, list[str]]] = {
                    root_customer_id: (root_state, root_request_ids)
                }
                while queue:
                    manager_customer_id, manager_path = queue.pop(0)
                    visit_key = (manager_customer_id, manager_path)
                    if visit_key in visited_paths:
                        continue
                    visited_paths.add(visit_key)
                    if len(manager_path) > 20:
                        raise GoogleAdsAdapterError("Иерархия MCC глубже 20 уровней или содержит цикл.")
                    if manager_customer_id not in children_cache:
                        children_cache[manager_customer_id] = self._search_rows(client, manager_customer_id, query)
                    rows, hierarchy_request_ids = children_cache[manager_customer_id]
                    ordered_rows = sorted(
                        rows,
                        key=lambda item: str(item.customer_client.client_customer),
                    )
                    for row in ordered_rows:
                        resource_name = str(row.customer_client.client_customer)
                        customer_id = normalize_customer_id(resource_name.rsplit("/", 1)[-1])
                        level = int(row.customer_client.level)
                        if customer_id == manager_customer_id or level == 0:
                            continue
                        if customer_id in manager_path:
                            continue
                        child_path = (*manager_path, customer_id)
                        if customer_id not in customer_state_cache:
                            customer_state_cache[customer_id] = self._read_customer_state(client, customer_id)
                        customer_state, customer_request_ids = customer_state_cache[customer_id]
                        request_ids = tuple(dict.fromkeys([*hierarchy_request_ids, *customer_request_ids]))
                        account = CustomerAccountInfo(
                            customer_id=customer_id,
                            manager_customer_id=manager_customer_id,
                            descriptive_name=customer_state.get("descriptive_name")
                            or row.customer_client.descriptive_name
                            or None,
                            currency_code=customer_state.get("currency_code")
                            or row.customer_client.currency_code
                            or None,
                            time_zone=customer_state.get("time_zone") or row.customer_client.time_zone or None,
                            can_manage_clients=bool(customer_state.get("manager")),
                            is_test_account=bool(customer_state.get("test_account")),
                            is_hidden=bool(row.customer_client.hidden),
                            status=customer_state.get("status") or _enum_name(row.customer_client.status),
                            parent_customer_id=manager_customer_id,
                            hierarchy_level=len(child_path) - 1,
                            account_type=("MANAGER" if bool(customer_state.get("manager")) else "CLIENT"),
                            request_ids=request_ids,
                            access_paths=(child_path,),
                        )
                        existing = accounts.get(customer_id)
                        if existing:
                            all_paths = tuple(
                                sorted(
                                    {
                                        *existing.access_paths,
                                        *account.access_paths,
                                    },
                                    key=lambda item: (len(item), item),
                                )
                            )
                            primary_path = all_paths[0]
                            base = account if child_path == primary_path else existing
                            account = replace(
                                base,
                                manager_customer_id=(primary_path[-2] if len(primary_path) > 1 else None),
                                parent_customer_id=(primary_path[-2] if len(primary_path) > 1 else None),
                                hierarchy_level=len(primary_path) - 1,
                                request_ids=tuple(dict.fromkeys([*existing.request_ids, *request_ids])),
                                access_paths=all_paths,
                            )
                        accounts[customer_id] = account
                        if account.can_manage_clients:
                            queue.append((customer_id, child_path))
        except Exception as exc:
            message, _ = _google_ads_failure_message(
                exc,
                root_customer_id,
                f"Синхронизация аккаунтов MCC {root_customer_id} не выполнена",
            )
            raise GoogleAdsAdapterError(message) from exc
        return CustomerHierarchyResult(
            root=root,
            accounts=tuple(
                sorted(
                    accounts.values(),
                    key=lambda item: (
                        item.hierarchy_level or 0,
                        item.customer_id,
                    ),
                )
            ),
            accessible_customer_ids=tuple(sorted(accessible_ids)),
            request_ids=tuple(
                dict.fromkeys(
                    [
                        *accessible_request_ids,
                        *root_request_ids,
                        *self._recent_request_ids,
                    ]
                )
            ),
        )

    def _list_accessible_customers(self, client: Any) -> tuple[list[str], list[str]]:
        service = client.get_service("CustomerService")
        request = client.get_type("ListAccessibleCustomersRequest")
        response, request_id = unary_call_with_request_id(
            service,
            "list_accessible_customers",
            request,
            timeout=self.config.timeout_seconds,
        )
        request_ids = self._remember_request_id(request_id)
        customer_ids = [
            normalize_customer_id(str(resource_name).rsplit("/", 1)[-1]) for resource_name in response.resource_names
        ]
        return customer_ids, request_ids

    def _read_customer_state(self, client: Any, customer_id: str) -> tuple[dict, list[str]]:
        rows, request_ids = self._search_rows(client, customer_id, MCC_CUSTOMER_QUERY)
        if not rows:
            raise GoogleAdsAdapterError(f"Google Ads не вернул данные customer для {customer_id}.")
        customer = rows[0].customer
        return (
            {
                "customer_id": str(customer.id),
                "descriptive_name": customer.descriptive_name or None,
                "status": _enum_name(customer.status),
                "manager": bool(customer.manager),
                "test_account": bool(customer.test_account),
                "currency_code": customer.currency_code or None,
                "time_zone": customer.time_zone or None,
            },
            request_ids,
        )

    def _search_rows(self, client: Any, customer_id: str, query: str) -> tuple[list[Any], list[str]]:
        service = client.get_service("GoogleAdsService")
        if not hasattr(client, "get_type") or not hasattr(service, "transport"):
            return (
                list(
                    service.search(
                        customer_id=normalize_customer_id(customer_id),
                        query=query,
                    )
                ),
                [],
            )
        rows: list[Any] = []
        request_ids: list[str] = []
        page_token = ""
        while True:
            request = client.get_type("SearchGoogleAdsRequest")
            request.customer_id = normalize_customer_id(customer_id)
            request.query = query
            if page_token:
                request.page_token = page_token
            response, request_id = unary_call_with_request_id(
                service,
                "search",
                request,
                timeout=self.config.timeout_seconds,
                routing_fields=(("customer_id", request.customer_id),),
            )
            if not hasattr(response, "_pb"):
                response = type(client.get_type("SearchGoogleAdsResponse"))(response)
            rows.extend(response.results)
            request_ids.extend(self._remember_request_id(request_id))
            page_token = str(response.next_page_token or "")
            if not page_token:
                break
        return rows, list(dict.fromkeys(request_ids))

    def _remember_request_id(self, request_id: str | None) -> list[str]:
        if not request_id:
            return []
        self._recent_request_ids.append(request_id)
        return [request_id]

    def fetch_moderation(self, customer_ids: list[str]) -> list[dict]:
        query = """
            SELECT ad_group_ad.resource_name,
                   ad_group_ad.policy_summary.approval_status,
                   ad_group_ad.policy_summary.policy_topic_entries
            FROM ad_group_ad
            WHERE campaign.advertising_channel_type = DEMAND_GEN
        """
        result: list[dict] = []
        with google_ads_client(self.config) as client:
            service = client.get_service("GoogleAdsService")
            for customer_id in customer_ids:
                for batch in service.search_stream(customer_id=customer_id, query=query):
                    for row in batch.results:
                        summary = row.ad_group_ad.policy_summary
                        result.append(
                            {
                                "customer_id": customer_id,
                                "resource_name": row.ad_group_ad.resource_name,
                                "approval_status": getattr(summary.approval_status, "name", None)
                                or str(summary.approval_status),
                                "policy_topics": [
                                    {
                                        "topic": entry.topic,
                                        "type": getattr(entry.type_, "name", None) or str(entry.type_),
                                    }
                                    for entry in summary.policy_topic_entries
                                ],
                            }
                        )
        return result

    def fetch_statistics(self, customer_ids: list[str]) -> list[dict]:
        query = """
            SELECT segments.date,
                   metrics.impressions,
                   metrics.clicks,
                   metrics.cost_micros,
                   metrics.conversions
            FROM campaign
            WHERE campaign.advertising_channel_type = DEMAND_GEN
              AND segments.date DURING LAST_30_DAYS
        """
        totals: dict[tuple[str, str], dict] = {}
        with google_ads_client(self.config) as client:
            service = client.get_service("GoogleAdsService")
            for customer_id in customer_ids:
                for batch in service.search_stream(customer_id=customer_id, query=query):
                    for row in batch.results:
                        key = (customer_id, str(row.segments.date))
                        item = totals.setdefault(
                            key,
                            {"impressions": 0, "clicks": 0, "cost_micros": 0, "conversions": 0.0},
                        )
                        item["impressions"] += int(row.metrics.impressions)
                        item["clicks"] += int(row.metrics.clicks)
                        item["cost_micros"] += int(row.metrics.cost_micros)
                        item["conversions"] += float(row.metrics.conversions)
        return [
            {"customer_id": customer_id, "snapshot_date": snapshot_date, "metrics": metrics}
            for (customer_id, snapshot_date), metrics in totals.items()
        ]

    def validate_plan(self, snapshot: dict) -> PlanExecutionResult:
        return self._execute_plan(snapshot, validate_only=True)

    def deploy_plan(self, snapshot: dict) -> PlanExecutionResult:
        return self._execute_plan(snapshot, validate_only=False)

    def change_campaign_status(self, customer_id: str, campaigns: list[dict], status: str) -> PlanExecutionResult:
        return self._mutate_campaign_status(customer_id, campaigns, status, validate_only=False)

    def validate_campaign_status(self, customer_id: str, campaigns: list[dict], status: str) -> PlanExecutionResult:
        return self._mutate_campaign_status(customer_id, campaigns, status, validate_only=True)

    def _mutate_campaign_status(
        self,
        customer_id: str,
        campaigns: list[dict],
        status: str,
        *,
        validate_only: bool,
    ) -> PlanExecutionResult:
        self._require_google_test_mutate()
        requested_status = status.upper()
        if requested_status not in {"ENABLED", "PAUSED"}:
            raise ValueError("Google Ads поддерживает только ENABLED или PAUSED для этого действия")
        errors: list[dict] = []
        request_ids: list[str] = []
        rows: list[dict] = []
        self._recent_request_ids = []
        with google_ads_client(self.config) as client:
            request = client.get_type("MutateGoogleAdsRequest")
            request.customer_id = customer_id
            request.partial_failure = False
            request.validate_only = validate_only
            for item in campaigns:
                operation = client.get_type("MutateOperation")
                campaign = operation.campaign_operation.update
                campaign.resource_name = item["resource_name"]
                campaign.status = getattr(client.enums.CampaignStatusEnum, requested_status)
                operation.campaign_operation.update_mask.paths.append("status")
                request.mutate_operations.append(operation)
            try:
                service = client.get_service("GoogleAdsService")
                _, request_id = unary_call_with_request_id(
                    service,
                    "mutate",
                    request,
                    timeout=self.config.timeout_seconds,
                    routing_fields=(("customer_id", request.customer_id),),
                )
                request_ids.extend(self._remember_request_id(request_id))
                rows = [
                    {
                        "campaign_instance_id": item.get("campaign_instance_id"),
                        "customer_id": customer_id,
                        "ok": True,
                        "errors": [],
                        "warnings": [],
                        "request_ids": [request_id] if request_id else [],
                        "resource_names": [item["resource_name"]],
                        "status": requested_status,
                    }
                    for item in campaigns
                ]
            except Exception as exc:
                issues, request_id = _google_exception(exc, customer_id, None)
                errors.extend(issues)
                if request_id:
                    request_ids.append(request_id)
                rows = [
                    {
                        "campaign_instance_id": item.get("campaign_instance_id"),
                        "customer_id": customer_id,
                        "ok": False,
                        "errors": issues,
                        "warnings": [],
                        "request_ids": [request_id] if request_id else [],
                        "resource_names": [item["resource_name"]],
                        "status": requested_status,
                    }
                    for item in campaigns
                ]
        return PlanExecutionResult(
            ok=not errors,
            mode="VALIDATE_ONLY" if validate_only else self.config.connection_mode,
            errors=errors,
            warnings=[],
            request_ids=request_ids,
            resource_names=[item["resource_name"] for item in campaigns],
            details={
                "google_contacted": True,
                "validate_only": validate_only,
                "status": requested_status,
                "instances": rows,
            },
        )

    def change_campaign_budget(
        self,
        customer_id: str,
        budget_resource_name: str,
        amount_micros: int,
        validate_only: bool,
    ) -> PlanExecutionResult:
        self._require_google_test_mutate()
        if amount_micros <= 0:
            raise ValueError("Бюджет должен быть больше нуля")
        request_ids: list[str] = []
        errors: list[dict] = []
        self._recent_request_ids = []
        with google_ads_client(self.config) as client:
            operation = client.get_type("CampaignBudgetOperation")
            operation.update.resource_name = budget_resource_name
            operation.update.amount_micros = amount_micros
            operation.update_mask.paths.append("amount_micros")
            request = client.get_type("MutateCampaignBudgetsRequest")
            request.customer_id = normalize_customer_id(customer_id)
            request.operations.append(operation)
            request.validate_only = validate_only
            request.partial_failure = False
            try:
                service = client.get_service("CampaignBudgetService")
                _, request_id = unary_call_with_request_id(
                    service,
                    "mutate_campaign_budgets",
                    request,
                    timeout=self.config.timeout_seconds,
                    routing_fields=(("customer_id", request.customer_id),),
                )
                request_ids.extend(self._remember_request_id(request_id))
            except Exception as exc:
                errors, request_id = _google_exception(exc, customer_id, None)
                if request_id:
                    request_ids.append(request_id)
        return PlanExecutionResult(
            ok=not errors,
            mode="VALIDATE_ONLY" if validate_only else self.config.connection_mode,
            errors=errors,
            warnings=[],
            request_ids=request_ids,
            resource_names=[budget_resource_name],
            details={
                "google_contacted": True,
                "validate_only": validate_only,
                "amount_micros": amount_micros,
            },
        )

    def fetch_control_center_metrics(
        self,
        customer_id: str,
        start_date: str,
        end_date: str,
        conversion_actions: dict[str, list[str]] | None = None,
    ) -> dict:
        query = f"""
            SELECT
              segments.date,
              metrics.impressions,
              metrics.clicks,
              metrics.cost_micros,
              metrics.conversions,
              metrics.all_conversions,
              metrics.conversions_value
            FROM customer
            WHERE segments.date BETWEEN '{_escape_gaql(start_date)}'
              AND '{_escape_gaql(end_date)}'
        """
        mapped_actions = _normalized_conversion_actions(conversion_actions)
        totals = {
            "impressions": 0,
            "clicks": 0,
            "cost_micros": 0,
            "conversions": 0.0,
            "all_conversions": 0.0,
            "conversion_value": 0.0,
            "registrations": 0.0 if mapped_actions["REGISTRATION"] else None,
            "deposits": 0.0 if mapped_actions["DEPOSIT"] else None,
            "registration_value": 0.0 if mapped_actions["REGISTRATION"] else None,
            "deposit_value": 0.0 if mapped_actions["DEPOSIT"] else None,
            "registration_data_available": bool(mapped_actions["REGISTRATION"]),
            "deposit_data_available": bool(mapped_actions["DEPOSIT"]),
        }
        daily: dict[str, dict] = {}
        row_count = 0
        self._recent_request_ids = []
        with google_ads_client(self.config) as client:
            rows, request_ids = self._search_rows(client, normalize_customer_id(customer_id), query)
            for row in rows:
                row_count += 1
                item = {
                    "impressions": int(row.metrics.impressions),
                    "clicks": int(row.metrics.clicks),
                    "cost_micros": int(row.metrics.cost_micros),
                    "conversions": float(row.metrics.conversions),
                    "all_conversions": float(row.metrics.all_conversions),
                    "conversion_value": float(row.metrics.conversions_value),
                    "registrations": 0.0 if mapped_actions["REGISTRATION"] else None,
                    "deposits": 0.0 if mapped_actions["DEPOSIT"] else None,
                    "registration_value": 0.0 if mapped_actions["REGISTRATION"] else None,
                    "deposit_value": 0.0 if mapped_actions["DEPOSIT"] else None,
                    "registration_data_available": bool(mapped_actions["REGISTRATION"]),
                    "deposit_data_available": bool(mapped_actions["DEPOSIT"]),
                }
                daily[str(row.segments.date)] = item
                for field in (
                    "impressions",
                    "clicks",
                    "cost_micros",
                    "conversions",
                    "all_conversions",
                    "conversion_value",
                ):
                    value = item[field]
                    totals[field] += value
            conversion_request_ids: list[str] = []
            if mapped_actions["ALL"]:
                conversion_values = ", ".join(
                    f"'{_escape_gaql(item)}'" for item in sorted(mapped_actions["ALL"])
                )
                conversion_query = f"""
                    SELECT
                      segments.date,
                      segments.conversion_action,
                      metrics.conversions,
                      metrics.conversions_value
                    FROM customer
                    WHERE segments.date BETWEEN '{_escape_gaql(start_date)}'
                      AND '{_escape_gaql(end_date)}'
                      AND segments.conversion_action IN ({conversion_values})
                """
                conversion_rows, conversion_request_ids = self._search_rows(
                    client,
                    normalize_customer_id(customer_id),
                    conversion_query,
                )
                for row in conversion_rows:
                    resource_name = str(row.segments.conversion_action)
                    semantic_type = (
                        "REGISTRATION"
                        if resource_name in mapped_actions["REGISTRATION"]
                        else "DEPOSIT"
                        if resource_name in mapped_actions["DEPOSIT"]
                        else None
                    )
                    if semantic_type is None:
                        continue
                    day = str(row.segments.date)
                    item = daily.setdefault(
                        day,
                        _empty_metric_day(mapped_actions),
                    )
                    field = "registrations" if semantic_type == "REGISTRATION" else "deposits"
                    value_field = (
                        "registration_value"
                        if semantic_type == "REGISTRATION"
                        else "deposit_value"
                    )
                    conversions = float(row.metrics.conversions)
                    conversion_value = float(row.metrics.conversions_value)
                    item[field] = float(item[field] or 0) + conversions
                    item[value_field] = float(item[value_field] or 0) + conversion_value
                    totals[field] = float(totals[field] or 0) + conversions
                    totals[value_field] = float(totals[value_field] or 0) + conversion_value
            request_ids = list(dict.fromkeys([*request_ids, *conversion_request_ids]))
        return {
            **totals,
            "daily": [{"date": key, **value} for key, value in sorted(daily.items())],
            "has_data": row_count > 0,
            "_request_ids": request_ids,
        }

    def read_control_center_account(self, customer_id: str) -> dict:
        query = """
            SELECT
              customer.id,
              customer.descriptive_name,
              customer.status,
              customer.manager,
              customer.test_account,
              customer.currency_code,
              customer.time_zone
            FROM customer
            LIMIT 1
        """
        normalized_customer_id = normalize_customer_id(customer_id)
        self._recent_request_ids = []
        with google_ads_client(self.config) as client:
            rows, request_ids = self._search_rows(client, normalized_customer_id, query)
            row = rows[0] if rows else None
        if row is None:
            raise ValueError("Google Ads не вернул текущее состояние аккаунта")
        return {
            "customer_id": str(row.customer.id),
            "descriptive_name": row.customer.descriptive_name or None,
            "status": _enum_name(row.customer.status),
            "manager": bool(row.customer.manager),
            "test_account": bool(row.customer.test_account),
            "currency_code": row.customer.currency_code or None,
            "time_zone": row.customer.time_zone or None,
            "_request_ids": request_ids,
        }

    def fetch_identity_verification(self, customer_id: str) -> dict:
        try:
            from google.protobuf.json_format import MessageToDict
        except ImportError as exc:  # pragma: no cover - runtime dependency
            raise RuntimeError("Google protobuf runtime недоступен") from exc
        normalized_customer_id = normalize_customer_id(customer_id)
        with google_ads_client(self.config) as client:
            request = client.get_type("GetIdentityVerificationRequest")
            request.customer_id = normalized_customer_id
            response = client.get_service("IdentityVerificationService").get_identity_verification(request=request)
            raw = MessageToDict(
                response._pb,
                preserving_proto_field_name=True,
                use_integers_for_enums=False,
            )
        rows = raw.get("identity_verification") or []
        if not rows:
            return {
                "required": False,
                "status": "NOT_REQUIRED",
                "deadline": None,
                "action_url": None,
                "raw_status": {},
            }
        item = rows[0]
        requirement = item.get("identity_verification_requirement") or item.get("requirement") or {}
        progress = item.get("verification_progress") or {}
        deadline = requirement.get("verification_completion_deadline_time") or requirement.get(
            "verification_start_deadline_time"
        )
        status = progress.get("program_status") or item.get("program_status") or "UNKNOWN"
        return {
            "required": True,
            "status": status,
            "deadline": deadline,
            "action_url": progress.get("action_url"),
            "invitation_expires_at": progress.get("invitation_link_expiration_time"),
            "raw_status": {
                "verification_program": item.get("verification_program"),
                "program_status": status,
            },
        }

    def fetch_billing_summary(self, customer_id: str) -> dict:
        billing_setup_query = """
            SELECT
              billing_setup.resource_name,
              billing_setup.id,
              billing_setup.status,
              billing_setup.start_date_time,
              billing_setup.end_date_time,
              billing_setup.end_time_type,
              billing_setup.payments_account_info.payments_account_name,
              billing_setup.payments_account_info.payments_profile_name
            FROM billing_setup
        """
        account_budget_query = """
            SELECT
              account_budget.resource_name,
              account_budget.status,
              account_budget.billing_setup,
              account_budget.approved_spending_limit_micros,
              account_budget.approved_spending_limit_type,
              account_budget.adjusted_spending_limit_micros,
              account_budget.adjusted_spending_limit_type,
              account_budget.amount_served_micros,
              account_budget.total_adjustments_micros,
              account_budget.approved_start_date_time,
              account_budget.approved_end_date_time,
              account_budget.approved_end_time_type,
              account_budget.purchase_order_number
            FROM account_budget
        """
        normalized_customer_id = normalize_customer_id(customer_id)
        try:
            with google_ads_client(self.config) as client:
                setup_rows, setup_request_ids = self._search_rows(
                    client,
                    normalized_customer_id,
                    billing_setup_query,
                )
                budget_rows, budget_request_ids = self._search_rows(
                    client,
                    normalized_customer_id,
                    account_budget_query,
                )
        except Exception as exc:
            message, _ = _google_ads_failure_message(
                exc,
                normalized_customer_id,
                "Не удалось прочитать monthly invoicing",
            )
            raise GoogleAdsAdapterError(message) from exc
        request_ids = list(dict.fromkeys([*setup_request_ids, *budget_request_ids]))
        return {
            "billing_setups": [
                {
                    "resource_name": str(row.billing_setup.resource_name),
                    "billing_setup_id": str(row.billing_setup.id),
                    "status": _enum_name(row.billing_setup.status),
                    "start_date_time": row.billing_setup.start_date_time or None,
                    "end_date_time": row.billing_setup.end_date_time or None,
                    "end_time_type": _enum_name(row.billing_setup.end_time_type),
                    "payments_account_name": (
                        row.billing_setup.payments_account_info.payments_account_name or None
                    ),
                    "payments_profile_name": (
                        row.billing_setup.payments_account_info.payments_profile_name or None
                    ),
                }
                for row in setup_rows
            ],
            "account_budgets": [
                {
                    "resource_name": str(row.account_budget.resource_name),
                    "status": _enum_name(row.account_budget.status),
                    "billing_setup": str(row.account_budget.billing_setup),
                    "approved_spending_limit_micros": _optional_int(
                        row.account_budget,
                        "approved_spending_limit_micros",
                    ),
                    "approved_spending_limit_type": _enum_name(
                        row.account_budget.approved_spending_limit_type
                    ),
                    "adjusted_spending_limit_micros": _optional_int(
                        row.account_budget,
                        "adjusted_spending_limit_micros",
                    ),
                    "adjusted_spending_limit_type": _enum_name(
                        row.account_budget.adjusted_spending_limit_type
                    ),
                    "amount_served_micros": _optional_int(
                        row.account_budget,
                        "amount_served_micros",
                    ),
                    "total_adjustments_micros": _optional_int(
                        row.account_budget,
                        "total_adjustments_micros",
                    ),
                    "approved_start_date_time": (
                        row.account_budget.approved_start_date_time or None
                    ),
                    "approved_end_date_time": row.account_budget.approved_end_date_time or None,
                    "approved_end_time_type": _enum_name(
                        row.account_budget.approved_end_time_type
                    ),
                    "purchase_order_number": row.account_budget.purchase_order_number or None,
                }
                for row in budget_rows
            ],
            "request_ids": request_ids,
        }

    def list_control_center_campaigns(
        self,
        customer_id: str,
        start_date: str,
        end_date: str,
        conversion_actions: dict[str, list[str]] | None = None,
    ) -> list[dict]:
        core_query = """
            SELECT
              campaign.resource_name,
              campaign.id,
              campaign.name,
              campaign.status,
              campaign.primary_status,
              campaign.primary_status_reasons,
              campaign.advertising_channel_type,
              campaign.advertising_channel_sub_type,
              campaign.bidding_strategy_type,
              campaign.campaign_budget,
              campaign_budget.amount_micros,
              campaign_budget.explicitly_shared
            FROM campaign
            WHERE campaign.status != REMOVED
        """
        metric_query = f"""
            SELECT
              campaign.resource_name,
              metrics.impressions,
              metrics.clicks,
              metrics.cost_micros,
              metrics.conversions,
              metrics.all_conversions,
              metrics.conversions_value
            FROM campaign
            WHERE campaign.status != REMOVED
              AND segments.date BETWEEN '{_escape_gaql(start_date)}'
              AND '{_escape_gaql(end_date)}'
        """
        rows: dict[str, dict] = {}
        mapped_actions = _normalized_conversion_actions(conversion_actions)
        normalized_customer_id = normalize_customer_id(customer_id)
        self._recent_request_ids = []
        with google_ads_client(self.config) as client:
            core_rows, core_request_ids = self._search_rows(client, normalized_customer_id, core_query)
            for row in core_rows:
                campaign = row.campaign
                resource_name = str(campaign.resource_name)
                rows[resource_name] = {
                    "resource_name": resource_name,
                    "campaign_id": str(campaign.id),
                    "name": campaign.name,
                    "status": _enum_name(campaign.status),
                    "primary_status": _enum_name(campaign.primary_status),
                    "primary_status_reasons": [_enum_name(reason) for reason in campaign.primary_status_reasons],
                    "channel_type": _enum_name(campaign.advertising_channel_type),
                    "channel_subtype": _enum_name(campaign.advertising_channel_sub_type),
                    "bidding_strategy_type": _enum_name(campaign.bidding_strategy_type),
                    "budget_resource_name": str(campaign.campaign_budget) or None,
                    "budget_micros": int(row.campaign_budget.amount_micros),
                    "budget_shared": bool(row.campaign_budget.explicitly_shared),
                    "impressions": None,
                    "clicks": None,
                    "cost_micros": None,
                    "conversions": None,
                    "all_conversions": None,
                    "registrations": 0.0 if mapped_actions["REGISTRATION"] else None,
                    "deposits": 0.0 if mapped_actions["DEPOSIT"] else None,
                    "registration_data_available": bool(mapped_actions["REGISTRATION"]),
                    "deposit_data_available": bool(mapped_actions["DEPOSIT"]),
                    "conversion_value": None,
                    "policy_status": _enum_name(campaign.primary_status),
                    "policy_issues": [
                        _enum_name(reason)
                        for reason in campaign.primary_status_reasons
                        if "POLICY" in _enum_name(reason)
                    ],
                }
            metric_rows, metric_request_ids = self._search_rows(client, normalized_customer_id, metric_query)
            for row in metric_rows:
                item = rows.get(str(row.campaign.resource_name))
                if not item:
                    continue
                item.update(
                    {
                        "impressions": int(row.metrics.impressions),
                        "clicks": int(row.metrics.clicks),
                        "cost_micros": int(row.metrics.cost_micros),
                        "conversions": float(row.metrics.conversions),
                        "all_conversions": float(row.metrics.all_conversions),
                        "conversion_value": float(row.metrics.conversions_value),
                    }
                )
            conversion_request_ids: list[str] = []
            if mapped_actions["ALL"]:
                conversion_values = ", ".join(
                    f"'{_escape_gaql(item)}'" for item in sorted(mapped_actions["ALL"])
                )
                conversion_query = f"""
                    SELECT
                      campaign.resource_name,
                      segments.conversion_action,
                      metrics.conversions
                    FROM campaign
                    WHERE campaign.status != REMOVED
                      AND segments.date BETWEEN '{_escape_gaql(start_date)}'
                      AND '{_escape_gaql(end_date)}'
                      AND segments.conversion_action IN ({conversion_values})
                """
                conversion_rows, conversion_request_ids = self._search_rows(
                    client,
                    normalized_customer_id,
                    conversion_query,
                )
                for row in conversion_rows:
                    item = rows.get(str(row.campaign.resource_name))
                    if not item:
                        continue
                    resource_name = str(row.segments.conversion_action)
                    field = (
                        "registrations"
                        if resource_name in mapped_actions["REGISTRATION"]
                        else "deposits"
                        if resource_name in mapped_actions["DEPOSIT"]
                        else None
                    )
                    if field:
                        item[field] = float(item[field] or 0) + float(row.metrics.conversions)
        request_ids = list(
            dict.fromkeys(
                [
                    *core_request_ids,
                    *metric_request_ids,
                    *conversion_request_ids,
                ]
            )
        )
        for item in rows.values():
            item["_request_ids"] = request_ids
        return list(rows.values())

    def list_conversion_actions(self, customer_id: str) -> list[dict]:
        query = """
            SELECT
              conversion_action.resource_name,
              conversion_action.id,
              conversion_action.name,
              conversion_action.category,
              conversion_action.status,
              conversion_action.owner_customer
            FROM conversion_action
            WHERE conversion_action.status != REMOVED
            LIMIT 10000
        """
        with google_ads_client(self.config) as client:
            rows, request_ids = self._search_rows(
                client,
                normalize_customer_id(customer_id),
                query,
            )
        result = [
            {
                "resource_name": str(row.conversion_action.resource_name),
                "conversion_action_id": str(row.conversion_action.id),
                "name": row.conversion_action.name or None,
                "category": _enum_name(row.conversion_action.category),
                "status": _enum_name(row.conversion_action.status),
                "owner_customer_id": _customer_id_from_resource(
                    str(row.conversion_action.owner_customer)
                ),
                "_request_ids": request_ids,
            }
            for row in rows
        ]
        return result

    def list_control_center_ad_groups(self, customer_id: str) -> list[dict]:
        query = """
            SELECT
              campaign.resource_name,
              ad_group.resource_name,
              ad_group.id,
              ad_group.name,
              ad_group.status,
              ad_group.type
            FROM ad_group
            WHERE ad_group.status != REMOVED
            LIMIT 10000
        """
        with google_ads_client(self.config) as client:
            rows, request_ids = self._search_rows(
                client,
                normalize_customer_id(customer_id),
                query,
            )
        return [
            {
                "campaign_resource_name": str(row.campaign.resource_name),
                "resource_name": str(row.ad_group.resource_name),
                "ad_group_id": str(row.ad_group.id),
                "name": row.ad_group.name,
                "status": _enum_name(row.ad_group.status),
                "type": _enum_name(row.ad_group.type_),
                "_request_ids": request_ids,
            }
            for row in rows
        ]

    def list_control_center_ads(self, customer_id: str) -> list[dict]:
        query = """
            SELECT
              campaign.resource_name,
              ad_group.resource_name,
              ad_group_ad.resource_name,
              ad_group_ad.status,
              ad_group_ad.policy_summary.approval_status,
              ad_group_ad.policy_summary.review_status,
              ad_group_ad.policy_summary.policy_topic_entries,
              ad_group_ad.ad.resource_name,
              ad_group_ad.ad.id,
              ad_group_ad.ad.name,
              ad_group_ad.ad.type,
              ad_group_ad.ad.final_urls
            FROM ad_group_ad
            WHERE ad_group_ad.status != REMOVED
            LIMIT 10000
        """
        with google_ads_client(self.config) as client:
            rows, request_ids = self._search_rows(
                client,
                normalize_customer_id(customer_id),
                query,
            )
        return [
            {
                "campaign_resource_name": str(row.campaign.resource_name),
                "ad_group_resource_name": str(row.ad_group.resource_name),
                "resource_name": str(row.ad_group_ad.resource_name),
                "ad_resource_name": str(row.ad_group_ad.ad.resource_name),
                "ad_id": str(row.ad_group_ad.ad.id),
                "name": row.ad_group_ad.ad.name or None,
                "type": _enum_name(row.ad_group_ad.ad.type_),
                "status": _enum_name(row.ad_group_ad.status),
                "final_urls": [str(value) for value in row.ad_group_ad.ad.final_urls],
                "policy_approval_status": _enum_name(
                    row.ad_group_ad.policy_summary.approval_status
                ),
                "policy_review_status": _enum_name(
                    row.ad_group_ad.policy_summary.review_status
                ),
                "policy_topics": _policy_topics(
                    row.ad_group_ad.policy_summary.policy_topic_entries
                ),
                "_request_ids": request_ids,
            }
            for row in rows
        ]

    def list_control_center_asset_links(self, customer_id: str) -> list[dict]:
        query = """
            SELECT
              campaign.resource_name,
              ad_group.resource_name,
              ad_group_ad.resource_name,
              ad_group_ad_asset_view.resource_name,
              ad_group_ad_asset_view.field_type,
              ad_group_ad_asset_view.performance_label,
              asset.resource_name,
              asset.id,
              asset.name,
              asset.type,
              asset.image_asset.full_size.url,
              asset.image_asset.full_size.width_pixels,
              asset.image_asset.full_size.height_pixels,
              asset.youtube_video_asset.youtube_video_id
            FROM ad_group_ad_asset_view
            LIMIT 10000
        """
        with google_ads_client(self.config) as client:
            rows, request_ids = self._search_rows(
                client,
                normalize_customer_id(customer_id),
                query,
            )
        return [
            {
                "campaign_resource_name": str(row.campaign.resource_name),
                "ad_group_resource_name": str(row.ad_group.resource_name),
                "ad_resource_name": str(row.ad_group_ad.resource_name),
                "link_resource_name": str(row.ad_group_ad_asset_view.resource_name),
                "field_type": _enum_name(row.ad_group_ad_asset_view.field_type),
                "performance_label": _enum_name(
                    row.ad_group_ad_asset_view.performance_label
                ),
                "asset_resource_name": str(row.asset.resource_name),
                "asset_id": str(row.asset.id),
                "asset_name": row.asset.name or None,
                "asset_type": _enum_name(row.asset.type_),
                "image_url": row.asset.image_asset.full_size.url or None,
                "width": int(row.asset.image_asset.full_size.width_pixels or 0) or None,
                "height": int(row.asset.image_asset.full_size.height_pixels or 0) or None,
                "youtube_video_id": (
                    row.asset.youtube_video_asset.youtube_video_id or None
                ),
                "_request_ids": request_ids,
            }
            for row in rows
        ]

    def fetch_control_center_changes(
        self,
        customer_id: str,
        start_date_time: str,
        end_date_time: str,
    ) -> list[dict]:
        start_date = _gaql_date(start_date_time)
        end_date = _gaql_date(end_date_time)
        query = f"""
            SELECT
              change_event.resource_name,
              change_event.change_date_time,
              change_event.change_resource_name,
              change_event.change_resource_type,
              change_event.client_type,
              change_event.resource_change_operation,
              change_event.user_email,
              change_event.changed_fields,
              change_event.old_resource,
              change_event.new_resource
            FROM change_event
            WHERE change_event.change_date_time >= '{start_date}'
              AND change_event.change_date_time <= '{end_date}'
            ORDER BY change_event.change_date_time DESC
            LIMIT 10000
        """
        with google_ads_client(self.config) as client:
            rows, request_ids = self._search_rows(
                client,
                normalize_customer_id(customer_id),
                query,
            )
        return [
            {
                "resource_name": str(row.change_event.resource_name),
                "changed_at": str(row.change_event.change_date_time),
                "changed_resource_name": str(
                    row.change_event.change_resource_name
                ),
                "resource_type": _enum_name(
                    row.change_event.change_resource_type
                ),
                "change_type": _change_type(row.change_event),
                "client_type": _enum_name(row.change_event.client_type),
                "user_email": row.change_event.user_email or None,
                "changed_fields": list(row.change_event.changed_fields.paths),
                "old_resource": _protobuf_payload(row.change_event.old_resource),
                "new_resource": _protobuf_payload(row.change_event.new_resource),
                "_request_ids": request_ids,
            }
            for row in rows
        ]

    def read_control_center_campaign(self, customer_id: str, resource_name: str) -> dict:
        query = f"""
            SELECT
              campaign.resource_name,
              campaign.id,
              campaign.name,
              campaign.status,
              campaign.primary_status,
              campaign.primary_status_reasons,
              campaign.campaign_budget,
              campaign_budget.amount_micros,
              campaign_budget.explicitly_shared,
              campaign_budget.reference_count
            FROM campaign
            WHERE campaign.resource_name = '{_escape_gaql(resource_name)}'
            LIMIT 1
        """
        self._recent_request_ids = []
        with google_ads_client(self.config) as client:
            rows, request_ids = self._search_rows(client, normalize_customer_id(customer_id), query)
            row = rows[0] if rows else None
        if row is None:
            raise ValueError("Кампания не найдена или больше недоступна")
        return {
            "resource_name": str(row.campaign.resource_name),
            "campaign_id": str(row.campaign.id),
            "name": row.campaign.name,
            "status": _enum_name(row.campaign.status),
            "primary_status": _enum_name(row.campaign.primary_status),
            "primary_status_reasons": [_enum_name(reason) for reason in row.campaign.primary_status_reasons],
            "budget_resource_name": str(row.campaign.campaign_budget) or None,
            "budget_micros": int(row.campaign_budget.amount_micros),
            "budget_shared": bool(row.campaign_budget.explicitly_shared),
            "budget_reference_count": int(row.campaign_budget.reference_count),
            "_request_ids": request_ids,
        }

    def fetch_campaign_performance(self, customer_id: str, resource_names: list[str]) -> list[dict]:
        if not resource_names:
            return []
        values = ", ".join(f"'{_escape_gaql(item)}'" for item in resource_names)
        query = f"""
            SELECT campaign.resource_name,
                   campaign.name,
                   campaign.status,
                   metrics.impressions,
                   metrics.clicks,
                   metrics.cost_micros,
                   metrics.conversions,
                   metrics.conversions_value
            FROM campaign
            WHERE campaign.resource_name IN ({values})
              AND segments.date DURING LAST_30_DAYS
        """
        rows: list[dict] = []
        with google_ads_client(self.config) as client:
            service = client.get_service("GoogleAdsService")
            for batch in service.search_stream(customer_id=customer_id, query=query):
                for row in batch.results:
                    rows.append(
                        {
                            "customer_id": customer_id,
                            "resource_name": str(row.campaign.resource_name),
                            "campaign_name": row.campaign.name,
                            "status": _enum_name(row.campaign.status),
                            "metrics": {
                                "impressions": int(row.metrics.impressions),
                                "clicks": int(row.metrics.clicks),
                                "cost_micros": int(row.metrics.cost_micros),
                                "conversions": float(row.metrics.conversions),
                                "conversion_value": float(row.metrics.conversions_value),
                            },
                        }
                    )
        return rows

    def fetch_account_catalog(self, customer_id: str) -> dict:
        queries = {
            "conversion_actions": """
                SELECT conversion_action.resource_name, conversion_action.name,
                       conversion_action.category, conversion_action.status
                FROM conversion_action
                WHERE conversion_action.status != REMOVED
                LIMIT 10000
            """,
            "audiences": """
                SELECT audience.resource_name, audience.name, audience.description
                FROM audience
                LIMIT 10000
            """,
            "user_lists": """
                SELECT user_list.resource_name, user_list.name, user_list.type,
                       user_list.size_for_display
                FROM user_list
                LIMIT 10000
            """,
            "assets": """
                SELECT asset.resource_name, asset.name, asset.type
                FROM asset
                LIMIT 10000
            """,
            "user_interests": """
                SELECT user_interest.resource_name, user_interest.user_interest_id,
                       user_interest.name, user_interest.taxonomy_type,
                       user_interest.user_interest_parent
                FROM user_interest
                LIMIT 10000
            """,
        }
        result: dict[str, list[dict] | str | bool] = {
            "customer_id": customer_id,
            "mode": self.config.connection_mode,
            "google_contacted": True,
        }
        with google_ads_client(self.config) as client:
            service = client.get_service("GoogleAdsService")
            result["conversion_actions"] = [
                {
                    "resource_name": str(row.conversion_action.resource_name),
                    "name": row.conversion_action.name,
                    "category": _enum_name(row.conversion_action.category),
                    "status": _enum_name(row.conversion_action.status),
                }
                for row in service.search(customer_id=customer_id, query=queries["conversion_actions"])
            ]
            result["audiences"] = [
                {
                    "resource_name": str(row.audience.resource_name),
                    "name": row.audience.name,
                    "description": row.audience.description,
                }
                for row in service.search(customer_id=customer_id, query=queries["audiences"])
            ]
            result["user_lists"] = [
                {
                    "resource_name": str(row.user_list.resource_name),
                    "name": row.user_list.name,
                    "type": _enum_name(row.user_list.type_),
                    "size_for_display": int(row.user_list.size_for_display),
                }
                for row in service.search(customer_id=customer_id, query=queries["user_lists"])
            ]
            result["assets"] = [
                {
                    "resource_name": str(row.asset.resource_name),
                    "name": row.asset.name,
                    "type": _enum_name(row.asset.type_),
                }
                for row in service.search(customer_id=customer_id, query=queries["assets"])
            ]
            result["user_interests"] = [
                {
                    "resource_name": str(row.user_interest.resource_name),
                    "user_interest_id": str(row.user_interest.user_interest_id),
                    "name": row.user_interest.name,
                    "taxonomy_type": _enum_name(row.user_interest.taxonomy_type),
                    "parent_resource_name": str(
                        row.user_interest.user_interest_parent or ""
                    ),
                }
                for row in service.search(
                    customer_id=customer_id,
                    query=queries["user_interests"],
                )
            ]
        return result

    def read_campaign(self, customer_id: str, campaign_resource_name: str) -> dict:
        query = f"""
            SELECT campaign.resource_name, campaign.name, campaign.status,
                   campaign.campaign_budget, campaign.bidding_strategy_type,
                   campaign.target_cpa.target_cpa_micros,
                   campaign.target_roas.target_roas,
                   campaign.start_date_time, campaign.end_date_time,
                   campaign.tracking_url_template, campaign.final_url_suffix
            FROM campaign
            WHERE campaign.resource_name = '{_escape_gaql(campaign_resource_name)}'
              AND campaign.advertising_channel_type = DEMAND_GEN
            LIMIT 1
        """
        self._recent_request_ids = []
        with google_ads_client(self.config) as client:
            rows, request_ids = self._search_rows(client, customer_id, query)
            row = rows[0] if rows else None
        if not row:
            raise ValueError("Кампания Demand Gen не найдена в выбранном аккаунте")
        strategy = _enum_name(row.campaign.bidding_strategy_type)
        template = {
            "campaign": {
                "source_campaign_resource": str(row.campaign.resource_name),
                "ad_group_name": "Основная группа",
                "ad_type": "IMAGE",
                "start_date_time": row.campaign.start_date_time or None,
                "end_date_time": row.campaign.end_date_time or None,
            },
            "bidding": {
                "strategy": strategy,
                "target_cpa_micros": int(row.campaign.target_cpa.target_cpa_micros or 0),
                "target_roas": float(row.campaign.target_roas.target_roas or 0),
            },
            "url": {
                "tracking_template": row.campaign.tracking_url_template or None,
                "final_url_suffix": row.campaign.final_url_suffix or None,
            },
            "targeting": {},
            "texts": {},
            "ads": {},
        }
        return {
            "customer_id": customer_id,
            "campaign_resource_name": campaign_resource_name,
            "mode": self.config.connection_mode,
            "google_contacted": True,
            "source_campaign_name": row.campaign.name,
            "template": template,
            "_request_ids": request_ids,
        }

    def read_demand_gen_resources(
        self,
        customer_id: str,
        campaign_resource_name: str,
        known_resource_names: list[str] | None = None,
    ) -> dict:
        normalized_customer_id = normalize_customer_id(customer_id)
        escaped_campaign = _escape_gaql(campaign_resource_name)
        self._recent_request_ids = []
        queries = {
            "campaigns": f"""
                SELECT campaign.resource_name, campaign.id, campaign.name,
                       campaign.status, campaign.advertising_channel_type,
                       campaign.campaign_budget,
                       campaign_budget.resource_name, campaign_budget.id,
                       campaign_budget.amount_micros,
                       campaign_budget.explicitly_shared
                FROM campaign
                WHERE campaign.resource_name = '{escaped_campaign}'
                LIMIT 1
            """,
            "ad_groups": f"""
                SELECT ad_group.resource_name, ad_group.id, ad_group.name,
                       ad_group.status, ad_group.campaign
                FROM ad_group
                WHERE campaign.resource_name = '{escaped_campaign}'
            """,
            "ads": f"""
                SELECT ad_group_ad.resource_name, ad_group_ad.status,
                       ad_group_ad.ad.resource_name, ad_group_ad.ad.id,
                       ad_group_ad.ad.name, ad_group_ad.ad.type,
                       ad_group_ad.ad.final_urls
                FROM ad_group_ad
                WHERE campaign.resource_name = '{escaped_campaign}'
            """,
            "campaign_criteria": f"""
                SELECT campaign_criterion.resource_name,
                       campaign_criterion.criterion_id,
                       campaign_criterion.type,
                       campaign_criterion.negative
                FROM campaign_criterion
                WHERE campaign.resource_name = '{escaped_campaign}'
            """,
            "ad_group_criteria": f"""
                SELECT ad_group_criterion.resource_name,
                       ad_group_criterion.criterion_id,
                       ad_group_criterion.type,
                       ad_group_criterion.negative,
                       ad_group_criterion.audience.audience
                FROM ad_group_criterion
                WHERE campaign.resource_name = '{escaped_campaign}'
            """,
        }
        payload: dict[str, list[dict]] = {}
        with google_ads_client(self.config) as client:
            for key, query in queries.items():
                rows, _ = self._search_rows(client, normalized_customer_id, query)
                payload[key] = [_resource_readback_row(key, row) for row in rows]
            asset_names = [item for item in (known_resource_names or []) if "/assets/" in str(item)]
            if asset_names:
                values = ", ".join(f"'{_escape_gaql(item)}'" for item in asset_names)
                asset_rows, _ = self._search_rows(
                    client,
                    normalized_customer_id,
                    f"""
                        SELECT asset.resource_name, asset.id, asset.name, asset.type
                        FROM asset
                        WHERE asset.resource_name IN ({values})
                    """,
                )
                payload["assets"] = [_resource_readback_row("assets", row) for row in asset_rows]
            else:
                payload["assets"] = []
            audience_names = [item for item in (known_resource_names or []) if "/audiences/" in str(item)]
            if audience_names:
                values = ", ".join(f"'{_escape_gaql(item)}'" for item in audience_names)
                audience_rows, _ = self._search_rows(
                    client,
                    normalized_customer_id,
                    f"""
                        SELECT audience.resource_name, audience.id,
                               audience.name, audience.status
                        FROM audience
                        WHERE audience.resource_name IN ({values})
                    """,
                )
                payload["audiences"] = [_resource_readback_row("audiences", row) for row in audience_rows]
            else:
                payload["audiences"] = []
        campaign_rows = payload["campaigns"]
        if not campaign_rows:
            raise ValueError("Созданная Demand Gen кампания не найдена при повторном чтении")
        return {
            "customer_id": normalized_customer_id,
            "campaign_resource_name": campaign_resource_name,
            "mode": self.config.connection_mode,
            "google_contacted": True,
            "request_ids": list(dict.fromkeys(self._recent_request_ids)),
            "resources": payload,
            "verified": {
                "campaign_paused": campaign_rows[0].get("status") == "PAUSED",
                "budget_present": bool(campaign_rows[0].get("budget_resource_name")),
                "ad_groups_present": bool(payload["ad_groups"]),
                "ads_present": bool(payload["ads"]),
                "criteria_present": bool(payload["campaign_criteria"] or payload["ad_group_criteria"]),
                "assets_present": bool(payload["assets"]),
                "audiences_present": bool(payload["audiences"]),
            },
        }

    def _execute_plan(self, snapshot: dict, validate_only: bool) -> PlanExecutionResult:
        self._require_google_test_mutate()
        errors: list[dict] = []
        warnings: list[dict] = []
        request_ids: list[str] = []
        resources: list[str] = []
        instance_results: list[dict] = []
        self._recent_request_ids = []
        with google_ads_client(self.config) as client:
            service = client.get_service("GoogleAdsService")
            for campaign in snapshot.get("campaigns") or []:
                request_id_start = len(self._recent_request_ids)
                customer_id = str(campaign["customer_id"])
                instance_result = {
                    "campaign_instance_id": campaign.get("campaign_instance_id"),
                    "customer_id": customer_id,
                    "campaign_name": campaign.get("campaign_name"),
                    "ok": True,
                    "errors": [],
                    "warnings": [],
                    "request_ids": [],
                    "resource_names": [],
                }
                if not validate_only:
                    existing = self._find_existing_campaign(client, customer_id, campaign["google_campaign_name"])
                    if existing:
                        resources.append(existing)
                        warning = {
                            "code": "IDEMPOTENT_REUSE",
                            "message": f"Кампания уже существует: {campaign['google_campaign_name']}",
                        }
                        warnings.append(warning)
                        instance_result["warnings"].append(warning)
                        instance_result["resource_names"].append(existing)
                        instance_results.append(instance_result)
                        continue
                try:
                    operations = self._build_operations(
                        client,
                        customer_id,
                        campaign,
                        snapshot.get("media") or [],
                        service=service,
                    )
                    request = client.get_type("MutateGoogleAdsRequest")
                    request.customer_id = customer_id
                    request.mutate_operations.extend(operations)
                    request.partial_failure = False
                    request.validate_only = validate_only
                    response, request_id = unary_call_with_request_id(
                        service,
                        "mutate",
                        request,
                        timeout=self.config.timeout_seconds,
                        routing_fields=(("customer_id", request.customer_id),),
                    )
                    self._remember_request_id(request_id)
                    if not validate_only:
                        created_resources = _resource_names(response)
                        resources.extend(created_resources)
                        instance_result["resource_names"].extend(created_resources)
                except Exception as exc:
                    issue, request_id = _google_exception(exc, customer_id, campaign.get("campaign_name"))
                    errors.extend(issue)
                    instance_result["ok"] = False
                    instance_result["errors"].extend(issue)
                    if request_id:
                        request_ids.append(request_id)
                        instance_result["request_ids"].append(request_id)
                instance_result["request_ids"] = list(
                    dict.fromkeys(
                        [
                            *instance_result["request_ids"],
                            *self._recent_request_ids[request_id_start:],
                        ]
                    )
                )
                instance_results.append(instance_result)

        request_ids = list(dict.fromkeys([*request_ids, *self._recent_request_ids]))
        return PlanExecutionResult(
            ok=not errors,
            mode=self.config.connection_mode,
            errors=errors,
            warnings=warnings,
            request_ids=request_ids,
            resource_names=resources,
            details={
                "validate_only": validate_only,
                "google_contacted": True,
                "campaign_status": "PAUSED",
                "atomic_scope": "campaign",
                "instances": instance_results,
            },
        )

    def _require_google_test_mutate(self) -> None:
        if self.config.connection_mode != "GOOGLE_TEST":
            raise GoogleAdsAdapterError(
                "PRODUCTION_MUTATE_BLOCKED: Google Ads mutate разрешён только для отдельного подключения GOOGLE_TEST."
            )

    def _find_existing_campaign(self, client: Any, customer_id: str, campaign_name: str) -> str | None:
        escaped = campaign_name.replace("\\", "\\\\").replace("'", "\\'")
        query = f"""
            SELECT campaign.resource_name
            FROM campaign
            WHERE campaign.name = '{escaped}'
              AND campaign.advertising_channel_type = DEMAND_GEN
            LIMIT 1
        """
        rows, _ = self._search_rows(client, customer_id, query)
        for row in rows:
            return str(row.campaign.resource_name)
        return None

    def _find_existing_asset(self, client: Any, customer_id: str, asset_name: str) -> str | None:
        query = f"""
            SELECT asset.resource_name
            FROM asset
            WHERE asset.name = '{_escape_gaql(asset_name)}'
            LIMIT 1
        """
        rows, _ = self._search_rows(client, customer_id, query)
        for row in rows:
            return str(row.asset.resource_name)
        return None

    def _build_operations(
        self,
        client: Any,
        customer_id: str,
        campaign: dict,
        media: list[dict],
        service: Any | None = None,
    ) -> list[Any]:
        operations: list[Any] = []
        budget_name = client.get_service("CampaignBudgetService").campaign_budget_path(customer_id, -1)
        campaign_name = client.get_service("CampaignService").campaign_path(customer_id, -2)
        ad_group_name = client.get_service("AdGroupService").ad_group_path(customer_id, -3)

        budget_op = client.get_type("MutateOperation")
        budget = budget_op.campaign_budget_operation.create
        budget.resource_name = budget_name
        budget.name = f"{campaign['google_campaign_name']} budget"
        if str(campaign.get("budget_type") or "DAILY").upper() == "TOTAL":
            budget.total_amount_micros = int(campaign["daily_budget_micros"])
            budget.period = client.enums.BudgetPeriodEnum.CUSTOM_PERIOD
        else:
            budget.amount_micros = int(campaign["daily_budget_micros"])
        budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
        budget.explicitly_shared = False
        operations.append(budget_op)

        campaign_op = client.get_type("MutateOperation")
        created_campaign = campaign_op.campaign_operation.create
        created_campaign.resource_name = campaign_name
        created_campaign.name = campaign["google_campaign_name"]
        created_campaign.status = client.enums.CampaignStatusEnum.PAUSED
        created_campaign.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.DEMAND_GEN
        created_campaign.campaign_budget = budget_name
        _set_bidding(client, created_campaign, campaign)
        if campaign.get("start_date_time"):
            created_campaign.start_date_time = _google_date_time(campaign["start_date_time"])
        if campaign.get("end_date_time"):
            created_campaign.end_date_time = _google_date_time(campaign["end_date_time"])
        if campaign.get("tracking_template"):
            created_campaign.tracking_url_template = campaign["tracking_template"]
        if campaign.get("final_url_suffix"):
            created_campaign.final_url_suffix = campaign["final_url_suffix"]
        _append_custom_parameters(
            client,
            created_campaign.url_custom_parameters,
            campaign.get("custom_parameters") or [],
        )
        for resource_name in campaign.get("conversion_action_resource_names") or []:
            created_campaign.selective_optimization.conversion_actions.append(resource_name)
        created_campaign.contains_eu_political_advertising = (
            client.enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
        )
        operations.append(campaign_op)

        created_audience_name: str | None = None
        audience_config = campaign.get("create_audience") or {}
        if audience_config:
            created_audience_name = client.get_service("AudienceService").audience_path(customer_id, -4)
            audience_op = client.get_type("MutateOperation")
            audience = audience_op.audience_operation.create
            audience.resource_name = created_audience_name
            audience.name = str(audience_config.get("name") or f"{campaign['google_campaign_name']} audience")[:255]
            audience.description = str(
                audience_config.get("description") or "Demand Gen Uploader Google Test acceptance audience"
            )[:10_000]
            age_dimension = client.get_type("AudienceDimension")
            age_range = client.get_type("AgeSegment")
            age_range.min_age = 18
            age_range.max_age = 64
            age_dimension.age.age_ranges.append(age_range)
            age_dimension.age.include_undetermined = True
            audience.dimensions.append(age_dimension)
            operations.append(audience_op)

        ad_group_op = client.get_type("MutateOperation")
        ad_group = ad_group_op.ad_group_operation.create
        ad_group.resource_name = ad_group_name
        ad_group.name = str(campaign["ad_group_name"])[:255]
        ad_group.campaign = campaign_name
        ad_group.status = client.enums.AdGroupStatusEnum.ENABLED
        ad_group.optimized_targeting_enabled = bool(campaign.get("optimized_targeting", True))
        if created_audience_name:
            ad_group.audience_setting.use_audience_grouped = True
        _configure_channel_controls(client, ad_group, campaign.get("channel_controls") or {})
        operations.append(ad_group_op)

        for location_id in campaign.get("location_ids") or []:
            operations.append(
                _criterion_operation(
                    client,
                    ad_group_name,
                    "location.geo_target_constant",
                    f"geoTargetConstants/{location_id}",
                )
            )
        for location_id in campaign.get("excluded_location_ids") or []:
            operations.append(
                _criterion_operation(
                    client,
                    ad_group_name,
                    "location.geo_target_constant",
                    f"geoTargetConstants/{location_id}",
                    negative=True,
                )
            )
        for language_id in campaign.get("language_ids") or []:
            operations.append(
                _criterion_operation(
                    client,
                    ad_group_name,
                    "language.language_constant",
                    f"languageConstants/{language_id}",
                )
            )
        for resource_name in campaign.get("audience_resource_names") or []:
            operations.append(_criterion_operation(client, ad_group_name, "audience.audience", resource_name))
        if created_audience_name:
            operations.append(
                _criterion_operation(
                    client,
                    ad_group_name,
                    "audience.audience",
                    created_audience_name,
                )
            )
        for resource_name in campaign.get("user_list_resource_names") or []:
            operations.append(_criterion_operation(client, ad_group_name, "user_list.user_list", resource_name))
        for resource_name in campaign.get("custom_audience_resource_names") or []:
            operations.append(
                _criterion_operation(client, ad_group_name, "custom_audience.custom_audience", resource_name)
            )
        for resource_name in campaign.get("user_interest_resource_names") or []:
            operations.append(
                _criterion_operation(client, ad_group_name, "user_interest.user_interest_category", resource_name)
            )
        for life_event_id in campaign.get("life_event_ids") or []:
            operations.append(_criterion_operation(client, ad_group_name, "life_event.life_event_id", life_event_id))
        _append_demographic_operations(client, operations, ad_group_name, campaign.get("demographics") or {})
        _append_schedule_operations(client, operations, campaign_name, campaign.get("schedule") or [])

        selected_ids = set(campaign.get("media_ids") or [])
        selected_media = [item for item in media if item.get("id") in selected_ids]
        next_temp_id = -10
        image_assets: list[tuple[str, dict]] = []
        for item in selected_media:
            if item.get("kind") != "IMAGE" or not item.get("storage_key"):
                continue
            _customer_scope, sha256 = asset_cache_key(customer_id, str(item["sha256"]))
            stable_name = f"DGU image {sha256}"[:255]
            asset_name = self._find_existing_asset(client, customer_id, stable_name) if service else None
            if not asset_name:
                asset_name = client.get_service("AssetService").asset_path(customer_id, next_temp_id)
                next_temp_id -= 1
                asset_op = client.get_type("MutateOperation")
                asset = asset_op.asset_operation.create
                asset.resource_name = asset_name
                asset.name = stable_name
                asset.type_ = client.enums.AssetTypeEnum.IMAGE
                asset.image_asset.data = (settings.storage_root / item["storage_key"]).read_bytes()
                operations.append(asset_op)
            image_assets.append((asset_name, item))
        logo_media_id = str(campaign.get("logo_media_id") or "")
        logo_asset = next(
            (
                item
                for item in image_assets
                if str(item[1].get("id") or "") == logo_media_id
            ),
            None,
        )

        youtube_id = str(campaign.get("youtube_video_id") or "")
        if not youtube_id:
            youtube_id = next(
                (str(item.get("youtube_video_id")) for item in selected_media if item.get("youtube_video_id")), ""
            )
        video_asset_name: str | None = None
        if youtube_id:
            stable_name = f"DGU YouTube {youtube_id}"
            video_asset_name = self._find_existing_asset(client, customer_id, stable_name) if service else None
            if not video_asset_name:
                video_asset_name = client.get_service("AssetService").asset_path(customer_id, next_temp_id)
                next_temp_id -= 1
                asset_op = client.get_type("MutateOperation")
                asset = asset_op.asset_operation.create
                asset.resource_name = video_asset_name
                asset.name = stable_name
                asset.type_ = client.enums.AssetTypeEnum.YOUTUBE_VIDEO
                asset.youtube_video_asset.youtube_video_id = youtube_id
                operations.append(asset_op)

        ad_op = client.get_type("MutateOperation")
        ad_group_ad = ad_op.ad_group_ad_operation.create
        ad_group_ad.ad_group = ad_group_name
        ad_group_ad.status = client.enums.AdGroupAdStatusEnum.ENABLED
        ad = ad_group_ad.ad
        ad.name = f"{campaign['google_campaign_name']} ad"[:255]
        ad.final_urls.append(campaign["final_url"])
        if campaign.get("mobile_final_url"):
            ad.final_mobile_urls.append(campaign["mobile_final_url"])
        if campaign.get("tracking_template"):
            ad.tracking_url_template = campaign["tracking_template"]
        if campaign.get("final_url_suffix"):
            ad.final_url_suffix = campaign["final_url_suffix"]
        _append_custom_parameters(client, ad.url_custom_parameters, campaign.get("custom_parameters") or [])
        if campaign.get("ad_type") == "VIDEO":
            info = ad.demand_gen_video_responsive_ad
            info.business_name.text = campaign["business_name"]
            if video_asset_name:
                video_link = client.get_type("AdVideoAsset")
                video_link.asset = video_asset_name
                info.videos.append(video_link)
            square_assets = [item for item in image_assets if _image_role(item[1]) == "SQUARE"]
            companion_assets = [item for item in image_assets if _image_role(item[1]) == "LANDSCAPE"]
            for asset_name, _item in ([logo_asset] if logo_asset else square_assets[:1]):
                image_link = client.get_type("AdImageAsset")
                image_link.asset = asset_name
                info.logo_images.append(image_link)
            for asset_name, _item in companion_assets[:1]:
                image_link = client.get_type("AdImageAsset")
                image_link.asset = asset_name
                info.companion_banners.append(image_link)
            _append_text_assets(client, info.headlines, campaign.get("headlines") or [])
            _append_text_assets(client, info.long_headlines, [campaign["long_headline"]])
            _append_text_assets(client, info.descriptions, campaign.get("descriptions") or [])
            cta_asset_name = client.get_service("AssetService").asset_path(customer_id, next_temp_id)
            cta_op = client.get_type("MutateOperation")
            cta_asset = cta_op.asset_operation.create
            cta_asset.resource_name = cta_asset_name
            cta_asset.name = f"DGU CTA {campaign.get('call_to_action') or 'LEARN_MORE'}"
            cta_asset.type_ = client.enums.AssetTypeEnum.CALL_TO_ACTION
            cta_asset.call_to_action_asset.call_to_action = getattr(
                client.enums.CallToActionTypeEnum,
                str(campaign.get("call_to_action") or "LEARN_MORE").upper(),
            )
            operations.append(cta_op)
            cta_link = client.get_type("AdCallToActionAsset")
            cta_link.asset = cta_asset_name
            info.call_to_actions.append(cta_link)
            paths = [item for item in str(campaign.get("display_path") or "").split("/") if item]
            if paths:
                info.breadcrumb1 = paths[0][:15]
            if len(paths) > 1:
                info.breadcrumb2 = paths[1][:15]
        elif campaign.get("ad_type") == "CAROUSEL":
            logo_asset = logo_asset or next(
                (item for item in image_assets if _image_role(item[1]) == "SQUARE"),
                image_assets[0],
            )
            info = ad.demand_gen_carousel_ad
            info.business_name = campaign["business_name"]
            info.call_to_action_text = campaign.get("call_to_action") or "LEARN_MORE"
            info.logo_image.asset = logo_asset[0]
            info.headline.text = str((campaign.get("headlines") or [""])[0])
            info.description.text = str((campaign.get("descriptions") or [""])[0])
            card_headlines = campaign.get("carousel_card_headlines") or campaign.get("headlines") or []
            for index, (asset_name, item) in enumerate([row for row in image_assets if row != logo_asset][:10]):
                card_name = client.get_service("AssetService").asset_path(customer_id, next_temp_id)
                next_temp_id -= 1
                card_op = client.get_type("MutateOperation")
                card = card_op.asset_operation.create
                card.resource_name = card_name
                card.name = f"DGU card {campaign['deployment_key'][:12]} {index + 1}"
                card.type_ = client.enums.AssetTypeEnum.DEMAND_GEN_CAROUSEL_CARD
                if _image_role(item) == "SQUARE":
                    card.demand_gen_carousel_card_asset.square_marketing_image_asset = asset_name
                else:
                    card.demand_gen_carousel_card_asset.marketing_image_asset = asset_name
                card.demand_gen_carousel_card_asset.headline = str(
                    card_headlines[index % len(card_headlines)] if card_headlines else campaign["business_name"]
                )[:40]
                card.demand_gen_carousel_card_asset.call_to_action_text = campaign.get("call_to_action") or "LEARN_MORE"
                card.final_urls.append(campaign["final_url"])
                operations.append(card_op)
                card_link = client.get_type("AdDemandGenCarouselCardAsset")
                card_link.asset = card_name
                info.carousel_cards.append(card_link)
        else:
            info = ad.demand_gen_multi_asset_ad
            info.business_name = campaign["business_name"]
            info.call_to_action_text = campaign.get("call_to_action") or "LEARN_MORE"
            _append_text_assets(client, info.headlines, campaign.get("headlines") or [])
            _append_text_assets(client, info.descriptions, campaign.get("descriptions") or [])
            if logo_asset:
                logo_link = client.get_type("AdImageAsset")
                logo_link.asset = logo_asset[0]
                info.logo_images.append(logo_link)
            for asset_name, item in image_assets:
                link = client.get_type("AdImageAsset")
                link.asset = asset_name
                ratio = (item.get("width") or 0) / max(item.get("height") or 1, 1)
                if abs(ratio - 1.0) < 0.08:
                    info.square_marketing_images.append(link)
                elif abs(ratio - 0.8) < 0.08:
                    info.portrait_marketing_images.append(link)
                elif str(item.get("suggested_role") or "").upper() == "CLASSIC_DISPLAY":
                    info.classic_display_images.append(link)
                else:
                    info.marketing_images.append(link)
        operations.append(ad_op)
        return operations

    def start_youtube_video_upload(
        self, customer_id: str, file_path: str, title: str, description: str
    ) -> YouTubeUploadResult:
        self._require_google_test_mutate()
        with google_ads_client(self.config) as client:
            service = client.get_service("YouTubeVideoUploadService")
            request = client.get_type("CreateYouTubeVideoUploadRequest")
            request.customer_id = customer_id
            request.you_tube_video_upload.video_title = title
            request.you_tube_video_upload.video_description = description
            request.you_tube_video_upload.video_privacy = client.enums.YouTubeVideoPrivacyEnum.UNLISTED
            with Path(file_path).open("rb") as stream:
                response = service.create_you_tube_video_upload(stream=stream, request=request, retry=None)
            return YouTubeUploadResult(
                state="PENDING",
                resource_name=response.resource_name,
                video_id=None,
                message="Видео передано в Google Ads и ожидает обработки YouTube",
            )

    def get_youtube_video_upload(self, customer_id: str, resource_name: str) -> YouTubeUploadResult:
        escaped = resource_name.replace("'", "\\'")
        query = f"""
            SELECT you_tube_video_upload.resource_name,
                   you_tube_video_upload.video_id,
                   you_tube_video_upload.state
            FROM you_tube_video_upload
            WHERE you_tube_video_upload.resource_name = '{escaped}'
        """
        with google_ads_client(self.config) as client:
            service = client.get_service("GoogleAdsService")
            for batch in service.search_stream(customer_id=customer_id, query=query):
                for row in batch.results:
                    state = getattr(row.you_tube_video_upload.state, "name", None) or str(
                        row.you_tube_video_upload.state
                    )
                    return YouTubeUploadResult(
                        state=state,
                        resource_name=row.you_tube_video_upload.resource_name,
                        video_id=row.you_tube_video_upload.video_id or None,
                        message=f"Состояние YouTube upload: {state}",
                    )
        return YouTubeUploadResult(
            state="UNAVAILABLE",
            resource_name=resource_name,
            video_id=None,
            message="Google Ads не вернул ресурс загрузки",
        )


def _append_text_assets(client: Any, target: Any, values: list[str]) -> None:
    for value in values:
        item = client.get_type("AdTextAsset")
        item.text = value
        target.append(item)


def _append_custom_parameters(client: Any, target: Any, values: list[dict]) -> None:
    for value in values:
        key = str(value.get("key") or "").strip()
        parameter_value = str(value.get("value") or "").strip()
        if not key:
            continue
        item = client.get_type("CustomParameter")
        item.key = key
        item.value = parameter_value
        target.append(item)


def _set_bidding(client: Any, target: Any, campaign: dict) -> None:
    strategy = str(campaign.get("bidding_strategy") or "TARGET_CPA").upper()
    target_cpa = int(campaign.get("target_cpa_micros") or 0)
    target_roas = float(campaign.get("target_roas") or 0)
    if target_roas > 10:
        target_roas /= 100
    if strategy == "TARGET_CPA":
        target.bidding_strategy_type = client.enums.BiddingStrategyTypeEnum.TARGET_CPA
        target.target_cpa.target_cpa_micros = target_cpa
    elif strategy == "MAXIMIZE_CONVERSIONS":
        target.bidding_strategy_type = client.enums.BiddingStrategyTypeEnum.MAXIMIZE_CONVERSIONS
        target.maximize_conversions = client.get_type("MaximizeConversions")
        if target_cpa:
            target.maximize_conversions.target_cpa_micros = target_cpa
    elif strategy == "TARGET_ROAS":
        target.bidding_strategy_type = client.enums.BiddingStrategyTypeEnum.TARGET_ROAS
        target.target_roas.target_roas = target_roas
    elif strategy == "MAXIMIZE_CLICKS":
        target.bidding_strategy_type = client.enums.BiddingStrategyTypeEnum.TARGET_SPEND
        target.target_spend = client.get_type("TargetSpend")
        ceiling = int(campaign.get("cpc_bid_ceiling_micros") or 0)
        if ceiling:
            target.target_spend.cpc_bid_ceiling_micros = ceiling
    else:
        raise ValueError(f"Стратегия ставок {strategy} недоступна для Demand Gen")


def _configure_channel_controls(client: Any, ad_group: Any, config: dict) -> None:
    mode = str(config.get("mode") or "ALL_CHANNELS").upper()
    controls = ad_group.demand_gen_ad_group_settings.channel_controls
    if mode == "ALL_CHANNELS":
        controls.channel_strategy = client.enums.DemandGenChannelStrategyEnum.ALL_CHANNELS
        return
    if mode in {"GOOGLE_OWNED", "ALL_OWNED_AND_OPERATED_CHANNELS"}:
        controls.channel_strategy = client.enums.DemandGenChannelStrategyEnum.ALL_OWNED_AND_OPERATED_CHANNELS
        return
    if mode not in {"MANUAL", "SELECTED_CHANNELS"}:
        raise ValueError(f"Неизвестный режим channel controls: {mode}")
    selected = config.get("selected") or config.get("selected_channels") or {}
    if selected.get("maps") and "maps" not in controls.selected_channels._meta.fields:
        raise ValueError("Google Maps отсутствует в protobuf-схеме установленного Google Ads Python client")
    supported = ("youtube_in_stream", "youtube_in_feed", "youtube_shorts", "discover", "gmail", "display", "maps")
    enabled = 0
    for field in supported:
        if field not in controls.selected_channels._meta.fields:
            continue
        value = bool(selected.get(field, False))
        setattr(controls.selected_channels, field, value)
        enabled += int(value)
    if not enabled:
        raise ValueError("При ручном выборе каналов нужно включить хотя бы один канал")


def _criterion_operation(
    client: Any,
    ad_group_name: str,
    field_path: str,
    value: object,
    *,
    negative: bool = False,
) -> Any:
    operation = client.get_type("MutateOperation")
    criterion = operation.ad_group_criterion_operation.create
    criterion.ad_group = ad_group_name
    criterion.negative = negative
    target = criterion
    parts = field_path.split(".")
    for part in parts[:-1]:
        target = getattr(target, part)
    setattr(target, parts[-1], value)
    return operation


def _append_demographic_operations(
    client: Any,
    operations: list[Any],
    ad_group_name: str,
    demographics: dict,
) -> None:
    fields = {
        "age_ranges": ("age_range.type_", client.enums.AgeRangeTypeEnum),
        "genders": ("gender.type_", client.enums.GenderTypeEnum),
        "parental_statuses": ("parental_status.type_", client.enums.ParentalStatusTypeEnum),
        "income_ranges": ("income_range.type_", client.enums.IncomeRangeTypeEnum),
    }
    for key, (field_path, enum_type) in fields.items():
        for value in demographics.get(key) or []:
            operations.append(
                _criterion_operation(client, ad_group_name, field_path, getattr(enum_type, str(value).upper()))
            )
        for value in demographics.get(f"excluded_{key}") or []:
            operations.append(
                _criterion_operation(
                    client,
                    ad_group_name,
                    field_path,
                    getattr(enum_type, str(value).upper()),
                    negative=True,
                )
            )


def _append_schedule_operations(
    client: Any,
    operations: list[Any],
    campaign_name: str,
    schedule: list[dict],
) -> None:
    for item in schedule:
        operation = client.get_type("MutateOperation")
        criterion = operation.campaign_criterion_operation.create
        criterion.campaign = campaign_name
        criterion.ad_schedule.day_of_week = getattr(
            client.enums.DayOfWeekEnum,
            str(item.get("day_of_week") or "MONDAY").upper(),
        )
        criterion.ad_schedule.start_hour = int(item.get("start_hour", 0))
        criterion.ad_schedule.start_minute = getattr(
            client.enums.MinuteOfHourEnum,
            str(item.get("start_minute") or "ZERO").upper(),
        )
        criterion.ad_schedule.end_hour = int(item.get("end_hour", 24))
        criterion.ad_schedule.end_minute = getattr(
            client.enums.MinuteOfHourEnum,
            str(item.get("end_minute") or "ZERO").upper(),
        )
        operations.append(operation)


def _google_date_time(value: object) -> str:
    text = str(value).strip()
    if len(text) == 17 and text[8] == " " and text[11] == ":":
        return text
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return parsed.strftime("%Y%m%d %H:%M:%S")


def _image_role(item: dict) -> str:
    ratio = (item.get("width") or 0) / max(item.get("height") or 1, 1)
    if abs(ratio - 1.0) < 0.08:
        return "SQUARE"
    if abs(ratio - 0.8) < 0.08:
        return "PORTRAIT"
    return "LANDSCAPE"


def _escape_gaql(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("'", "\\'")


def _gaql_date(value: object) -> str:
    normalized = str(value).strip().replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).date().isoformat()


def asset_cache_key(customer_id: str, sha256: str) -> tuple[str, str]:
    return ("".join(character for character in customer_id if character.isdigit()), sha256.lower())


def _enum_name(value: object) -> str:
    return getattr(value, "name", None) or str(value)


def _optional_int(message: object, field: str) -> int | None:
    protobuf = getattr(message, "_pb", None)
    if protobuf is not None and hasattr(protobuf, "HasField"):
        try:
            if not protobuf.HasField(field):
                return None
        except ValueError:
            pass
    value = getattr(message, field, None)
    return int(value) if value is not None else None


def _normalized_conversion_actions(
    conversion_actions: dict[str, list[str]] | None,
) -> dict[str, set[str]]:
    registration = {
        str(item)
        for item in (conversion_actions or {}).get("REGISTRATION", [])
        if item
    }
    deposit = {
        str(item)
        for item in (conversion_actions or {}).get("DEPOSIT", [])
        if item
    }
    return {
        "REGISTRATION": registration,
        "DEPOSIT": deposit,
        "ALL": registration | deposit,
    }


def _empty_metric_day(mapped_actions: dict[str, set[str]]) -> dict:
    return {
        "impressions": 0,
        "clicks": 0,
        "cost_micros": 0,
        "conversions": 0.0,
        "all_conversions": 0.0,
        "conversion_value": 0.0,
        "registrations": 0.0 if mapped_actions["REGISTRATION"] else None,
        "deposits": 0.0 if mapped_actions["DEPOSIT"] else None,
        "registration_value": 0.0 if mapped_actions["REGISTRATION"] else None,
        "deposit_value": 0.0 if mapped_actions["DEPOSIT"] else None,
        "registration_data_available": bool(mapped_actions["REGISTRATION"]),
        "deposit_data_available": bool(mapped_actions["DEPOSIT"]),
    }


def _customer_id_from_resource(resource_name: str) -> str | None:
    parts = resource_name.split("/")
    return parts[1] if len(parts) > 1 and parts[0] == "customers" else None


def _protobuf_payload(message: object) -> dict:
    try:
        from google.protobuf.json_format import MessageToDict

        protobuf_message = getattr(message, "_pb", message)
        return MessageToDict(
            protobuf_message,
            preserving_proto_field_name=True,
            use_integers_for_enums=False,
        )
    except (AttributeError, ImportError, TypeError, ValueError):
        return {}


def _policy_topics(entries: object) -> list[dict]:
    return [_protobuf_payload(entry) for entry in entries or []]


def _change_type(change_event: object) -> str:
    operation = _enum_name(
        getattr(change_event, "resource_change_operation", "UNKNOWN")
    )
    operation_names = {
        "CREATE": "CREATED",
        "UPDATE": "UPDATED",
        "REMOVE": "REMOVED",
    }
    if operation in operation_names:
        return operation_names[operation]

    old_resource = _protobuf_payload(getattr(change_event, "old_resource", None))
    new_resource = _protobuf_payload(getattr(change_event, "new_resource", None))
    if old_resource and new_resource:
        return "UPDATED"
    if new_resource:
        return "CREATED"
    if old_resource:
        return "REMOVED"
    return "UNKNOWN"


def _resource_readback_row(kind: str, row: Any) -> dict:
    if kind == "campaigns":
        return {
            "resource_name": str(row.campaign.resource_name),
            "id": str(row.campaign.id),
            "name": row.campaign.name,
            "status": _enum_name(row.campaign.status),
            "channel_type": _enum_name(row.campaign.advertising_channel_type),
            "budget_resource_name": str(row.campaign.campaign_budget),
            "budget_id": str(row.campaign_budget.id),
            "budget_micros": int(row.campaign_budget.amount_micros),
            "budget_shared": bool(row.campaign_budget.explicitly_shared),
        }
    if kind == "ad_groups":
        return {
            "resource_name": str(row.ad_group.resource_name),
            "id": str(row.ad_group.id),
            "name": row.ad_group.name,
            "status": _enum_name(row.ad_group.status),
            "campaign": str(row.ad_group.campaign),
        }
    if kind == "ads":
        return {
            "resource_name": str(row.ad_group_ad.resource_name),
            "status": _enum_name(row.ad_group_ad.status),
            "ad_resource_name": str(row.ad_group_ad.ad.resource_name),
            "ad_id": str(row.ad_group_ad.ad.id),
            "name": row.ad_group_ad.ad.name,
            "type": _enum_name(row.ad_group_ad.ad.type_),
            "final_urls": [str(item) for item in row.ad_group_ad.ad.final_urls],
        }
    if kind == "campaign_criteria":
        return {
            "resource_name": str(row.campaign_criterion.resource_name),
            "criterion_id": str(row.campaign_criterion.criterion_id),
            "type": _enum_name(row.campaign_criterion.type_),
            "negative": bool(row.campaign_criterion.negative),
        }
    if kind == "ad_group_criteria":
        return {
            "resource_name": str(row.ad_group_criterion.resource_name),
            "criterion_id": str(row.ad_group_criterion.criterion_id),
            "type": _enum_name(row.ad_group_criterion.type_),
            "negative": bool(row.ad_group_criterion.negative),
            "audience": str(row.ad_group_criterion.audience.audience or ""),
        }
    if kind == "assets":
        return {
            "resource_name": str(row.asset.resource_name),
            "id": str(row.asset.id),
            "name": row.asset.name,
            "type": _enum_name(row.asset.type_),
        }
    if kind == "audiences":
        return {
            "resource_name": str(row.audience.resource_name),
            "id": str(row.audience.id),
            "name": row.audience.name,
            "status": _enum_name(row.audience.status),
        }
    raise ValueError(f"Неподдерживаемый тип readback: {kind}")


def _resource_names(response: Any) -> list[str]:
    names: list[str] = []
    result_fields = (
        "campaign_budget_result",
        "campaign_result",
        "ad_group_result",
        "ad_group_criterion_result",
        "audience_result",
        "asset_result",
        "ad_group_ad_result",
    )
    for operation_response in response.mutate_operation_responses:
        for field in result_fields:
            result = getattr(operation_response, field, None)
            resource_name = getattr(result, "resource_name", "") if result is not None else ""
            if resource_name:
                names.append(str(resource_name))
                break
    return names


def _google_exception(exc: Exception, customer_id: str, campaign_name: str | None) -> tuple[list[dict], str | None]:
    try:
        from google.ads.googleads.errors import GoogleAdsException
    except ImportError:  # pragma: no cover
        GoogleAdsException = ()  # type: ignore[assignment,misc]
    if isinstance(exc, GoogleAdsException):
        issues = []
        for error in exc.failure.errors:
            issues.append(
                {
                    "customer_id": customer_id,
                    "campaign_name": campaign_name,
                    "code": _google_error_code(error),
                    "message": error.message,
                    "field_path": str(error.location) if error.location else None,
                }
            )
        return issues, exc.request_id
    return (
        [
            {
                "customer_id": customer_id,
                "campaign_name": campaign_name,
                "code": exc.__class__.__name__,
                "message": str(exc),
            }
        ],
        None,
    )


def _google_error_code(error: Any) -> str:
    error_code = error.error_code
    protobuf = getattr(error_code, "_pb", None)
    field_name = protobuf.WhichOneof("error_code") if protobuf is not None else None
    if field_name:
        field = protobuf.DESCRIPTOR.fields_by_name.get(field_name)
        number = getattr(protobuf, field_name)
        enum_value = field.enum_type.values_by_number.get(number) if field and field.enum_type else None
        value_name = enum_value.name if enum_value else _enum_name(getattr(error_code, field_name))
        return f"{field_name.upper()}.{value_name}"
    return str(error_code).strip() or "GOOGLE_ADS_ERROR"


def _connection_check_failure(exc: Exception, customer_id: str, api_version: str) -> AdapterCheckResult:
    message, request_id = _google_ads_failure_message(
        exc,
        customer_id,
        f"Проверка MCC {customer_id} не пройдена",
    )
    return AdapterCheckResult(
        ok=False,
        status="ERROR",
        message=message,
        api_version=api_version,
        request_id=request_id,
    )


def _google_ads_failure_message(exc: Exception, customer_id: str, prefix: str) -> tuple[str, str | None]:
    issues, request_id = _google_exception(exc, customer_id, None)
    codes = sorted({str(issue.get("code") or "GOOGLE_ADS_ERROR") for issue in issues})
    messages = [str(issue.get("message") or "").strip() for issue in issues]
    google_message = "; ".join(message for message in messages if message) or str(exc)
    explanation = _connection_error_explanation(codes)
    request_part = f" Request ID: {request_id}." if request_id else ""
    return (
        (
            f"{prefix}. Код Google Ads: {', '.join(codes)}. {explanation} "
            f"Сообщение Google: {google_message}.{request_part}"
        ),
        request_id,
    )


def _connection_error_explanation(codes: list[str]) -> str:
    joined = " ".join(codes)
    if "USER_PERMISSION_DENIED" in joined:
        return "Пользователь OAuth не имеет доступа к этому MCC или указан неверный login customer ID."
    if "DEVELOPER_TOKEN_INVALID" in joined:
        return "Сохранённый Developer Token отклонён Google как недействительный."
    if "DEVELOPER_TOKEN_NOT_APPROVED" in joined:
        return "Developer Token не имеет уровня доступа, необходимого для этого аккаунта."
    if "CUSTOMER_NOT_ENABLED" in joined:
        return "Указанный аккаунт Google Ads не активирован."
    if "AUTHENTICATION_ERROR" in joined or "OAUTH_TOKEN_HEADER_INVALID" in joined:
        return "Google отклонил сохранённые OAuth-реквизиты."
    return "Google Ads отклонил безопасный запрос чтения; код и Request ID указаны для диагностики."
