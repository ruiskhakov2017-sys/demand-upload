from __future__ import annotations

import csv
import io
from copy import deepcopy
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_csrf
from app.api.workflow_schemas import BatchGenerateIn, CampaignInstancePatchIn
from app.core.database import get_db
from app.core.security import utcnow, verify_password
from app.db.models import (
    AccountTestBundle,
    ApplicationSetting,
    BudgetGenerationConfig,
    CampaignInstance,
    CampaignTemplate,
    CampaignTemplateVersion,
    CampaignUpload,
    CreativeAssignment,
    CustomerAccount,
    GoogleConnection,
    LaunchBatch,
    MediaAsset,
    User,
)
from app.domain.audit import record_audit
from app.domain.batch_generator import (
    GenerationError,
    build_deployment_key,
    build_financial_preview,
    deep_merge,
    generate_batch_matrix,
)
from app.domain_validation.persistence import enqueue_upload_validation, mark_upload_validation_pending
from app.google_ads.safety import (
    GoogleAdsSafetyError,
    require_execution_mode_for_connection,
    require_google_test_connection_target,
)
from app.google_ads.service import is_google_connection_active

router = APIRouter(tags=["campaign-builder"])
DEFAULT_GUARDRAILS = {
    "max_campaigns_per_account": 50,
    "max_campaigns_per_job": 500,
    "max_parallel_enabled": 20,
    "max_budget_by_currency": {},
}


