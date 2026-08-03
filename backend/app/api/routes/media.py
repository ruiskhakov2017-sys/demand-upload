from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_csrf
from app.api.workflow_schemas import MediaOut, YouTubeRegisterIn, YouTubeUploadIn
from app.core.database import get_db
from app.core.security import utcnow
from app.db.models import (
    CustomerAccount,
    GoogleConnection,
    Job,
    JobStatus,
    MediaAsset,
    MediaStatus,
    User,
)
from app.domain.audit import record_audit
from app.domain.media import inspect_media
from app.google_ads.safety import (
    GoogleAdsSafetyError,
    require_execution_mode_for_connection,
    require_google_test_connection_target,
)
from app.google_ads.service import is_google_connection_active
from app.storage.filesystem import FilesystemStorage

router = APIRouter(prefix="/media", tags=["media"])
MAX_MEDIA_BYTES = 5 * 1024 * 1024 * 1024


@router.get("", response_model=list[MediaOut])
def list_media(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[MediaAsset]:
    return list(db.scalars(select(MediaAsset).order_by(desc(MediaAsset.updated_at)).limit(500)).all())


@router.get("/{media_id}/content", response_class=FileResponse)
def get_media_content(
    media_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    asset = db.get(MediaAsset, media_id)
    if not asset or not asset.storage_key:
        raise HTTPException(status_code=404, detail="Медиафайл не найден")

    storage = FilesystemStorage()
    root = storage.root.resolve()
    try:
        path = storage.open_path(asset.storage_key).resolve()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Медиафайл не найден") from exc
    if root not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Медиафайл не найден")

    return FileResponse(
        path,
        media_type=asset.content_type or "application/octet-stream",
        filename=asset.name,
        content_disposition_type="inline",
    )


@router.post("/upload", response_model=MediaOut, status_code=status.HTTP_201_CREATED)
async def upload_media(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> MediaAsset:
    suffix = Path(file.filename or "media.bin").suffix.lower()
    sha = hashlib.sha256()
    total = 0
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_path = Path(temp.name)
    try:
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_MEDIA_BYTES:
                raise HTTPException(status_code=413, detail="Размер медиа превышает 5 ГБ")
            sha.update(chunk)
            temp.write(chunk)
        temp.close()
        if not total:
            raise HTTPException(status_code=422, detail="Файл пуст")
        try:
            inspection = inspect_media(temp_path, file.content_type)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        digest = sha.hexdigest()
        existing = db.scalar(
            select(MediaAsset).where(MediaAsset.kind == inspection["kind"], MediaAsset.sha256 == digest)
        )
        if existing:
            return existing
        key = f"media/{digest[:2]}/{digest}{suffix}"
        FilesystemStorage().put_file(temp_path, key, file.content_type)
        asset = MediaAsset(
            kind=inspection["kind"],
            source="UPLOAD",
            name=(file.filename or digest)[:255],
            sha256=digest,
            storage_key=key,
            content_type=file.content_type,
            size_bytes=total,
            width=inspection["width"],
            height=inspection["height"],
            duration_seconds=inspection["duration_seconds"],
            aspect_ratio=inspection["aspect_ratio"],
            status=MediaStatus.READY.value if inspection["validation"]["valid"] else MediaStatus.INVALID.value,
            validation=inspection["validation"],
            google_asset_resources={},
            details={},
            created_by_id=user.id,
        )
        db.add(asset)
        db.flush()
        record_audit(
            db,
            request,
            user,
            "media.upload",
            "media_asset",
            str(asset.id),
            {"name": asset.name, "sha256": digest, "size_bytes": total, "kind": asset.kind},
        )
        db.commit()
        db.refresh(asset)
        return asset
    finally:
        temp.close()
        temp_path.unlink(missing_ok=True)


@router.post("/youtube", response_model=MediaOut, status_code=status.HTTP_201_CREATED)
def register_youtube_video(
    payload: YouTubeRegisterIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> MediaAsset:
    digest = hashlib.sha256(f"youtube:{payload.video_id}".encode()).hexdigest()
    existing = db.scalar(select(MediaAsset).where(MediaAsset.kind == "YOUTUBE", MediaAsset.sha256 == digest))
    if existing:
        return existing
    asset = MediaAsset(
        kind="YOUTUBE",
        source="YOUTUBE_ID",
        name=(payload.name or f"YouTube {payload.video_id}")[:255],
        sha256=digest,
        storage_key=None,
        content_type="video/youtube",
        size_bytes=0,
        status=MediaStatus.READY.value,
        validation={"valid": True, "errors": [], "warnings": []},
        youtube_video_id=payload.video_id,
        google_asset_resources={},
        details={"url": f"https://www.youtube.com/watch?v={payload.video_id}"},
        created_by_id=user.id,
    )
    db.add(asset)
    db.flush()
    record_audit(
        db,
        request,
        user,
        "media.youtube.register",
        "media_asset",
        str(asset.id),
        {"video_id": payload.video_id},
    )
    db.commit()
    db.refresh(asset)
    return asset


@router.post("/{media_id}/youtube-upload")
def queue_youtube_upload(
    media_id: UUID,
    payload: YouTubeUploadIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> dict:
    asset = db.get(MediaAsset, media_id)
    if not asset or asset.kind != "VIDEO" or not asset.storage_key:
        raise HTTPException(status_code=404, detail="Исходное видео не найдено")
    if payload.execution_mode != "SIMULATION":
        connection = db.get(GoogleConnection, payload.connection_id) if payload.connection_id else None
        if not is_google_connection_active(connection):
            raise HTTPException(status_code=409, detail="Для Google Test нужно активное подключение")
        account = db.scalar(
            select(CustomerAccount).where(
                CustomerAccount.connection_id == connection.id,
                CustomerAccount.customer_id == payload.customer_id,
            )
        )
        try:
            require_execution_mode_for_connection(connection, payload.execution_mode)
            require_google_test_connection_target(
                connection, account, payload.customer_id
            )
        except GoogleAdsSafetyError as exc:
            raise HTTPException(status_code=409, detail=f"{exc.code}: {exc}") from exc
    key = f"youtube-upload:{asset.id}:{payload.execution_mode}:{payload.connection_id or 'simulation'}"
    existing = db.scalar(select(Job).where(Job.idempotency_key == key))
    if existing and existing.status in {JobStatus.QUEUED.value, JobStatus.RUNNING.value, JobStatus.SUCCEEDED.value}:
        return {"job_id": str(existing.id), "reused": True}
    job = existing or Job(
        type="YOUTUBE_VIDEO_UPLOAD",
        status=JobStatus.QUEUED.value,
        connection_id=payload.connection_id,
        created_by_id=user.id,
        idempotency_key=key,
        progress_current=0,
        progress_total=2,
        payload={},
    )
    job.status = JobStatus.QUEUED.value
    job.error_message = None
    job.payload = {
        "media_id": str(asset.id),
        "confirmed_at": utcnow().isoformat(),
        **payload.model_dump(mode="json"),
    }
    asset.status = MediaStatus.PENDING.value
    db.add(job)
    db.flush()
    record_audit(
        db,
        request,
        user,
        "media.youtube.queue",
        "media_asset",
        str(asset.id),
        {"job_id": str(job.id), "execution_mode": payload.execution_mode},
    )
    db.commit()
    from app.jobs.tasks import upload_youtube_video

    upload_youtube_video.delay(str(job.id))
    return {"job_id": str(job.id), "reused": False}
