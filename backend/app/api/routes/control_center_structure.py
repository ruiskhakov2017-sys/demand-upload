from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_csrf, require_role
from app.control_center.schemas import (
    ConversionActionMappingIn,
    GeoCreateIn,
    GeoPatchIn,
    MccGeoAssignmentIn,
)
from app.core.database import get_db
from app.core.security import utcnow
from app.db.models import (
    AccountManagerHistory,
    ConversionActionMapping,
    CustomerAccount,
    GeoDefinition,
    GoogleAccountAccessPath,
    GoogleConnection,
    MccAccount,
    User,
    UserRole,
)
from app.domain.audit import record_audit

router = APIRouter(prefix="/control-center", tags=["control-center-structure"])


@router.get("/geos")
def list_geos(
    include_archived: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    del user
    query = select(GeoDefinition)
    if not include_archived:
        query = query.where(GeoDefinition.is_active.is_(True))
    return [_geo_payload(item) for item in db.scalars(query.order_by(GeoDefinition.display_name)).all()]


@router.post("/geos", status_code=status.HTTP_201_CREATED)
def create_geo(
    payload: GeoCreateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
    _: User = Depends(require_csrf),
) -> dict:
    geo = GeoDefinition(**payload.model_dump())
    db.add(geo)
    record_audit(
        db,
        request,
        user,
        "control_center.geo.create",
        "geo_definition",
        None,
        {"iso_code": geo.iso_code, "display_name": geo.display_name},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="GEO с таким ISO-кодом уже существует") from exc
    db.refresh(geo)
    return _geo_payload(geo)


@router.patch("/geos/{geo_id}")
def patch_geo(
    geo_id: UUID,
    payload: GeoPatchIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
    _: User = Depends(require_csrf),
) -> dict:
    geo = db.get(GeoDefinition, geo_id)
    if not geo:
        raise HTTPException(status_code=404, detail="GEO не найдено")
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(geo, field, value)
    record_audit(
        db,
        request,
        user,
        "control_center.geo.update",
        "geo_definition",
        str(geo.id),
        {"fields": sorted(changes)},
    )
    db.commit()
    db.refresh(geo)
    return _geo_payload(geo)


@router.get("/mcc")
def list_mcc_accounts(
    connection_id: UUID | None = None,
    geo_id: UUID | None = None,
    include_detached: bool = True,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    del user
    query = select(MccAccount)
    if connection_id:
        query = query.where(MccAccount.connection_id == connection_id)
    if geo_id:
        query = query.where(MccAccount.geo_id == geo_id)
    if not include_detached:
        query = query.where(MccAccount.detached_at.is_(None))
    mcc_accounts = list(
        db.scalars(
            query.order_by(
                MccAccount.connection_id,
                MccAccount.hierarchy_level,
                MccAccount.customer_id,
            )
        ).all()
    )
    geos = {
        geo.id: geo
        for geo in db.scalars(
            select(GeoDefinition).where(GeoDefinition.id.in_([item.geo_id for item in mcc_accounts if item.geo_id]))
        ).all()
    }
    connection_names = {
        item.id: item.name
        for item in db.scalars(
            select(GoogleConnection).where(GoogleConnection.id.in_([item.connection_id for item in mcc_accounts]))
        ).all()
    }
    return [
        _mcc_payload(
            item,
            geos.get(item.geo_id),
            connection_names.get(item.connection_id),
        )
        for item in mcc_accounts
    ]


@router.patch("/mcc/{mcc_id}/geo")
def assign_mcc_geo(
    mcc_id: UUID,
    payload: MccGeoAssignmentIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
    _: User = Depends(require_csrf),
) -> dict:
    mcc = db.get(MccAccount, mcc_id)
    if not mcc:
        raise HTTPException(status_code=404, detail="MCC не найден")
    geo = db.get(GeoDefinition, payload.geo_id) if payload.geo_id else None
    if payload.geo_id and not geo:
        raise HTTPException(status_code=404, detail="GEO не найдено")
    previous_geo_id = mcc.geo_id
    mcc.geo_id = geo.id if geo else None
    mcc.geo_assigned_by_id = user.id
    mcc.geo_assigned_at = utcnow()
    inherited_accounts = list(
        db.scalars(
            select(CustomerAccount).where(
                CustomerAccount.primary_mcc_id == mcc.id,
                CustomerAccount.geo_override_id.is_(None),
            )
        ).all()
    )
    for account in inherited_accounts:
        account.geo_id = mcc.geo_id
    record_audit(
        db,
        request,
        user,
        "control_center.mcc.assign_geo",
        "mcc_account",
        str(mcc.id),
        {
            "previous_geo_id": str(previous_geo_id) if previous_geo_id else None,
            "geo_id": str(mcc.geo_id) if mcc.geo_id else None,
            "inherited_accounts": len(inherited_accounts),
        },
    )
    db.commit()
    db.refresh(mcc)
    return _mcc_payload(mcc, geo, None)


@router.get("/hierarchy")
def get_hierarchy(
    connection_id: UUID | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    del user
    mcc_query = select(MccAccount)
    account_query = select(CustomerAccount)
    path_query = select(GoogleAccountAccessPath).where(GoogleAccountAccessPath.is_active.is_(True))
    if connection_id:
        mcc_query = mcc_query.where(MccAccount.connection_id == connection_id)
        account_query = account_query.where(CustomerAccount.connection_id == connection_id)
        path_query = path_query.where(GoogleAccountAccessPath.connection_id == connection_id)
    mcc_accounts = list(db.scalars(mcc_query).all())
    accounts = list(db.scalars(account_query).all())
    paths = list(db.scalars(path_query).all())
    return {
        "mcc": [
            {
                "id": str(item.id),
                "connection_id": str(item.connection_id),
                "customer_id": item.customer_id,
                "name": item.descriptive_name,
                "parent_customer_id": item.parent_customer_id,
                "level": item.hierarchy_level,
                "is_root": item.is_root,
                "geo_id": str(item.geo_id) if item.geo_id else None,
                "geo_assigned": item.geo_id is not None,
                "detached_at": item.detached_at,
            }
            for item in mcc_accounts
        ],
        "accounts": [
            {
                "id": str(item.id),
                "connection_id": str(item.connection_id),
                "customer_id": item.customer_id,
                "name": item.local_name or item.descriptive_name,
                "primary_mcc_id": str(item.primary_mcc_id) if item.primary_mcc_id else None,
                "geo_id": str(item.geo_id) if item.geo_id else None,
                "geo_override": item.geo_override_id is not None,
                "detached_at": item.detached_at,
            }
            for item in accounts
        ],
        "paths": [_path_payload(item) for item in paths],
    }


@router.get("/accounts/{account_id}/access-paths")
def list_account_access_paths(
    account_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    del user
    if not db.get(CustomerAccount, account_id):
        raise HTTPException(status_code=404, detail="Аккаунт не найден")
    return [
        _path_payload(item)
        for item in db.scalars(
            select(GoogleAccountAccessPath)
            .where(GoogleAccountAccessPath.account_id == account_id)
            .order_by(
                GoogleAccountAccessPath.is_active.desc(),
                GoogleAccountAccessPath.is_primary.desc(),
                GoogleAccountAccessPath.depth,
            )
        ).all()
    ]


@router.get("/accounts/{account_id}/manager-history")
def list_account_manager_history(
    account_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    del user
    if not db.get(CustomerAccount, account_id):
        raise HTTPException(status_code=404, detail="Аккаунт не найден")
    return [
        {
            "id": str(item.id),
            "previous_mcc_id": str(item.previous_mcc_id) if item.previous_mcc_id else None,
            "current_mcc_id": str(item.current_mcc_id) if item.current_mcc_id else None,
            "previous_manager_customer_id": item.previous_manager_customer_id,
            "current_manager_customer_id": item.current_manager_customer_id,
            "previous_path": item.previous_path,
            "current_path": item.current_path,
            "reason": item.reason,
            "changed_at": item.changed_at,
            "request_id": item.request_id,
        }
        for item in db.scalars(
            select(AccountManagerHistory)
            .where(AccountManagerHistory.account_id == account_id)
            .order_by(AccountManagerHistory.changed_at.desc())
        ).all()
    ]


@router.get("/conversion-action-mappings")
def list_conversion_action_mappings(
    connection_id: UUID | None = None,
    account_id: UUID | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    del user
    query = select(ConversionActionMapping)
    if connection_id:
        query = query.where(ConversionActionMapping.connection_id == connection_id)
    if account_id:
        query = query.where(
            or_(
                ConversionActionMapping.account_id == account_id,
                ConversionActionMapping.account_id.is_(None),
            )
        )
    return [
        _mapping_payload(item)
        for item in db.scalars(
            query.order_by(
                ConversionActionMapping.semantic_type,
                ConversionActionMapping.name,
                ConversionActionMapping.conversion_action_id,
            )
        ).all()
    ]


@router.post("/conversion-action-mappings", status_code=status.HTTP_201_CREATED)
def create_conversion_action_mapping(
    payload: ConversionActionMappingIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
    _: User = Depends(require_csrf),
) -> dict:
    connection = db.get(GoogleConnection, payload.connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Подключение не найдено")
    account = db.get(CustomerAccount, payload.account_id) if payload.account_id else None
    if account and account.connection_id != connection.id:
        raise HTTPException(
            status_code=422,
            detail="Аккаунт относится к другому Google-подключению",
        )
    scope_key = f"ACCOUNT:{account.id}" if account else f"CONNECTION:{connection.id}"
    mapping = ConversionActionMapping(
        **payload.model_dump(),
        scope_type="ACCOUNT" if account else "CONNECTION",
        scope_key=scope_key,
    )
    db.add(mapping)
    record_audit(
        db,
        request,
        user,
        "control_center.conversion_mapping.create",
        "conversion_action_mapping",
        None,
        {
            "connection_id": str(connection.id),
            "account_id": str(account.id) if account else None,
            "semantic_type": mapping.semantic_type,
            "conversion_action_id": mapping.conversion_action_id,
        },
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Такое сопоставление уже существует") from exc
    db.refresh(mapping)
    return _mapping_payload(mapping)


@router.delete(
    "/conversion-action-mappings/{mapping_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_conversion_action_mapping(
    mapping_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
    _: User = Depends(require_csrf),
) -> None:
    mapping = db.get(ConversionActionMapping, mapping_id)
    if not mapping:
        raise HTTPException(status_code=404, detail="Сопоставление не найдено")
    record_audit(
        db,
        request,
        user,
        "control_center.conversion_mapping.delete",
        "conversion_action_mapping",
        str(mapping.id),
        {
            "semantic_type": mapping.semantic_type,
            "conversion_action_id": mapping.conversion_action_id,
        },
    )
    db.delete(mapping)
    db.commit()


def _geo_payload(geo: GeoDefinition) -> dict:
    return {
        "id": str(geo.id),
        "iso_code": geo.iso_code,
        "display_name": geo.display_name,
        "default_currency_code": geo.default_currency_code,
        "default_time_zone": geo.default_time_zone,
        "is_active": geo.is_active,
        "color": geo.color,
        "short_label": geo.short_label,
        "created_at": geo.created_at,
        "updated_at": geo.updated_at,
    }


def _mcc_payload(
    mcc: MccAccount,
    geo: GeoDefinition | None,
    connection_name: str | None,
) -> dict:
    return {
        "id": str(mcc.id),
        "connection_id": str(mcc.connection_id),
        "connection_name": connection_name,
        "customer_id": mcc.customer_id,
        "parent_customer_id": mcc.parent_customer_id,
        "descriptive_name": mcc.descriptive_name,
        "currency_code": mcc.currency_code,
        "time_zone": mcc.time_zone,
        "is_root": mcc.is_root,
        "hierarchy_level": mcc.hierarchy_level,
        "status": mcc.status,
        "geo": _geo_payload(geo) if geo else None,
        "geo_assignment_status": "ASSIGNED" if geo else "UNASSIGNED",
        "first_seen_at": mcc.first_seen_at,
        "last_seen_at": mcc.last_seen_at,
        "last_sync_success_at": mcc.last_sync_success_at,
        "detached_at": mcc.detached_at,
    }


def _path_payload(path: GoogleAccountAccessPath) -> dict:
    return {
        "id": str(path.id),
        "connection_id": str(path.connection_id),
        "target_customer_id": path.target_customer_id,
        "account_id": str(path.account_id) if path.account_id else None,
        "mcc_account_id": str(path.mcc_account_id) if path.mcc_account_id else None,
        "root_customer_id": path.root_customer_id,
        "manager_customer_id": path.manager_customer_id,
        "customer_path": path.customer_path,
        "depth": path.depth,
        "is_primary": path.is_primary,
        "is_active": path.is_active,
        "first_seen_at": path.first_seen_at,
        "last_seen_at": path.last_seen_at,
        "lost_at": path.lost_at,
        "last_request_id": path.last_request_id,
    }


def _mapping_payload(mapping: ConversionActionMapping) -> dict:
    return {
        "id": str(mapping.id),
        "connection_id": str(mapping.connection_id),
        "account_id": str(mapping.account_id) if mapping.account_id else None,
        "scope_type": mapping.scope_type,
        "semantic_type": mapping.semantic_type,
        "resource_name": mapping.resource_name,
        "conversion_action_id": mapping.conversion_action_id,
        "name": mapping.name,
        "owner_customer_id": mapping.owner_customer_id,
        "is_cross_account": mapping.is_cross_account,
        "is_active": mapping.is_active,
        "last_synced_at": mapping.last_synced_at,
        "created_at": mapping.created_at,
        "updated_at": mapping.updated_at,
    }
