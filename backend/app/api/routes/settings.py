from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_csrf, require_role
from app.api.routes.batches import DEFAULT_GUARDRAILS
from app.api.workflow_schemas import GuardrailsPatchIn
from app.core.database import get_db
from app.db.models import ApplicationSetting, User, UserRole
from app.domain.audit import record_audit
from app.domain.batch_generator import deep_merge

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/campaign-builder-guardrails")
def get_campaign_builder_guardrails(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR, UserRole.VIEWER)),
) -> dict:
    item = db.scalar(select(ApplicationSetting).where(ApplicationSetting.key == "campaign_builder_guardrails"))
    value = deep_merge(DEFAULT_GUARDRAILS, item.value if item else {})
    value.pop("automatic_evaluation_actions_enabled", None)
    return value


@router.patch("/campaign-builder-guardrails")
def update_campaign_builder_guardrails(
    payload: GuardrailsPatchIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
    _: User = Depends(require_csrf),
) -> dict:
    value = payload.model_dump()
    value["max_budget_by_currency"] = {
        str(currency).upper(): float(amount)
        for currency, amount in value["max_budget_by_currency"].items()
        if float(amount) >= 0
    }
    item = db.scalar(select(ApplicationSetting).where(ApplicationSetting.key == "campaign_builder_guardrails"))
    if not item:
        item = ApplicationSetting(key="campaign_builder_guardrails", value=value, updated_by_id=user.id)
        db.add(item)
    else:
        item.value = value
        item.updated_by_id = user.id
    record_audit(
        db,
        request,
        user,
        "settings.campaign_builder_guardrails.update",
        "application_setting",
        "campaign_builder_guardrails",
        value,
    )
    db.commit()
    return value
