from __future__ import annotations

import hashlib
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import utcnow
from app.db.models import (
    AuditLog,
    CampaignUpload,
    DeploymentPlan,
    GoogleConnection,
    GoogleTestAcceptanceRun,
    MediaAsset,
    PlanStatus,
    UploadStatus,
)
from app.domain.planner import build_plan_snapshot, validate_plan_snapshot
from app.domain.scheduling import snapshot_fingerprint
from app.domain_validation.persistence import validate_snapshot
from app.domain_validation.service import filter_blocked_campaigns
from app.google_ads.execution_guard import refresh_google_test_snapshot_targets
from app.google_ads.service import build_google_ads_adapter

ACCEPTANCE_VIDEO_ID = "dQw4w9WgXcQ"
ACCEPTANCE_LOGO_FILENAME = "google-test-acceptance-logo.png"
ACCEPTANCE_LOGO_STORAGE_KEY = f"google-test-fixtures/{ACCEPTANCE_LOGO_FILENAME}"
DEMAND_GEN_PURPOSE = "DEMAND_GEN"
CONTROL_CENTER_PURPOSE = "CONTROL_CENTER"


def run_demand_gen_acceptance(
    db: Session,
    connection: GoogleConnection,
    customer_id: str,
    created_by_id: UUID,
    *,
    purpose: str = DEMAND_GEN_PURPOSE,
) -> GoogleTestAcceptanceRun:
    adapter = build_google_ads_adapter(db, connection)
    run = db.scalar(
        select(GoogleTestAcceptanceRun).where(
            GoogleTestAcceptanceRun.connection_id == connection.id,
            GoogleTestAcceptanceRun.customer_id == customer_id,
            GoogleTestAcceptanceRun.purpose == purpose,
        )
    )
    if run is not None and run.status == "SUCCEEDED":
        campaign_resource_name = _campaign_resource_name(run.resource_names)
        if campaign_resource_name:
            readback = adapter.read_demand_gen_resources(
                customer_id,
                campaign_resource_name,
                list(run.resource_names or []),
            )
            if all(readback["verified"].values()):
                run.readback = readback
                run.request_ids = _unique(
                    [*(run.request_ids or []), *(readback.get("request_ids") or [])]
                )
                db.commit()
                return run

    fixture_name = (
        run.fixture_name
        if run is not None
        else f"API_TEST_ACCEPTANCE_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
    )
    if run is None:
        run = GoogleTestAcceptanceRun(
            connection_id=connection.id,
            customer_id=customer_id,
            purpose=purpose,
            fixture_name=fixture_name,
            status="PENDING",
            resource_names=[],
            request_ids=[],
            readback={},
        )
        db.add(run)
        db.flush()

    run.status = "RUNNING"
    run.started_at = utcnow()
    run.completed_at = None
    run.last_error = None
    media = _acceptance_media(db, created_by_id)
    upload = _acceptance_upload(
        connection,
        customer_id,
        fixture_name,
        media,
        created_by_id,
    )
    db.add(upload)
    db.flush()
    run.upload_id = upload.id

    snapshot, _initial_fingerprint = build_plan_snapshot(
        upload, media, "GOOGLE_TEST"
    )
    snapshot["campaigns"][0]["create_audience"] = {
        "name": f"{fixture_name}_AUDIENCE",
        "description": "Neutral Google Test acceptance audience",
    }
    snapshot["domain_validation"] = validate_snapshot(
        snapshot,
        cached_report={},
        force=True,
    )
    executable_snapshot, blocked = filter_blocked_campaigns(
        snapshot, snapshot["domain_validation"]
    )
    if blocked or not executable_snapshot.get("campaigns"):
        raise RuntimeError("Acceptance Final URL не прошёл обязательную проверку домена")
    local_validation = validate_plan_snapshot(executable_snapshot)
    if not local_validation["valid"]:
        raise RuntimeError(_validation_error(local_validation))
    fingerprint = snapshot_fingerprint(executable_snapshot)

    plan = DeploymentPlan(
        upload_id=upload.id,
        connection_id=connection.id,
        status=PlanStatus.READY.value,
        execution_mode="GOOGLE_TEST",
        fingerprint=fingerprint,
        snapshot=executable_snapshot,
        local_validation=local_validation,
        google_validation={},
        result={},
        request_ids=[],
        resource_names=[],
        created_by_id=created_by_id,
    )
    db.add(plan)
    db.flush()
    run.plan_id = plan.id
    confirmation_time = utcnow()
    try:
        read_request_ids = refresh_google_test_snapshot_targets(
            db,
            connection,
            adapter,
            executable_snapshot,
            require_confirmation=False,
        )
        validation = adapter.validate_plan(executable_snapshot)
        validation_request_ids = _unique(
            [*read_request_ids, *validation.request_ids]
        )
        plan.request_ids = validation_request_ids
        run.request_ids = _unique(
            [*(run.request_ids or []), *validation_request_ids]
        )
        plan.google_validation = validation.__dict__
        if not validation.ok:
            raise RuntimeError(_execution_error(validation.errors))
        plan.validated_at = utcnow()
        plan.confirmed_at = confirmation_time
        plan.status = PlanStatus.VALIDATED.value

        guard_request_ids = refresh_google_test_snapshot_targets(
            db,
            connection,
            adapter,
            executable_snapshot,
            confirmed_at=confirmation_time,
            require_confirmation=True,
        )
        deployment = adapter.deploy_plan(executable_snapshot)
        mutation_request_ids = _unique(
            [
                *validation_request_ids,
                *guard_request_ids,
                *deployment.request_ids,
            ]
        )
        plan.request_ids = mutation_request_ids
        run.request_ids = _unique(
            [*(run.request_ids or []), *mutation_request_ids]
        )
        if not deployment.ok:
            raise RuntimeError(_execution_error(deployment.errors))
        campaign_resource_name = _campaign_resource_name(
            deployment.resource_names
        )
        if not campaign_resource_name:
            raise RuntimeError("Google Ads не вернул resource name созданной кампании")
        all_resources = _unique(
            [*(run.resource_names or []), *deployment.resource_names]
        )
        plan.resource_names = all_resources
        run.resource_names = all_resources
        readback = adapter.read_demand_gen_resources(
            customer_id,
            campaign_resource_name,
            all_resources,
        )
        failed_checks = [
            key for key, value in readback["verified"].items() if not value
        ]
        if failed_checks:
            raise RuntimeError(
                "Повторное чтение не подтвердило ресурсы: "
                + ", ".join(failed_checks)
            )

        request_ids = _unique(
            [
                *mutation_request_ids,
                *(readback.get("request_ids") or []),
            ]
        )
        plan.result = deployment.__dict__
        plan.request_ids = request_ids
        plan.resource_names = all_resources
        plan.status = PlanStatus.SUCCEEDED.value
        plan.completed_at = utcnow()
        upload.status = UploadStatus.SUCCEEDED.value
        run.resource_names = all_resources
        run.request_ids = request_ids
        run.readback = readback
        run.status = "SUCCEEDED"
        run.completed_at = utcnow()
        db.add(
            AuditLog(
                created_at=utcnow(),
                actor_user_id=created_by_id,
                action="google_test.acceptance.demand_gen.complete",
                entity_type="google_test_acceptance_run",
                entity_id=str(run.id),
                summary={
                    "customer_id": customer_id,
                    "purpose": purpose,
                    "request_ids": request_ids,
                    "resource_names": all_resources,
                    "readback_verified": True,
                },
            )
        )
        db.commit()
        db.refresh(run)
        return run
    except Exception as exc:
        run.status = "FAILED"
        run.last_error = str(exc)
        run.completed_at = utcnow()
        plan.status = PlanStatus.FAILED.value
        plan.result = {
            "ok": False,
            "errors": [
                {"code": exc.__class__.__name__, "message": str(exc)}
            ],
        }
        upload.status = UploadStatus.FAILED.value
        upload.last_error = str(exc)
        db.commit()
        raise


