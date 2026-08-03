from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.db.models import (
    ControlCenterAd,
    ControlCenterAdAssetLink,
    ControlCenterAdGroup,
    ControlCenterAsset,
    ControlCenterGoogleChange,
    ControlCenterSyncItem,
    ControlCenterSyncRun,
    CustomerAccount,
    GoogleConnection,
    User,
)
from app.google_ads.service import build_google_ads_adapter, is_google_connection_active

router = APIRouter(prefix="/control-center", tags=["control-center-drilldown"])


@router.get("/conversion-actions/catalog")
def conversion_action_catalog(
    account_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    del user
    account = db.get(CustomerAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")
    connection = db.get(GoogleConnection, account.connection_id)
    if not is_google_connection_active(connection):
        raise HTTPException(status_code=409, detail="Google-подключение не активно")
    try:
        rows = build_google_ads_adapter(db, connection).list_conversion_actions(
            account.customer_id
        )
    except Exception as exc:
        raise _google_read_http_error(exc) from exc
    request_ids = list(
        dict.fromkeys(
            request_id
            for row in rows
            for request_id in (row.pop("_request_ids", []) or [])
        )
    )
    return {
        "account_id": str(account.id),
        "customer_id": account.customer_id,
        "items": rows,
        "request_ids": request_ids,
        "read_only": True,
    }


@router.get("/ad-groups")
def list_ad_groups(
    account_id: UUID | None = None,
    campaign_id: UUID | None = None,
    status_filter: str | None = None,
    search: str | None = Query(default=None, max_length=500),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    del user
    query = select(ControlCenterAdGroup)
    if account_id:
        query = query.where(ControlCenterAdGroup.account_id == account_id)
    if campaign_id:
        query = query.where(ControlCenterAdGroup.campaign_id == campaign_id)
    if status_filter:
        query = query.where(ControlCenterAdGroup.status == status_filter.upper())
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                ControlCenterAdGroup.name.ilike(term),
                ControlCenterAdGroup.resource_name.ilike(term),
            )
        )
    all_rows = list(db.scalars(query.order_by(ControlCenterAdGroup.name)).all())
    return {
        "items": [_ad_group_payload(row) for row in all_rows[offset : offset + limit]],
        "total": len(all_rows),
        "limit": limit,
        "offset": offset,
    }


@router.get("/ads")
def list_ads(
    account_id: UUID | None = None,
    campaign_id: UUID | None = None,
    ad_group_id: UUID | None = None,
    status_filter: str | None = None,
    policy_status: str | None = None,
    search: str | None = Query(default=None, max_length=500),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    del user
    query = select(ControlCenterAd)
    if account_id:
        query = query.where(ControlCenterAd.account_id == account_id)
    if campaign_id:
        query = query.where(ControlCenterAd.campaign_id == campaign_id)
    if ad_group_id:
        query = query.where(ControlCenterAd.ad_group_id == ad_group_id)
    if status_filter:
        query = query.where(ControlCenterAd.status == status_filter.upper())
    if policy_status:
        query = query.where(ControlCenterAd.primary_status == policy_status.upper())
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                ControlCenterAd.name.ilike(term),
                ControlCenterAd.resource_name.ilike(term),
            )
        )
    all_rows = list(
        db.scalars(query.order_by(desc(ControlCenterAd.last_synced_at), ControlCenterAd.ad_id)).all()
    )
    return {
        "items": [_ad_payload(row) for row in all_rows[offset : offset + limit]],
        "total": len(all_rows),
        "limit": limit,
        "offset": offset,
    }


@router.get("/assets")
def list_assets(
    account_id: UUID | None = None,
    campaign_id: UUID | None = None,
    ad_id: UUID | None = None,
    asset_type: str | None = None,
    search: str | None = Query(default=None, max_length=500),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    del user
    query = select(ControlCenterAsset)
    if campaign_id or ad_id:
        query = query.join(
            ControlCenterAdAssetLink,
            ControlCenterAdAssetLink.asset_id == ControlCenterAsset.id,
        )
    if account_id:
        query = query.where(ControlCenterAsset.account_id == account_id)
    if campaign_id:
        query = query.where(ControlCenterAdAssetLink.campaign_id == campaign_id)
    if ad_id:
        query = query.where(ControlCenterAdAssetLink.ad_id == ad_id)
    if asset_type:
        query = query.where(ControlCenterAsset.asset_type == asset_type.upper())
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                ControlCenterAsset.name.ilike(term),
                ControlCenterAsset.resource_name.ilike(term),
                ControlCenterAsset.youtube_video_id.ilike(term),
            )
        )
    all_rows = list(
        db.scalars(
            query.distinct().order_by(
                ControlCenterAsset.asset_type,
                ControlCenterAsset.name,
                ControlCenterAsset.asset_id,
            )
        ).all()
    )
    return {
        "items": [_asset_payload(row) for row in all_rows[offset : offset + limit]],
        "total": len(all_rows),
        "limit": limit,
        "offset": offset,
    }