@router.get("/launch-batches")
def list_launch_batches(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    batches = db.scalars(select(LaunchBatch).order_by(desc(LaunchBatch.created_at)).limit(200)).all()
    return [_batch_summary(db, item) for item in batches]


@router.get("/launch-batches/{batch_id}")
def get_launch_batch(
    batch_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return _batch_detail(db, _get_batch(db, batch_id))


@router.post("/launch-batches/from-upload/{upload_id}/generate", status_code=status.HTTP_201_CREATED)
def generate_launch_batch(
    upload_id: UUID,
    payload: BatchGenerateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> dict:
    upload = db.get(CampaignUpload, upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Загрузка не найдена")
    if payload.execution_mode != "SIMULATION":
        connection = db.get(GoogleConnection, upload.connection_id) if upload.connection_id else None
        if not is_google_connection_active(connection):
            raise HTTPException(status_code=409, detail="Для Google Test нужно активное OAuth/MCC подключение")
        try:
            require_execution_mode_for_connection(connection, payload.execution_mode)
        except GoogleAdsSafetyError as exc:
            raise HTTPException(status_code=409, detail=f"{exc.code}: {exc}") from exc

    config = payload.model_dump(mode="json")
    password_confirmation = config.pop("password_confirmation", None)
    template_version = _resolve_template_version(db, payload)
    if template_version:
        config["template_defaults"] = deep_merge(template_version.payload, config.get("template_defaults") or {})
        config["template_name"] = db.get(CampaignTemplate, template_version.template_id).name
    config["accounts"] = _trusted_accounts(db, upload, config["accounts"], payload.execution_mode)
    guardrails = _guardrails(db)
    campaign_total = sum(
        int(item.get("campaigns_count") or payload.campaigns_per_account) for item in config["accounts"]
    )
    requires_password = campaign_total > int(guardrails["max_campaigns_per_job"])
    requires_password = requires_password or any(
        int(item.get("campaigns_count") or payload.campaigns_per_account)
        > int(guardrails["max_campaigns_per_account"])
        for item in config["accounts"]
    )
    if requires_password and not _password_ok(user, password_confirmation):
        raise HTTPException(
            status_code=409,
            detail="Превышен предохранитель количества кампаний. Подтвердите действие паролем администратора.",
        )

    batch_id = uuid4()
    generation_time = utcnow()
    media_rows = db.scalars(select(MediaAsset).where(MediaAsset.status == "READY")).all()
    media_catalog = [
        {
            "id": str(item.id),
            "kind": item.kind,
            "sha256": item.sha256,
            "suggested_role": item.validation.get("suggested_role"),
        }
        for item in media_rows
    ]
    try:
        matrix = generate_batch_matrix(batch_id, config, generation_time, media_catalog)
    except GenerationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if _budget_guardrail_exceeded(matrix["financial_preview"], guardrails) and not _password_ok(
        user, password_confirmation
    ):
        raise HTTPException(
            status_code=409,
            detail="Сумма бюджетов превышает предохранитель. Подтвердите действие паролем администратора.",
        )

    latest_version = db.scalar(
        select(func.max(LaunchBatch.version_number)).where(LaunchBatch.upload_id == upload.id)
    ) or 0
    batch = LaunchBatch(
        id=batch_id,
        upload_id=upload.id,
        connection_id=upload.connection_id,
        template_version_id=template_version.id if template_version else None,
        name=payload.batch_name,
        version_number=latest_version + 1,
        creation_mode=payload.creation_mode,
        execution_mode=payload.execution_mode,
        status="MATRIX_READY",
        generation_seed=matrix["generation_seed"],
        generation_time=generation_time,
        name_pattern=matrix["name_pattern"],
        builder_config=config,
        financial_preview=matrix["financial_preview"],
        created_by_id=user.id,
    )
    db.add(batch)
    db.flush()
    db.add(_budget_model(batch.id, config.get("budget") or {}, matrix["generation_seed"]))
    media_by_id = {str(item.id): item for item in media_rows}
    bundle_rows: list[tuple[dict, AccountTestBundle]] = []
    for bundle_data in matrix["bundles"]:
        bundle = AccountTestBundle(
            id=UUID(bundle_data["id"]),
            launch_batch_id=batch.id,
            customer_account_id=UUID(bundle_data["customer_account_id"])
            if bundle_data.get("customer_account_id")
            else None,
            customer_id=bundle_data["customer_id"],
            account_name=bundle_data["account_name"],
            currency_code=bundle_data["currency_code"],
            time_zone=bundle_data["time_zone"],
            status="DRAFT",
            campaigns_count=bundle_data["campaigns_count"],
            override_payload=bundle_data["override_payload"],
        )
        db.add(bundle)
        bundle_rows.append((bundle_data, bundle))

    db.flush()
    instance_rows: list[tuple[dict, CampaignInstance]] = []
    for bundle_data, _bundle in bundle_rows:
        for item in bundle_data["instances"]:
            instance = _instance_model(item, batch, template_version)
            db.add(instance)
            instance_rows.append((item, instance))

    db.flush()
    for item, instance in instance_rows:
        for position, media_id in enumerate(item["creative_assignment"].get("media_ids") or []):
            media_item = media_by_id.get(str(media_id))
            db.add(
                CreativeAssignment(
                    campaign_instance_id=instance.id,
                    media_asset_id=media_item.id if media_item else None,
                    customer_id=instance.customer_id,
                    role=(media_item.validation.get("suggested_role") if media_item else None) or "AUTO",
                    position=position,
                    sha256=media_item.sha256 if media_item else None,
                    assignment={"set_key": item["creative_assignment"].get("set_key")},
                )
            )

    upload.draft = {
        **(upload.draft or {}),
        "execution_mode": payload.execution_mode,
        "launch_batch_id": str(batch.id),
        "builder": config,
    }
    upload.current_step = 13
    upload.status = "DRAFT"
    db.flush()
    mark_upload_validation_pending(db, upload)
    record_audit(
        db,
        request,
        user,
        "launch_batch.generate",
        "launch_batch",
        str(batch.id),
        {
            "accounts": matrix["financial_preview"]["accounts"],
            "campaigns": matrix["financial_preview"]["campaigns"],
            "copy_mode": matrix["copy_mode"],
            "seed": matrix["generation_seed"],
        },
    )
    db.commit()
    enqueue_upload_validation(upload.id)
    return _batch_detail(db, batch)


@router.patch("/campaign-instances/{instance_id}")
def patch_campaign_instance(
    instance_id: UUID,
    payload: CampaignInstancePatchIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> dict:
    instance = _get_instance(db, instance_id)
    if instance.deployment_plan_id:
        raise HTTPException(
            status_code=409,
            detail="Campaign Instance входит в immutable plan. Создайте новую версию Launch Batch.",
        )
    changes = payload.model_dump(exclude_unset=True)
    if "campaign_name" in changes:
        duplicate = db.scalar(
            select(CampaignInstance).where(
                CampaignInstance.launch_batch_id == instance.launch_batch_id,
                CampaignInstance.campaign_name == changes["campaign_name"],
                CampaignInstance.id != instance.id,
            )
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Название кампании уже используется в этом плане")
        instance.campaign_name = changes.pop("campaign_name")
    if "budget" in changes:
        instance.budget_micros = int(Decimal(str(changes.pop("budget"))) * Decimal(1_000_000))
        instance.budget_mode = "PER_CAMPAIGN_OVERRIDE"
    for field in (
        "included",
        "campaign_settings",
        "bidding",
        "targeting",
        "url_settings",
        "texts",
        "creative_assignment",
        "override_payload",
    ):
        if field in changes:
            setattr(instance, field, changes[field])
    instance.deployment_key = build_deployment_key(_instance_key_payload(instance))
    batch = db.get(LaunchBatch, instance.launch_batch_id)
    batch.financial_preview = _recalculate_financial(db, batch.id)
    upload = db.get(CampaignUpload, batch.upload_id)
    if upload and "url_settings" in payload.model_fields_set:
        mark_upload_validation_pending(db, upload)
    db.flush()
    record_audit(
        db,
        request,
        user,
        "campaign_instance.update",
        "campaign_instance",
        str(instance.id),
        {"fields": list(payload.model_dump(exclude_unset=True))},
    )
    db.commit()
    db.refresh(instance)
    if upload and "url_settings" in payload.model_fields_set:
        enqueue_upload_validation(upload.id)
    return _instance_out(instance, db.get(AccountTestBundle, instance.account_test_bundle_id))


@router.get("/launch-batches/{batch_id}/export")
def export_launch_batch(
    batch_id: UUID,
    format_: str = Query(default="xlsx", alias="format", pattern="^(xlsx|csv)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    batch = _get_batch(db, batch_id)
    bundles = {item.id: item for item in _bundles(db, batch.id)}
    rows = [_export_row(item, bundles[item.account_test_bundle_id], batch) for item in _instances(db, batch.id)]
    headers = list(rows[0]) if rows else ["Launch Batch", "Customer ID", "Campaign"]
    if format_ == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
        content = output.getvalue().encode("utf-8-sig")
        media_type = "text/csv; charset=utf-8"
    else:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Campaign matrix"
        sheet.append(headers)
        for row in rows:
            sheet.append([row[item] for item in headers])
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = min(
                45, max(12, max(len(str(cell.value or "")) for cell in column) + 2)
            )
        stream = io.BytesIO()
        workbook.save(stream)
        content = stream.getvalue()
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    extension = "csv" if format_ == "csv" else "xlsx"
    filename = f"launch-batch-{batch.id}.{extension}"
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _resolve_template_version(db: Session, payload: BatchGenerateIn) -> CampaignTemplateVersion | None:
    if payload.template_version_id:
        item = db.get(CampaignTemplateVersion, payload.template_version_id)
        if not item:
            raise HTTPException(status_code=404, detail="Версия шаблона не найдена")
        return item
    if payload.template_id:
        template = db.get(CampaignTemplate, payload.template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Шаблон не найден")
        return db.scalar(
            select(CampaignTemplateVersion).where(
                CampaignTemplateVersion.template_id == template.id,
                CampaignTemplateVersion.version_number == template.current_version,
            )
        )
    return None


def _trusted_accounts(db: Session, upload: CampaignUpload, accounts: list[dict], execution_mode: str) -> list[dict]:
    if execution_mode == "SIMULATION":
        return accounts
    connection = (
        db.get(GoogleConnection, upload.connection_id)
        if upload.connection_id
        else None
    )
    try:
        require_execution_mode_for_connection(connection, execution_mode)
    except GoogleAdsSafetyError as exc:
        raise HTTPException(status_code=409, detail=f"{exc.code}: {exc}") from exc
    rows = db.scalars(
        select(CustomerAccount).where(CustomerAccount.connection_id == upload.connection_id)
    ).all()
    known = {item.customer_id: item for item in rows}
    result: list[dict] = []
    for selected in accounts:
        customer_id = "".join(ch for ch in selected["customer_id"] if ch.isdigit())
        item = known.get(customer_id)
        if not item:
            raise HTTPException(status_code=422, detail=f"Аккаунт {customer_id} не принадлежит выбранному connection")
        try:
            require_google_test_connection_target(connection, item, customer_id)
        except GoogleAdsSafetyError as exc:
            raise HTTPException(status_code=409, detail=f"{exc.code}: {exc}") from exc
        result.append(
            {
                **selected,
                "id": str(item.id),
                "customer_id": item.customer_id,
                "account_name": item.descriptive_name or item.customer_id,
                "currency_code": item.currency_code or "USD",
                "time_zone": item.time_zone or "UTC",
            }
        )
    return result


def _instance_model(
    item: dict,
    batch: LaunchBatch,
    template_version: CampaignTemplateVersion | None,
) -> CampaignInstance:
    return CampaignInstance(
        id=UUID(item["id"]),
        launch_batch_id=batch.id,
        account_test_bundle_id=UUID(item["account_test_bundle_id"]),
        template_version_id=template_version.id if template_version else None,
        customer_id=item["customer_id"],
        campaign_sequence=item["campaign_sequence"],
        campaign_name=item["campaign_name"],
        status="DRAFT",
        policy_status="UNKNOWN",
        included=item["included"],
        budget_micros=item["budget_micros"],
        currency_code=item["currency_code"],
        budget_mode=item["budget_mode"],
        generation_seed=item["generation_seed"],
        copy_mode=item["copy_mode"],
        deployment_key=item["deployment_key"],
        campaign_settings=item["campaign_settings"],
        bidding=item["bidding"],
        targeting=item["targeting"],
        url_settings=item["url_settings"],
        texts=item["texts"],
        creative_assignment=item["creative_assignment"],
        override_payload=item["override_payload"],
        local_validation={},
        google_validation={},
        resource_names=[],
        request_ids=[],
        metrics={},
    )


def _budget_model(batch_id: UUID, budget: dict, seed: str) -> BudgetGenerationConfig:
    return BudgetGenerationConfig(
        launch_batch_id=batch_id,
        mode=str(budget.get("mode") or "FIXED").upper(),
        distribution=str(budget.get("distribution") or "BALANCED_RANDOM").upper(),
        fixed_micros=_optional_micros(budget.get("fixed", budget.get("value"))),
        minimum_micros=_optional_micros(budget.get("minimum", budget.get("min"))),
        maximum_micros=_optional_micros(budget.get("maximum", budget.get("max"))),
        step_micros=_optional_micros(budget.get("step")) or 1_000_000,
        decimal_places=int(budget.get("decimal_places") or 2),
        allow_repeats=bool(budget.get("allow_repeats", True)),
        seed=str(budget.get("seed") or seed),
        manual_values=budget.get("manual_values") or [],
        per_currency=budget.get("per_currency") or {},
    )


def _batch_summary(db: Session, batch: LaunchBatch) -> dict:
    bundles = _bundles(db, batch.id)
    return {
        "id": str(batch.id),
        "upload_id": str(batch.upload_id),
        "name": batch.name,
        "version_number": batch.version_number,
        "creation_mode": batch.creation_mode,
        "execution_mode": batch.execution_mode,
        "status": batch.status,
        "generation_seed": batch.generation_seed,
        "financial_preview": batch.financial_preview,
        "bundles_count": len(bundles),
        "campaigns_count": sum(item.campaigns_count for item in bundles),
        "created_at": batch.created_at,
        "updated_at": batch.updated_at,
    }


def _batch_detail(db: Session, batch: LaunchBatch) -> dict:
    bundles = _bundles(db, batch.id)
    instances = _instances(db, batch.id)
    by_bundle: dict[UUID, list[CampaignInstance]] = {}
    for item in instances:
        by_bundle.setdefault(item.account_test_bundle_id, []).append(item)
    result = _batch_summary(db, batch)
    result.update(
        {
            "template_version_id": str(batch.template_version_id) if batch.template_version_id else None,
            "generation_time": batch.generation_time,
            "name_pattern": batch.name_pattern,
            "builder_config": batch.builder_config,
            "bundles": [
                {
                    "id": str(bundle.id),
                    "customer_id": bundle.customer_id,
                    "account_name": bundle.account_name,
                    "currency_code": bundle.currency_code,
                    "time_zone": bundle.time_zone,
                    "status": bundle.status,
                    "instances": [
                        _instance_out(item, bundle)
                        for item in sorted(by_bundle.get(bundle.id, []), key=lambda row: row.campaign_sequence)
                    ],
                }
                for bundle in bundles
            ],
        }
    )
    return result


def _instance_out(item: CampaignInstance, bundle: AccountTestBundle) -> dict:
    metrics = deepcopy(item.metrics or {})
    cost = int(metrics.get("cost_micros") or 0)
    conversions = float(metrics.get("conversions") or 0)
    metrics["cpa_micros"] = round(cost / conversions) if conversions else None
    metrics["ctr"] = (float(metrics.get("clicks") or 0) / float(metrics.get("impressions") or 1)) * 100
    return {
        "id": str(item.id),
        "launch_batch_id": str(item.launch_batch_id),
        "account_test_bundle_id": str(item.account_test_bundle_id),
        "customer_id": item.customer_id,
        "account_name": bundle.account_name,
        "currency_code": item.currency_code,
        "time_zone": bundle.time_zone,
        "campaign_sequence": item.campaign_sequence,
        "campaign_name": item.campaign_name,
        "status": item.status,
        "policy_status": item.policy_status,
        "included": item.included,
        "budget_micros": item.budget_micros,
        "budget": item.budget_micros / 1_000_000,
        "budget_mode": item.budget_mode,
        "copy_mode": item.copy_mode,
        "deployment_key": item.deployment_key,
        "campaign_settings": item.campaign_settings,
        "bidding": item.bidding,
        "targeting": item.targeting,
        "url_settings": item.url_settings,
        "texts": item.texts,
        "creative_assignment": item.creative_assignment,
        "local_validation": item.local_validation,
        "google_validation": item.google_validation,
        "resource_names": item.resource_names,
        "request_ids": item.request_ids,
        "metrics": metrics,
        "enabled_at": item.enabled_at,
        "last_synced_at": item.last_synced_at,
        "error_message": item.error_message,
    }


def _export_row(item: CampaignInstance, bundle: AccountTestBundle, batch: LaunchBatch) -> dict:
    targeting = item.targeting or {}
    return {
        "Launch Batch": batch.name,
        "Launch Group": bundle.account_name,
        "Account": bundle.account_name,
        "Customer ID": item.customer_id,
        "Currency": item.currency_code,
        "Time zone": bundle.time_zone,
        "Sequence": item.campaign_sequence,
        "Campaign": item.campaign_name,
        "Budget": item.budget_micros / 1_000_000,
        "Bidding": (item.bidding or {}).get("strategy"),
        "Target CPA/ROAS": (item.bidding or {}).get("target_cpa") or (item.bidding or {}).get("target_roas"),
        "Geo": ", ".join(targeting.get("location_ids") or []),
        "Language": ", ".join(targeting.get("language_ids") or []),
        "Audience": ", ".join(targeting.get("audience_resource_names") or []),
        "Channels": (targeting.get("channel_controls") or {}).get("mode", "ALL_CHANNELS"),
        "Final URL": (item.url_settings or {}).get("final_url"),
        "Creative set": (item.creative_assignment or {}).get("set_key"),
        "Media count": len((item.creative_assignment or {}).get("media_ids") or []),
        "Validation": "VALID" if (item.local_validation or {}).get("valid") else "PENDING",
    }


def _recalculate_financial(db: Session, batch_id: UUID) -> dict:
    batch = db.get(LaunchBatch, batch_id)
    instances = _instances(db, batch_id)
    payload = [
        {
            "customer_id": item.customer_id,
            "account_test_bundle_id": str(item.account_test_bundle_id),
            "currency_code": item.currency_code,
            "budget_micros": item.budget_micros,
            "included": item.included,
        }
        for item in instances
    ]
    return build_financial_preview(payload, (batch.builder_config or {}).get("budget") or {})


def _instance_key_payload(item: CampaignInstance) -> dict:
    return {
        "id": str(item.id),
        "launch_batch_id": str(item.launch_batch_id),
        "account_test_bundle_id": str(item.account_test_bundle_id),
        "customer_id": item.customer_id,
        "campaign_sequence": item.campaign_sequence,
        "template_version_id": str(item.template_version_id) if item.template_version_id else None,
        "campaign_name": item.campaign_name,
        "budget_micros": item.budget_micros,
        "bidding": item.bidding,
        "targeting": item.targeting,
        "url_settings": item.url_settings,
        "texts": item.texts,
        "creative_assignment": item.creative_assignment,
    }


def _guardrails(db: Session) -> dict:
    item = db.scalar(select(ApplicationSetting).where(ApplicationSetting.key == "campaign_builder_guardrails"))
    return deep_merge(DEFAULT_GUARDRAILS, item.value if item else {})


def _budget_guardrail_exceeded(financial: dict, guardrails: dict) -> bool:
    maximums = guardrails.get("max_budget_by_currency") or {}
    for row in financial.get("by_currency") or []:
        limit = maximums.get(row["currency_code"])
        if limit is not None and Decimal(row["assigned"]) > Decimal(str(limit)):
            return True
    return False


def _password_ok(user: User, value: str | None) -> bool:
    return bool(value and verify_password(value, user.password_hash))


def _optional_micros(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(Decimal(str(value)) * Decimal(1_000_000))


def _get_batch(db: Session, batch_id: UUID) -> LaunchBatch:
    item = db.get(LaunchBatch, batch_id)
    if not item:
        raise HTTPException(status_code=404, detail="Launch Batch не найден")
    return item


def _get_instance(db: Session, instance_id: UUID) -> CampaignInstance:
    item = db.get(CampaignInstance, instance_id)
    if not item:
        raise HTTPException(status_code=404, detail="Campaign Instance не найден")
    return item


def _bundles(db: Session, batch_id: UUID) -> list[AccountTestBundle]:
    return list(
        db.scalars(
            select(AccountTestBundle)
            .where(AccountTestBundle.launch_batch_id == batch_id)
            .order_by(AccountTestBundle.account_name)
        ).all()
    )


def _instances(db: Session, batch_id: UUID) -> list[CampaignInstance]:
    return list(
        db.scalars(
            select(CampaignInstance)
            .where(CampaignInstance.launch_batch_id == batch_id)
            .order_by(CampaignInstance.customer_id, CampaignInstance.campaign_sequence)
        ).all()
    )