def run_control_center_acceptance(
    db: Session,
    connection: GoogleConnection,
    customer_id: str,
    created_by_id: UUID,
) -> GoogleTestAcceptanceRun:
    run = run_demand_gen_acceptance(
        db,
        connection,
        customer_id,
        created_by_id,
        purpose=CONTROL_CENTER_PURPOSE,
    )
    campaign_resource_name = _campaign_resource_name(run.resource_names)
    if not campaign_resource_name:
        raise RuntimeError("Acceptance campaign resource name отсутствует")
    adapter = build_google_ads_adapter(db, connection)
    request_ids = list(run.request_ids or [])
    steps: list[dict] = []
    run.status = "RUNNING"
    run.started_at = utcnow()
    run.completed_at = None
    run.last_error = None
    db.commit()
    try:
        for target_status in ("ENABLED", "PAUSED"):
            guard_request_ids = refresh_google_test_snapshot_targets(
                db,
                connection,
                adapter,
                {
                    "campaigns": [{"customer_id": customer_id}],
                },
                confirmed_at=utcnow(),
                require_confirmation=True,
            )
            before = adapter.read_control_center_campaign(
                customer_id, campaign_resource_name
            )
            validation = adapter.validate_campaign_status(
                customer_id,
                [{"resource_name": campaign_resource_name}],
                target_status,
            )
            request_ids.extend(validation.request_ids)
            if not validation.ok:
                raise RuntimeError(_execution_error(validation.errors))
            mutation = adapter.change_campaign_status(
                customer_id,
                [{"resource_name": campaign_resource_name}],
                target_status,
            )
            request_ids.extend(mutation.request_ids)
            if not mutation.ok:
                raise RuntimeError(_execution_error(mutation.errors))
            after = adapter.read_control_center_campaign(
                customer_id, campaign_resource_name
            )
            if after.get("status") != target_status:
                raise RuntimeError(
                    f"Readback ожидал {target_status}, получил {after.get('status')}"
                )
            step_request_ids = _unique(
                [
                    *guard_request_ids,
                    *(before.get("_request_ids") or []),
                    *validation.request_ids,
                    *mutation.request_ids,
                    *(after.get("_request_ids") or []),
                ]
            )
            request_ids.extend(step_request_ids)
            steps.append(
                {
                    "action": target_status,
                    "before": before.get("status"),
                    "after": after.get("status"),
                    "verified": True,
                    "request_ids": step_request_ids,
                }
            )

        budget_guard_request_ids = refresh_google_test_snapshot_targets(
            db,
            connection,
            adapter,
            {
                "campaigns": [{"customer_id": customer_id}],
            },
            confirmed_at=utcnow(),
            require_confirmation=True,
        )
        before_budget = adapter.read_control_center_campaign(
            customer_id, campaign_resource_name
        )
        target_budget = 11_000_000
        budget_validation = adapter.change_campaign_budget(
            customer_id,
            before_budget["budget_resource_name"],
            target_budget,
            validate_only=True,
        )
        request_ids.extend(budget_validation.request_ids)
        if not budget_validation.ok:
            raise RuntimeError(_execution_error(budget_validation.errors))
        budget_mutation = adapter.change_campaign_budget(
            customer_id,
            before_budget["budget_resource_name"],
            target_budget,
            validate_only=False,
        )
        request_ids.extend(budget_mutation.request_ids)
        if not budget_mutation.ok:
            raise RuntimeError(_execution_error(budget_mutation.errors))
        after_budget = adapter.read_control_center_campaign(
            customer_id, campaign_resource_name
        )
        if after_budget.get("budget_micros") != target_budget:
            raise RuntimeError(
                "Повторное чтение не подтвердило изменение бюджета Google Test"
            )
        budget_request_ids = _unique(
            [
                *budget_guard_request_ids,
                *(before_budget.get("_request_ids") or []),
                *budget_validation.request_ids,
                *budget_mutation.request_ids,
                *(after_budget.get("_request_ids") or []),
            ]
        )
        steps.append(
            {
                "action": "SET_BUDGET",
                "before": before_budget.get("budget_micros"),
                "after": after_budget.get("budget_micros"),
                "verified": True,
                "request_ids": budget_request_ids,
            }
        )
        request_ids.extend(budget_request_ids)
        run.request_ids = _unique(request_ids)
        run.readback = {**(run.readback or {}), "control_center_steps": steps}
        run.status = "SUCCEEDED"
        run.completed_at = utcnow()
        db.add(
            AuditLog(
                created_at=utcnow(),
                actor_user_id=created_by_id,
                action="google_test.acceptance.control_center.complete",
                entity_type="google_test_acceptance_run",
                entity_id=str(run.id),
                summary={
                    "customer_id": customer_id,
                    "request_ids": run.request_ids,
                    "steps": steps,
                },
            )
        )
        db.commit()
        db.refresh(run)
        return run
    except Exception as exc:
        run.request_ids = _unique(request_ids)
        run.readback = {
            **(run.readback or {}),
            "control_center_steps": steps,
        }
        run.status = "FAILED"
        run.last_error = str(exc)
        run.completed_at = utcnow()
        db.add(
            AuditLog(
                created_at=utcnow(),
                actor_user_id=created_by_id,
                action="google_test.acceptance.control_center.failed",
                entity_type="google_test_acceptance_run",
                entity_id=str(run.id),
                summary={
                    "customer_id": customer_id,
                    "request_ids": run.request_ids,
                    "completed_steps": steps,
                    "error": str(exc),
                },
            )
        )
        db.commit()
        raise


