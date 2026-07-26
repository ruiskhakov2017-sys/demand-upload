from __future__ import annotations

from copy import deepcopy

from sqlalchemy import select

from app.core.config import settings
from app.db.models import CampaignInstance, CampaignUpload, LaunchBatch
from app.domain_validation.service import (
    DomainValidationService,
    extract_final_url_references,
    snapshot_url_references,
)


def collect_upload_references(db, upload: CampaignUpload) -> list[dict]:
    references = [
        *extract_final_url_references(upload.source_rows or [], source="import"),
        *extract_final_url_references(upload.draft or {}, source="draft"),
    ]
    instances = []
    if hasattr(db, "scalars"):
        instances = db.scalars(
            select(CampaignInstance)
            .join(LaunchBatch, CampaignInstance.launch_batch_id == LaunchBatch.id)
            .where(LaunchBatch.upload_id == upload.id, CampaignInstance.included.is_(True))
        ).all()
    for instance in instances:
        value = (instance.url_settings or {}).get("final_url")
        if value:
            references.append(
                {
                    "url": str(value),
                    "source": "campaign_instance",
                    "path": "url_settings.final_url",
                    "campaign_instance_id": str(instance.id),
                    "campaign_name": instance.campaign_name,
                }
            )
    return references


def mark_upload_validation_pending(db, upload: CampaignUpload) -> dict:
    draft = deepcopy(upload.draft or {})
    previous = draft.get("domain_validation") or {}
    report = DomainValidationService.pending(collect_upload_references(db, upload), previous)
    draft["domain_validation"] = report
    upload.draft = draft
    return report


def validate_upload(
    db,
    upload: CampaignUpload,
    *,
    force: bool,
    service: DomainValidationService | None = None,
) -> dict:
    draft = deepcopy(upload.draft or {})
    checker = service or DomainValidationService()
    report = checker.validate(
        collect_upload_references(db, upload),
        cached_report=draft.get("domain_validation") or {},
        force=force,
    )
    draft["domain_validation"] = report
    upload.draft = draft
    return report


def validate_snapshot(
    snapshot: dict,
    *,
    cached_report: dict | None,
    force: bool,
    service: DomainValidationService | None = None,
) -> dict:
    checker = service or DomainValidationService()
    return checker.validate(
        snapshot_url_references(snapshot),
        cached_report=cached_report,
        force=force,
    )


def enqueue_upload_validation(upload_id) -> bool:
    if settings.app_env.lower() == "test":
        return False
    try:
        from app.jobs.tasks import validate_upload_domains

        validate_upload_domains.delay(str(upload_id))
        return True
    except Exception:
        return False
