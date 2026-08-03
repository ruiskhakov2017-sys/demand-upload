from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_csrf
from app.api.workflow_schemas import ImportOut, ManualRowsIn, UploadCreateIn, UploadOut, UploadPatchIn
from app.core.config import settings
from app.core.database import get_db
from app.db.models import CampaignUpload, Job, JobEvent, JobStatus, UploadStatus, User
from app.domain.audit import record_audit
from app.domain.tabular import parse_tabular
from app.domain_validation.persistence import (
    collect_upload_references,
    enqueue_upload_validation,
    mark_upload_validation_pending,
)
from app.domain_validation.service import DomainValidationService

router = APIRouter(prefix="/uploads", tags=["uploads"])
MAX_IMPORT_BYTES = 20 * 1024 * 1024


@router.get("", response_model=list[UploadOut])
def list_uploads(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[CampaignUpload]:
    return list(db.scalars(select(CampaignUpload).order_by(desc(CampaignUpload.updated_at)).limit(200)).all())


@router.post("", response_model=UploadOut, status_code=status.HTTP_201_CREATED)
def create_upload(
    payload: UploadCreateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> CampaignUpload:
    upload = CampaignUpload(
        name=payload.name,
        status=UploadStatus.DRAFT.value,
        source_type="MANUAL",
        source_rows=[],
        draft={"execution_mode": payload.execution_mode, "campaign": {}},
        current_step=0,
        created_by_id=user.id,
    )
    db.add(upload)
    db.flush()
    record_audit(db, request, user, "upload.create", "campaign_upload", str(upload.id), {"name": upload.name})
    db.commit()
    db.refresh(upload)
    return upload


@router.get("/{upload_id}", response_model=UploadOut)
def get_upload(
    upload_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> CampaignUpload:
    return _get_upload(db, upload_id)


@router.patch("/{upload_id}", response_model=UploadOut)
def update_upload(
    upload_id: UUID,
    payload: UploadPatchIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> CampaignUpload:
    upload = _get_upload(db, upload_id)
    changed = payload.model_fields_set
    material_changed = False
    if "name" in changed and payload.name is not None:
        material_changed = material_changed or upload.name != payload.name
        upload.name = payload.name
    if "connection_id" in changed:
        material_changed = material_changed or upload.connection_id != payload.connection_id
        upload.connection_id = payload.connection_id
    if "current_step" in changed and payload.current_step is not None:
        upload.current_step = payload.current_step
    if "draft" in changed and payload.draft is not None:
        material_changed = material_changed or upload.draft != payload.draft
        upload.draft = payload.draft
    if material_changed:
        upload.status = UploadStatus.DRAFT.value
        upload.last_error = None
    should_validate = material_changed and "draft" in changed
    if should_validate:
        mark_upload_validation_pending(db, upload)
    record_audit(
        db,
        request,
        user,
        "upload.update",
        "campaign_upload",
        str(upload.id),
        {"fields": sorted(changed)},
    )
    db.commit()
    db.refresh(upload)
    if should_validate:
        enqueue_upload_validation(upload.id)
    return upload


@router.post("/{upload_id}/import", response_model=ImportOut)
async def import_upload_file(
    upload_id: UUID,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> ImportOut:
    upload = _get_upload(db, upload_id)
    content = await file.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="Файл импорта превышает 20 МБ")
    try:
        rows = parse_tabular(file.filename or "import.csv", content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    upload.source_type = "XLSX" if (file.filename or "").lower().endswith((".xlsx", ".xlsm")) else "CSV"
    upload.source_name = file.filename
    upload.source_rows = rows
    upload.status = UploadStatus.DRAFT.value
    mark_upload_validation_pending(db, upload)
    columns = sorted({key for row in rows for key in row})
    record_audit(
        db,
        request,
        user,
        "upload.import",
        "campaign_upload",
        str(upload.id),
        {"filename": file.filename, "rows": len(rows), "columns": columns},
    )
    db.commit()
    db.refresh(upload)
    enqueue_upload_validation(upload.id)
    return ImportOut(upload=UploadOut.model_validate(upload), row_count=len(rows), columns=columns, preview=rows[:10])


@router.post("/{upload_id}/manual-rows", response_model=UploadOut)
def set_manual_rows(
    upload_id: UUID,
    payload: ManualRowsIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> CampaignUpload:
    upload = _get_upload(db, upload_id)
    upload.source_type = "MANUAL"
    upload.source_name = None
    upload.source_rows = payload.rows
    upload.status = UploadStatus.DRAFT.value
    mark_upload_validation_pending(db, upload)
    record_audit(
        db,
        request,
        user,
        "upload.manual_rows",
        "campaign_upload",
        str(upload.id),
        {"rows": len(payload.rows)},
    )
    db.commit()
    db.refresh(upload)
    enqueue_upload_validation(upload.id)
    return upload


@router.get("/{upload_id}/domain-validation")
def get_domain_validation(
    upload_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    upload = _get_upload(db, upload_id)
    report = (upload.draft or {}).get("domain_validation")
    if report:
        return report
    report = DomainValidationService.pending(collect_upload_references(db, upload))
    report["status"] = "NOT_RUN"
    report["checked_at"] = None
    for result in report["results"]:
        result["status"] = "NOT_RUN"
        result["code"] = "DOMAIN_CHECK_NOT_RUN"
    return report


@router.post("/{upload_id}/domain-validation", status_code=status.HTTP_202_ACCEPTED)
def start_domain_validation(
    upload_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> dict:
    return _start_domain_validation(upload_id, request, db, user)


@router.post("/{upload_id}/domain-validation/retry")
def retry_domain_validation(
    upload_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> dict:
    return _start_domain_validation(upload_id, request, db, user)


def _start_domain_validation(
    upload_id: UUID,
    request: Request,
    db: Session,
    user: User,
) -> dict:
    upload = db.scalar(
        select(CampaignUpload)
        .where(CampaignUpload.id == upload_id)
        .with_for_update()
    )
    if not upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Загрузка не найдена")
    active_jobs = list(
        db.scalars(
            select(Job)
            .where(
                Job.type == "DOMAIN_VALIDATION",
                Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
            )
            .order_by(desc(Job.created_at))
        ).all()
    )
    existing = next(
        (
            job
            for job in active_jobs
            if str((job.payload or {}).get("upload_id")) == str(upload.id)
        ),
        None,
    )
    if existing:
        return {
            "job_id": str(existing.id),
            "job_status": existing.status,
            "reused": True,
            "report": (upload.draft or {}).get("domain_validation")
            or DomainValidationService.pending(collect_upload_references(db, upload)),
        }

    report = mark_upload_validation_pending(db, upload)
    job = Job(
        type="DOMAIN_VALIDATION",
        status=JobStatus.QUEUED.value,
        created_by_id=user.id,
        idempotency_key=f"domain-validation:{upload.id}:{uuid4().hex}",
        progress_current=0,
        progress_total=1,
        payload={"upload_id": str(upload.id), "force": True, "source": "USER_REQUEST"},
    )
    db.add(job)
    db.flush()
    db.add(
        JobEvent(
            job_id=job.id,
            level="INFO",
            message="Проверка доменов поставлена в очередь",
            data={"upload_id": str(upload.id)},
        )
    )
    record_audit(
        db,
        request,
        user,
        "upload.domain_validation.start",
        "campaign_upload",
        str(upload.id),
        {
            "urls": report["summary"]["urls"],
            "enforcement": report["enforcement"],
            "job_id": str(job.id),
        },
    )
    db.commit()
    queued = enqueue_upload_validation(upload.id, job_id=job.id, force=True)
    if not queued:
        job = db.get(Job, job.id)
        if job and settings.app_env.lower() != "test":
            job.status = JobStatus.FAILED.value
            job.error_message = "Не удалось поставить проверку доменов в очередь"
            db.add(
                JobEvent(
                    job_id=job.id,
                    level="ERROR",
                    message=job.error_message,
                    data={"code": "QUEUE_UNAVAILABLE"},
                )
            )
            db.commit()
            raise HTTPException(status_code=503, detail=job.error_message)
    return {
        "job_id": str(job.id),
        "job_status": job.status,
        "reused": False,
        "report": report,
    }


def _get_upload(db: Session, upload_id: UUID) -> CampaignUpload:
    upload = db.get(CampaignUpload, upload_id)
    if not upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Загрузка не найдена")
    return upload