@router.get("/asset-links")
def list_asset_links(
    account_id: UUID | None = None,
    campaign_id: UUID | None = None,
    ad_id: UUID | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    del user
    query = select(ControlCenterAdAssetLink)
    if account_id:
        query = query.where(ControlCenterAdAssetLink.account_id == account_id)
    if campaign_id:
        query = query.where(ControlCenterAdAssetLink.campaign_id == campaign_id)
    if ad_id:
        query = query.where(ControlCenterAdAssetLink.ad_id == ad_id)
    return [
        {
            "id": str(row.id),
            "account_id": str(row.account_id),
            "campaign_id": str(row.campaign_id),
            "ad_group_id": str(row.ad_group_id),
            "ad_id": str(row.ad_id),
            "asset_id": str(row.asset_id),
            "resource_name": row.resource_name,
            "field_type": row.field_type,
            "performance_label": row.performance_label,
            "policy_summary": row.policy_summary,
            "last_synced_at": row.last_synced_at,
        }
        for row in db.scalars(query.order_by(ControlCenterAdAssetLink.field_type)).all()
    ]


@router.get("/moderation")
def list_moderation(
    account_id: UUID | None = None,
    only_issues: bool = True,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    del user
    query = select(ControlCenterAd)
    if account_id:
        query = query.where(ControlCenterAd.account_id == account_id)
    if only_issues:
        query = query.where(
            ControlCenterAd.primary_status.in_(
                ["DISAPPROVED", "APPROVED_LIMITED", "AREA_OF_INTEREST_ONLY"]
            )
        )
    rows = list(db.scalars(query.order_by(desc(ControlCenterAd.last_synced_at))).all())
    return {
        "items": [_ad_payload(row) for row in rows],
        "total": len(rows),
        "data_note": (
            "Показаны только статусы и причины, которые вернул Google Ads API; "
            "программа не придумывает причину блокировки."
        ),
    }


@router.get("/verification")
def list_verification(
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    del user
    query = select(CustomerAccount)
    if status_filter:
        query = query.where(
            CustomerAccount.verification_status == status_filter.upper()
        )
    return [
        {
            "account_id": str(row.id),
            "customer_id": row.customer_id,
            "account_name": row.local_name or row.descriptive_name or row.customer_id,
            "status": row.verification_status or "UNKNOWN",
            "deadline": row.verification_deadline,
            "action_url": row.verification_action_url,
            "checked_at": row.verification_checked_at,
            "last_sync_error": row.sync_error,
        }
        for row in db.scalars(
            query.order_by(
                CustomerAccount.verification_deadline,
                CustomerAccount.customer_id,
            )
        ).all()
    ]


@router.get("/changes")
def list_google_changes(
    account_id: UUID | None = None,
    campaign_id: UUID | None = None,
    resource_type: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    del user
    query = select(ControlCenterGoogleChange)
    if account_id:
        query = query.where(ControlCenterGoogleChange.account_id == account_id)
    if campaign_id:
        query = query.where(ControlCenterGoogleChange.campaign_id == campaign_id)
    if resource_type:
        query = query.where(
            ControlCenterGoogleChange.resource_type == resource_type.upper()
        )
    rows = list(
        db.scalars(
            query.order_by(desc(ControlCenterGoogleChange.changed_at))
        ).all()
    )
    return {
        "items": [_change_payload(row) for row in rows[offset : offset + limit]],
        "total": len(rows),
        "limit": limit,
        "offset": offset,
        "history_depth": (
            "Google ChangeEvent обычно доступен только за ограниченный недавний период; "
            "программа сохраняет уже синхронизированную локальную историю."
        ),
    }


@router.get("/sync-runs")
def list_sync_runs(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    del user
    runs = list(
        db.scalars(
            select(ControlCenterSyncRun)
            .order_by(desc(ControlCenterSyncRun.created_at))
            .limit(limit)
        ).all()
    )
    run_ids = [row.id for row in runs]
    items_by_run: dict[UUID, list[ControlCenterSyncItem]] = {
        run_id: [] for run_id in run_ids
    }
    if run_ids:
        for item in db.scalars(
            select(ControlCenterSyncItem).where(
                ControlCenterSyncItem.sync_run_id.in_(run_ids)
            )
        ).all():
            items_by_run[item.sync_run_id].append(item)
    return [
        {
            "id": str(row.id),
            "scope": row.scope,
            "mode": row.mode,
            "status": row.status,
            "estimated_operations": row.estimated_operations,
            "actual_operations": row.actual_operations,
            "successful_accounts": row.successful_accounts,
            "failed_accounts": row.failed_accounts,
            "request_ids": row.request_ids,
            "statistics": row.statistics,
            "started_at": row.started_at,
            "completed_at": row.completed_at,
            "duration_ms": row.duration_ms,
            "created_at": row.created_at,
            "items": [
                {
                    "id": str(item.id),
                    "account_id": str(item.account_id),
                    "status": item.status,
                    "attempts": item.attempts,
                    "operations": item.operations,
                    "request_ids": item.request_ids,
                    "error_code": item.error_code,
                    "error_message": item.error_message,
                }
                for item in items_by_run[row.id]
            ],
        }
        for row in runs
    ]


def _ad_group_payload(row: ControlCenterAdGroup) -> dict:
    return {
        "id": str(row.id),
        "account_id": str(row.account_id),
        "campaign_id": str(row.campaign_id),
        "resource_name": row.resource_name,
        "ad_group_id": row.ad_group_id,
        "name": row.name,
        "status": row.status,
        "ad_group_type": row.ad_group_type,
        "optimized_targeting_enabled": row.optimized_targeting_enabled,
        "metrics": {
            "impressions": row.impressions,
            "clicks": row.clicks,
            "cost_micros": row.cost_micros,
            "conversions": row.conversions,
            "conversion_value": row.conversion_value,
        },
        "policy_issues": row.policy_issues,
        "last_synced_at": row.last_synced_at,
    }


def _ad_payload(row: ControlCenterAd) -> dict:
    return {
        "id": str(row.id),
        "account_id": str(row.account_id),
        "campaign_id": str(row.campaign_id),
        "ad_group_id": str(row.ad_group_id),
        "resource_name": row.resource_name,
        "ad_id": row.ad_id,
        "name": row.name,
        "ad_type": row.ad_type,
        "status": row.status,
        "policy_status": row.primary_status,
        "final_urls": row.final_urls,
        "policy_summary": row.policy_summary,
        "disapproval_reasons": row.disapproval_reasons,
        "metrics": {
            "impressions": row.impressions,
            "clicks": row.clicks,
            "cost_micros": row.cost_micros,
            "conversions": row.conversions,
            "conversion_value": row.conversion_value,
        },
        "last_synced_at": row.last_synced_at,
    }


def _asset_payload(row: ControlCenterAsset) -> dict:
    return {
        "id": str(row.id),
        "account_id": str(row.account_id),
        "resource_name": row.resource_name,
        "asset_id": row.asset_id,
        "name": row.name,
        "asset_type": row.asset_type,
        "source": row.source,
        "status": row.status,
        "policy_summary": row.policy_summary,
        "image_url": row.image_url,
        "image_width": row.image_width,
        "image_height": row.image_height,
        "file_size_bytes": row.file_size_bytes,
        "youtube_video_id": row.youtube_video_id,
        "youtube_video_title": row.youtube_video_title,
        "youtube_processing_status": row.youtube_processing_status,
        "processing_note": (
            None
            if row.youtube_processing_status
            else "Google Ads API не вернул отдельный статус обработки YouTube для этого asset."
        ),
        "last_synced_at": row.last_synced_at,
    }


def _change_payload(row: ControlCenterGoogleChange) -> dict:
    return {
        "id": str(row.id),
        "connection_id": str(row.connection_id),
        "account_id": str(row.account_id),
        "campaign_id": str(row.campaign_id) if row.campaign_id else None,
        "change_resource_name": row.change_resource_name,
        "changed_resource_name": row.changed_resource_name,
        "resource_type": row.resource_type,
        "change_type": row.change_type,
        "client_type": row.client_type,
        "user_email": row.user_email,
        "old_resource": row.old_resource,
        "new_resource": row.new_resource,
        "changed_fields": row.changed_fields,
        "changed_at": row.changed_at,
        "request_id": row.request_id,
    }


def _google_read_http_error(exc: Exception) -> HTTPException:
    request_id = getattr(exc, "request_id", None)
    code = exc.__class__.__name__
    failure = getattr(exc, "failure", None)
    errors = list(getattr(failure, "errors", []) or [])
    if errors:
        code = str(getattr(errors[0], "error_code", None) or code)
    return HTTPException(
        status_code=502,
        detail={
            "code": code,
            "message": str(exc),
            "request_id": str(request_id) if request_id else None,
            "explanation": "Google Ads не выполнил безопасный запрос на чтение.",
        },
    )