def _acceptance_media(db: Session, created_by_id: UUID) -> list[MediaAsset]:
    return [
        _acceptance_video_media(db, created_by_id),
        _acceptance_logo_media(db, created_by_id),
    ]


def _acceptance_video_media(db: Session, created_by_id: UUID) -> MediaAsset:
    sha256 = hashlib.sha256(ACCEPTANCE_VIDEO_ID.encode()).hexdigest()
    media = db.scalar(
        select(MediaAsset).where(
            MediaAsset.kind == "YOUTUBE",
            MediaAsset.sha256 == sha256,
        )
    )
    if media is not None:
        return media
    media = MediaAsset(
        kind="YOUTUBE",
        source="GOOGLE_TEST_FIXTURE",
        name="Google Test acceptance video",
        sha256=sha256,
        size_bytes=0,
        status="READY",
        validation={
            "valid": True,
            "fixture": True,
            "google_test_only": True,
        },
        youtube_video_id=ACCEPTANCE_VIDEO_ID,
        google_asset_resources={},
        details={"fixture": "GOOGLE_TEST_ACCEPTANCE"},
        created_by_id=created_by_id,
    )
    db.add(media)
    db.flush()
    return media


def _acceptance_logo_media(db: Session, created_by_id: UUID) -> MediaAsset:
    fixture_path = Path(__file__).with_name("fixtures") / ACCEPTANCE_LOGO_FILENAME
    image_bytes = fixture_path.read_bytes()
    sha256 = hashlib.sha256(image_bytes).hexdigest()
    storage_path = settings.storage_root / ACCEPTANCE_LOGO_STORAGE_KEY
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    if not storage_path.exists() or hashlib.sha256(storage_path.read_bytes()).hexdigest() != sha256:
        shutil.copyfile(fixture_path, storage_path)

    media = db.scalar(
        select(MediaAsset).where(
            MediaAsset.kind == "IMAGE",
            MediaAsset.sha256 == sha256,
        )
    )
    if media is not None:
        return media
    media = MediaAsset(
        kind="IMAGE",
        source="GOOGLE_TEST_FIXTURE",
        name="Google Test acceptance logo",
        sha256=sha256,
        storage_key=ACCEPTANCE_LOGO_STORAGE_KEY,
        content_type="image/png",
        size_bytes=len(image_bytes),
        width=1254,
        height=1254,
        aspect_ratio=1.0,
        status="READY",
        validation={
            "valid": True,
            "fixture": True,
            "google_test_only": True,
            "role": "SQUARE",
        },
        google_asset_resources={},
        details={
            "fixture": "GOOGLE_TEST_ACCEPTANCE",
            "generated_for": "isolated_google_test_only",
        },
        created_by_id=created_by_id,
    )
    db.add(media)
    db.flush()
    return media


