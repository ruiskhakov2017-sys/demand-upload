from copy import deepcopy
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_csrf
from app.api.workflow_schemas import (
    TemplateCopyIn,
    TemplateCreateIn,
    TemplateFromCampaignIn,
    TemplateOut,
    TemplateVersionCreateIn,
    TemplateVersionOut,
)
from app.core.database import get_db
from app.db.models import CampaignTemplate, CampaignTemplateVersion, GoogleConnection, User
from app.domain.audit import record_audit
from app.google_ads.service import build_google_ads_adapter, is_google_connection_active

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[TemplateOut])
def list_templates(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[CampaignTemplate]:
    return list(
        db.scalars(
            select(CampaignTemplate)
            .where(CampaignTemplate.is_active.is_(True))
            .order_by(desc(CampaignTemplate.updated_at))
        ).all()
    )


@router.post("", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: TemplateCreateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> CampaignTemplate:
    if db.scalar(select(CampaignTemplate).where(CampaignTemplate.name == payload.name)):
        raise HTTPException(status_code=409, detail="Шаблон с таким названием уже существует")
    item = CampaignTemplate(**payload.model_dump(), created_by_id=user.id)
    db.add(item)
    db.flush()
    if not item.semantic_key:
        item.semantic_key = f"template:{item.id}"
    db.add(
        CampaignTemplateVersion(
            template_id=item.id,
            version_number=1,
            payload=deepcopy(item.payload),
            change_summary="Первая версия",
            created_by_id=user.id,
        )
    )
    record_audit(db, request, user, "template.create", "campaign_template", str(item.id), {"name": item.name})
    db.commit()
    db.refresh(item)
    return item


@router.post("/from-google", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
def create_template_from_google(
    payload: TemplateFromCampaignIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> CampaignTemplate:
    if db.scalar(select(CampaignTemplate).where(CampaignTemplate.name == payload.name)):
        raise HTTPException(status_code=409, detail="Шаблон с таким названием уже существует")
    connection = db.get(GoogleConnection, payload.connection_id)
    if not is_google_connection_active(connection):
        raise HTTPException(status_code=409, detail="Google connection недоступен")
    source = build_google_ads_adapter(db, connection).read_campaign(
        "".join(ch for ch in payload.customer_id if ch.isdigit()),
        payload.campaign_resource_name,
    )
    item = CampaignTemplate(
        name=payload.name,
        description=payload.description,
        semantic_key=payload.semantic_key,
        payload=deepcopy(source["template"]),
        current_version=1,
        created_by_id=user.id,
    )
    db.add(item)
    db.flush()
    if not item.semantic_key:
        item.semantic_key = f"template:{item.id}"
    version = CampaignTemplateVersion(
        template_id=item.id,
        version_number=1,
        payload=deepcopy(item.payload),
        change_summary=f"Создано из Google Ads: {source.get('source_campaign_name') or payload.campaign_resource_name}",
        source_campaign_resource=payload.campaign_resource_name,
        created_by_id=user.id,
    )
    db.add(version)
    record_audit(
        db,
        request,
        user,
        "template.create_from_google",
        "campaign_template",
        str(item.id),
        {
            "customer_id": payload.customer_id,
            "campaign_resource_name": payload.campaign_resource_name,
            "google_contacted": True,
        },
    )
    db.commit()
    db.refresh(item)
    return item


@router.get("/{template_id}/versions", response_model=list[TemplateVersionOut])
def list_template_versions(
    template_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CampaignTemplateVersion]:
    _get_template(db, template_id)
    return list(
        db.scalars(
            select(CampaignTemplateVersion)
            .where(CampaignTemplateVersion.template_id == template_id)
            .order_by(desc(CampaignTemplateVersion.version_number))
        ).all()
    )


@router.post("/{template_id}/versions", response_model=TemplateVersionOut, status_code=status.HTTP_201_CREATED)
def create_template_version(
    template_id: UUID,
    payload: TemplateVersionCreateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> CampaignTemplateVersion:
    template = _get_template(db, template_id)
    latest = db.scalar(
        select(func.max(CampaignTemplateVersion.version_number)).where(
            CampaignTemplateVersion.template_id == template.id
        )
    ) or 0
    item = CampaignTemplateVersion(
        template_id=template.id,
        version_number=latest + 1,
        payload=deepcopy(payload.payload),
        change_summary=payload.change_summary,
        created_by_id=user.id,
    )
    db.add(item)
    template.current_version = item.version_number
    template.payload = deepcopy(payload.payload)
    db.flush()
    record_audit(
        db,
        request,
        user,
        "template.version.create",
        "campaign_template_version",
        str(item.id),
        {"template_id": str(template.id), "version_number": item.version_number},
    )
    db.commit()
    db.refresh(item)
    return item


@router.post("/{template_id}/copy", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
def copy_template(
    template_id: UUID,
    payload: TemplateCopyIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> CampaignTemplate:
    source = _get_template(db, template_id)
    if db.scalar(select(CampaignTemplate).where(CampaignTemplate.name == payload.name)):
        raise HTTPException(status_code=409, detail="Шаблон с таким названием уже существует")
    item = CampaignTemplate(
        name=payload.name,
        description=payload.description if payload.description is not None else source.description,
        semantic_key=payload.semantic_key,
        payload=deepcopy(source.payload),
        current_version=1,
        created_by_id=user.id,
    )
    db.add(item)
    db.flush()
    if not item.semantic_key:
        item.semantic_key = f"template:{item.id}"
    db.add(
        CampaignTemplateVersion(
            template_id=item.id,
            version_number=1,
            payload=deepcopy(item.payload),
            change_summary=f"Копия шаблона {source.name}",
            created_by_id=user.id,
        )
    )
    record_audit(
        db,
        request,
        user,
        "template.copy",
        "campaign_template",
        str(item.id),
        {"source_template_id": str(source.id)},
    )
    db.commit()
    db.refresh(item)
    return item


@router.get("/{template_id}/compare")
def compare_template_versions(
    template_id: UUID,
    from_version: int = Query(ge=1),
    to_version: int = Query(ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    _get_template(db, template_id)
    versions = list(
        db.scalars(
            select(CampaignTemplateVersion).where(
                CampaignTemplateVersion.template_id == template_id,
                CampaignTemplateVersion.version_number.in_([from_version, to_version]),
            )
        ).all()
    )
    by_number = {item.version_number: item for item in versions}
    if from_version not in by_number or to_version not in by_number:
        raise HTTPException(status_code=404, detail="Одна из версий шаблона не найдена")
    return {
        "template_id": str(template_id),
        "from_version": from_version,
        "to_version": to_version,
        "changes": _diff_payload(by_number[from_version].payload, by_number[to_version].payload),
    }


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> None:
    item = _get_template(db, template_id)
    item.is_active = False
    record_audit(db, request, user, "template.archive", "campaign_template", str(item.id))
    db.commit()


def _get_template(db: Session, template_id: UUID) -> CampaignTemplate:
    item = db.get(CampaignTemplate, template_id)
    if not item:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    return item


def _diff_payload(before: object, after: object, path: str = "") -> list[dict]:
    if isinstance(before, dict) and isinstance(after, dict):
        changes: list[dict] = []
        for key in sorted(set(before) | set(after)):
            child_path = f"{path}.{key}" if path else key
            if key not in before:
                changes.append({"path": child_path, "change": "ADDED", "before": None, "after": after[key]})
            elif key not in after:
                changes.append({"path": child_path, "change": "REMOVED", "before": before[key], "after": None})
            else:
                changes.extend(_diff_payload(before[key], after[key], child_path))
        return changes
    if before != after:
        return [{"path": path, "change": "CHANGED", "before": before, "after": after}]
    return []