def _acceptance_upload(
    connection: GoogleConnection,
    customer_id: str,
    fixture_name: str,
    media: list[MediaAsset],
    created_by_id: UUID,
) -> CampaignUpload:
    return CampaignUpload(
        name=fixture_name,
        status=UploadStatus.DRAFT.value,
        source_type="MANUAL",
        source_name="GOOGLE_TEST_ACCEPTANCE",
        source_rows=[],
        draft={
            "execution_mode": "GOOGLE_TEST",
            "customer_id": customer_id,
            "campaign": {
                "customer_id": customer_id,
                "campaign_name": fixture_name,
                "ad_group_name": f"{fixture_name}_AD_GROUP",
                "final_url": "https://example.com/",
                "ad_type": "VIDEO",
                "daily_budget": "10",
                "bidding_strategy": "MAXIMIZE_CLICKS",
                "business_name": "API Test",
                "headlines": ["API test headline"],
                "long_headline": "Neutral Google Ads API test campaign",
                "descriptions": ["Created only in a Google Ads test account"],
                "youtube_video_id": ACCEPTANCE_VIDEO_ID,
                "media_ids": [str(item.id) for item in media],
                "location_ids": ["2840"],
                "language_ids": ["1000"],
                "optimized_targeting": False,
            },
        },
        current_step=18,
        connection_id=connection.id,
        created_by_id=created_by_id,
    )


def _campaign_resource_name(resource_names: list[str] | None) -> str | None:
    return next(
        (
            str(item)
            for item in resource_names or []
            if "/campaigns/" in str(item)
        ),
        None,
    )


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if value))


def _execution_error(errors: list[dict]) -> str:
    return "; ".join(
        f"{item.get('code')}: {item.get('message')}" for item in errors
    )


def _validation_error(validation: dict) -> str:
    return "; ".join(
        f"{item.get('code')}: {item.get('message')}"
        for item in validation.get("errors") or []
    )
