from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from datetime import timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.gateway import AiProviderUnavailable, get_openai_api_key
from app.ai.orchestrator import fail_run, run_analysis
from app.ai.policy import effective_ai_settings, enforce_mode_for_role, require_ai_available, resolve_tool_context
from app.ai.providers import source_registry_payload
from app.ai.schemas import (
    AiAdminSettingsPatchIn,
    AiMessageIn,
    AiScope,
    ConversationCreateIn,
    ConversationPatchIn,
    DraftApplyIn,
    DraftPatchIn,
    GeoAnalyticsOverrideIn,
    GeoAnalyticsProfileIn,
    MetricSourceMappingIn,
    ModelProfilePatchIn,
    UserPreferencePatchIn,
    validate_draft_payload,
)
from app.ai.security import redact
from app.ai.tools import ToolRegistry
from app.api.deps import get_current_user, require_csrf, require_role
from app.control_center.schemas import ActionPreviewIn
from app.core.config import settings
from app.core.database import get_db
from app.core.security import encrypt_json, utcnow
from app.db.models import (
    AccountNoteHistory,
    AccountTag,
    AccountTagHistory,
    AccountWorkStatusHistory,
    AiAdminSetting,
    AiConversation,
    AiDraft,
    AiMessage,
    AiModelProfile,
    AiRun,
    AiRunStatus,
    AiSavedReport,
    AiToolCall,
    AiUsageDaily,
    AiUserPreference,
    ControlCenterActionRequest,
    ControlCenterEvent,
    ControlCenterRule,
    ControlCenterSavedView,
    ControlCenterTag,
    CustomerAccount,
    DeploymentPlan,
    GeoAnalyticsOverride,
    GeoAnalyticsProfile,
    GeoAnalyticsProfileHistory,
    MetricSourceMapping,
    User,
    UserRole,
)
from app.domain.audit import record_audit

router = APIRouter(prefix="/ai", tags=["ai-analyst"])
ALLOWED_AUDIO_TYPES = {
    "audio/webm",
    "audio/ogg",
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp4",
    "audio/x-m4a",
}


@router.get("/capabilities")
def ai_capabilities(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    gates = effective_ai_settings(db)
    stored = db.scalar(select(AiAdminSetting).where(AiAdminSetting.key == "global"))
    profiles = list(db.scalars(select(AiModelProfile).order_by(AiModelProfile.name)).all())
    registry = ToolRegistry()
    return {
        "enabled": bool(gates["enabled"]),
        "kill_switch": bool(gates["kill_switch"]),
        "provider": {
            "name": "OPENAI_RESPONSES_API",
            "configured": bool(settings.openai_api_key or (stored and stored.openai_key_encrypted)),
            "key_source": "SERVER_ENV"
            if settings.openai_api_key
            else "ENCRYPTED_SERVER_SETTING"
            if stored and stored.openai_key_encrypted
            else "NOT_CONFIGURED",
            "store": False,
            "live_model_access_verified": False,
        },
        "role": user.role,
        "authority_modes": ["READ_ONLY"]
        if user.role == UserRole.VIEWER.value
        else ["READ_ONLY", "DRAFT_ONLY", "CONFIRM_REQUIRED"],
        "environments": ["SIMULATION", "GOOGLE_TEST", "PRODUCTION"],
        "production": {
            "read_enabled": bool(gates["production_read_enabled"]),
            "actions_enabled": bool(gates["production_actions_enabled"]),
            "control_center_live_actions_enabled": settings.control_center_live_actions_enabled,
        },
        "models": [_model_profile_payload(item) for item in profiles],
        "tools": [{"name": item.name, "risk": item.risk.value, "version": item.version} for item in registry.specs],
        "limits": {
            "model_turns": settings.ai_max_model_turns,
            "read_tool_calls": settings.ai_max_read_tool_calls,
            "draft_tool_calls": settings.ai_max_draft_tool_calls,
            "rows_per_tool": settings.ai_max_rows_per_tool,
            "date_range_days": settings.ai_max_date_range_days,
            "timeout_seconds": settings.ai_interactive_timeout_seconds,
            "retention_days": int(gates["retention_days"]),
            "voice_seconds": settings.ai_voice_max_seconds,
            "voice_bytes": settings.ai_voice_max_bytes,
        },
    }


@router.get("/source-registry")
def ai_source_registry(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[dict[str, Any]]:
    del user
    return source_registry_payload(db)


@router.get("/conversations")
def list_conversations(
    archived: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    query = select(AiConversation).where(
        AiConversation.owner_user_id == user.id,
        AiConversation.deleted_at.is_(None),
        AiConversation.archived_at.is_not(None) if archived else AiConversation.archived_at.is_(None),
    )
    items = list(
        db.scalars(
            query.order_by(desc(AiConversation.last_message_at), desc(AiConversation.created_at)).limit(200)
        ).all()
    )
    return [_conversation_payload(item) for item in items]


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: User = Depends(require_csrf),
) -> dict[str, Any]:
    gates = effective_ai_settings(db)
    enforce_mode_for_role(user.role, payload.authority_mode.value, payload.google_environment.value, gates)
    item = AiConversation(
        owner_user_id=user.id,
        title=payload.title.strip(),
        authority_mode=payload.authority_mode.value,
        google_environment=payload.google_environment.value,
        scope=payload.scope.model_dump(mode="json"),
        locale=payload.locale,
        time_zone=payload.time_zone,
        retention_until=utcnow() + timedelta(days=int(gates["retention_days"])),
    )
    db.add(item)
    db.flush()
    record_audit(
        db,
        request,
        user,
        "ai.conversation.create",
        "ai_conversation",
        str(item.id),
        {"authority_mode": item.authority_mode, "environment": item.google_environment},
    )
    db.commit()
    db.refresh(item)
    return _conversation_payload(item)


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    item = _owned_conversation(db, conversation_id, user)
    messages = list(
        db.scalars(select(AiMessage).where(AiMessage.conversation_id == item.id).order_by(AiMessage.created_at)).all()
    )
    run_ids = [message.run_id for message in messages if message.run_id]
    tool_calls = (
        list(db.scalars(select(AiToolCall).where(AiToolCall.run_id.in_(run_ids)).order_by(AiToolCall.created_at)).all())
        if run_ids
        else []
    )
    calls_by_run: dict[UUID, list[dict[str, Any]]] = {}
    for call in tool_calls:
        calls_by_run.setdefault(call.run_id, []).append(_tool_call_payload(call))
    return {
        **_conversation_payload(item),
        "messages": [
            _message_payload(message, calls_by_run.get(message.run_id, []) if message.run_id else [])
            for message in messages
        ],
    }


@router.patch("/conversations/{conversation_id}")
def patch_conversation(
    conversation_id: UUID,
    payload: ConversationPatchIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: User = Depends(require_csrf),
) -> dict[str, Any]:
    item = _owned_conversation(db, conversation_id, user)
    changes = payload.model_dump(exclude_unset=True)
    authority = changes.get("authority_mode", item.authority_mode)
    environment = changes.get("google_environment", item.google_environment)
    authority_value = authority.value if hasattr(authority, "value") else authority
    environment_value = environment.value if hasattr(environment, "value") else environment
    enforce_mode_for_role(user.role, authority_value, environment_value, effective_ai_settings(db))
    if "title" in changes:
        item.title = str(changes["title"]).strip()
    if "authority_mode" in changes:
        item.authority_mode = authority_value
    if "google_environment" in changes:
        item.google_environment = environment_value
    if "scope" in changes:
        item.scope = (
            changes["scope"].model_dump(mode="json") if hasattr(changes["scope"], "model_dump") else changes["scope"]
        )
    if "archived" in changes:
        item.archived_at = utcnow() if changes["archived"] else None
    record_audit(
        db, request, user, "ai.conversation.update", "ai_conversation", str(item.id), {"fields": sorted(changes)}
    )
    db.commit()
    db.refresh(item)
    return _conversation_payload(item)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: User = Depends(require_csrf),
) -> None:
    item = _owned_conversation(db, conversation_id, user)
    item.deleted_at = utcnow()
    item.retention_until = utcnow()
    record_audit(db, request, user, "ai.conversation.delete", "ai_conversation", str(item.id), {"soft_delete": True})
    db.commit()


@router.get("/conversations/{conversation_id}/export")
def export_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JSONResponse:
    item = _owned_conversation(db, conversation_id, user)
    messages = list(
        db.scalars(select(AiMessage).where(AiMessage.conversation_id == item.id).order_by(AiMessage.created_at)).all()
    )
    response = JSONResponse(
        jsonable_encoder({
            "conversation": _conversation_payload(item),
            "messages": [_message_payload(message, []) for message in messages],
        })
    )
    response.headers["Content-Disposition"] = f'attachment; filename="axyro-ai-{item.id}.json"'
    return response


@router.post("/conversations/{conversation_id}/messages/stream")
def stream_message(
    conversation_id: UUID,
    payload: AiMessageIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: User = Depends(require_csrf),
) -> StreamingResponse:
    conversation = _owned_conversation(db, conversation_id, user)
    require_ai_available(db)
    request_id = hashlib.sha256(f"{user.id}:{conversation.id}:{payload.idempotency_key}".encode()).hexdigest()
    existing = db.scalar(select(AiRun).where(AiRun.request_id == request_id))
    if existing:
        existing_message = db.scalar(
            select(AiMessage).where(AiMessage.run_id == existing.id, AiMessage.role == "ASSISTANT")
        )
        return StreamingResponse(
            _replay_stream(existing, existing_message),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    db.add(
        AiMessage(
            conversation_id=conversation.id,
            user_id=user.id,
            role="USER",
            content=payload.content,
            structured_content={},
            evidence=[],
            status="COMPLETE",
        )
    )
    run = AiRun(
        conversation_id=conversation.id,
        user_id=user.id,
        request_id=request_id,
        status=AiRunStatus.QUEUED.value,
        model_profile=payload.model_profile,
        prompt_version="ai-analyst-v1",
        tool_schema_version="axyro-tools-v1",
        authority_mode=conversation.authority_mode,
        google_environment=conversation.google_environment,
        resolved_scope={},
    )
    db.add(run)
    db.flush()
    session = getattr(request.state, "user_session", None)
    if not session:
        raise HTTPException(status_code=401, detail="Сессия недействительна")
    context = resolve_tool_context(
        db,
        user=user,
        session_id=session.id,
        scope=AiScope.model_validate(conversation.scope or {}),
        authority_mode=conversation.authority_mode,
        google_environment=conversation.google_environment,
        request_id=request_id,
        ai_run_id=run.id,
        deadline=utcnow() + timedelta(seconds=settings.ai_interactive_timeout_seconds),
        locale=conversation.locale,
        time_zone=conversation.time_zone,
    )
    run.resolved_scope = context.public_scope()
    conversation.last_message_at = utcnow()
    conversation.retention_until = utcnow() + timedelta(days=int(effective_ai_settings(db)["retention_days"]))
    if conversation.title == "Новый диалог":
        conversation.title = payload.content[:80]
    db.commit()

    def generate():
        yield _sse("connected", {"run_id": str(run.id), "status": "RUNNING"})
        timeline: list[tuple[str, dict[str, Any]]] = []
        try:
            answer = run_analysis(
                db,
                context,
                payload.content,
                payload.model_profile,
                emit=lambda event, data: timeline.append((event, data)),
            )
            for event, data in timeline:
                yield _sse(event, data)
            text = answer.answer
            for index in range(0, len(text), 80):
                yield _sse("message.delta", {"text": text[index : index + 80]})
            yield _sse("message.completed", answer.model_dump(mode="json"))
        except Exception as exc:
            current = db.get(AiRun, run.id)
            if current:
                fail_run(db, current, exc)
            code = getattr(exc, "code", exc.__class__.__name__)
            message = (
                "OpenAI API key не настроен на сервере. Аналитик готов, но live-запросы пока заблокированы."
                if isinstance(exc, AiProviderUnavailable)
                else str(redact(str(exc)))
            )
            yield _sse("run.error", {"code": code, "message": message})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/runs/{run_id}/cancel")
def cancel_run(
    run_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: User = Depends(require_csrf),
) -> dict[str, Any]:
    run = db.get(AiRun, run_id)
    if not run or (run.user_id != user.id and user.role != UserRole.ADMIN.value):
        raise HTTPException(status_code=404, detail="Запуск не найден")
    run.cancel_requested = True
    record_audit(db, request, user, "ai.run.cancel", "ai_run", str(run.id), {})
    db.commit()
    return {"id": str(run.id), "cancel_requested": True}


@router.get("/drafts")
def list_drafts(
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    query = select(AiDraft).where(AiDraft.owner_user_id == user.id)
    if status_filter:
        query = query.where(AiDraft.status == status_filter)
    items = list(db.scalars(query.order_by(desc(AiDraft.created_at)).limit(200)).all())
    return [_draft_payload(item) for item in items]


@router.patch("/drafts/{draft_id}")
def patch_draft(
    draft_id: UUID,
    payload: DraftPatchIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: User = Depends(require_csrf),
) -> dict[str, Any]:
    draft = _owned_draft(db, draft_id, user)
    _require_editable_draft(draft, payload.expected_version)
    try:
        validated = validate_draft_payload(draft.draft_type, payload.payload)
        _validate_draft_targets(draft, validated)
        draft.payload = redact(validated)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"AI_DRAFT_INVALID: {exc}") from exc
    draft.version += 1
    draft.fingerprint = _draft_fingerprint(draft.draft_type, draft.payload, draft.scope, draft.version)
    record_audit(db, request, user, "ai.draft.update", "ai_draft", str(draft.id), {"version": draft.version})
    db.commit()
    db.refresh(draft)
    return _draft_payload(draft)


@router.post("/drafts/{draft_id}/apply")
def apply_draft(
    draft_id: UUID,
    payload: DraftApplyIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
    _: User = Depends(require_csrf),
) -> dict[str, Any]:
    draft = _owned_draft(db, draft_id, user)
    _require_editable_draft(draft, payload.expected_version, payload.fingerprint)
    result = _apply_local_draft(db, draft, user)
    draft.status = "APPLIED" if result.get("applied") else "OPENED_IN_EDITOR"
    record_audit(
        db, request, user, "ai.draft.apply", "ai_draft", str(draft.id), {"draft_type": draft.draft_type, **result}
    )
    db.commit()
    return {**_draft_payload(draft), "result": result}


@router.post("/drafts/{draft_id}/preview", status_code=status.HTTP_201_CREATED)
def create_preview_from_draft(
    draft_id: UUID,
    payload: DraftApplyIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
    _: User = Depends(require_csrf),
) -> dict[str, Any]:
    draft = _owned_draft(db, draft_id, user)
    _require_editable_draft(draft, payload.expected_version, payload.fingerprint)
    if draft.draft_type != "ACTION_SELECTION":
        raise HTTPException(status_code=409, detail="Этот черновик открывается в обычном редакторе Axyro")
    from app.api.routes.control_center import preview_action

    source = draft.payload or {}
    preview_input = ActionPreviewIn.model_validate(
        {
            "campaign_ids": source.get("campaign_ids") or [],
            "action_type": source.get("action_type"),
            "execution_mode": draft.google_environment,
            "amount_micros": source.get("amount_micros"),
        }
    )
    preview = preview_action(
        preview_input,
        request,
        db,
        user,
        user,
    )
    draft.action_request_id = UUID(preview["id"])
    action = db.get(ControlCenterActionRequest, draft.action_request_id)
    if action:
        action.requested_payload = {
            **(action.requested_payload or {}),
            "source": "AI_DRAFT",
            "ai_draft_id": str(draft.id),
        }
    draft.status = "PREVIEW_CREATED"
    db.commit()
    return {"draft": _draft_payload(draft), "preview": preview}


@router.delete("/drafts/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft(
    draft_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: User = Depends(require_csrf),
) -> None:
    draft = _owned_draft(db, draft_id, user)
    draft.status = "DELETED"
    record_audit(db, request, user, "ai.draft.delete", "ai_draft", str(draft.id), {})
    db.commit()


@router.get("/reports")
def list_reports(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    rows = list(
        db.scalars(
            select(AiSavedReport)
            .where(AiSavedReport.owner_user_id == user.id)
            .order_by(desc(AiSavedReport.created_at))
            .limit(200)
        ).all()
    )
    return [_report_payload(item) for item in rows]


@router.get("/reports/{report_id}/export")
def export_report(
    report_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JSONResponse:
    item = _owned_report(db, report_id, user)
    response = JSONResponse(jsonable_encoder(_report_payload(item)))
    response.headers["Content-Disposition"] = f'attachment; filename="axyro-ai-report-{item.id}.json"'
    return response


@router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(
    report_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: User = Depends(require_csrf),
) -> None:
    item = _owned_report(db, report_id, user)
    record_audit(db, request, user, "ai.report.delete", "ai_saved_report", str(item.id), {})
    db.delete(item)
    db.commit()


@router.get("/preferences")
def get_preferences(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    item = db.scalar(select(AiUserPreference).where(AiUserPreference.user_id == user.id))
    return _preference_payload(item, user)


@router.patch("/preferences")
def patch_preferences(
    payload: UserPreferencePatchIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: User = Depends(require_csrf),
) -> dict[str, Any]:
    item = db.scalar(select(AiUserPreference).where(AiUserPreference.user_id == user.id))
    if not item:
        item = AiUserPreference(user_id=user.id)
        db.add(item)
    changes = payload.model_dump(exclude_unset=True)
    authority = changes.get("default_authority_mode", item.default_authority_mode)
    environment = changes.get("default_environment", item.default_environment)
    enforce_mode_for_role(
        user.role,
        authority.value if hasattr(authority, "value") else authority,
        environment.value if hasattr(environment, "value") else environment,
        effective_ai_settings(db),
    )
    for key, value in changes.items():
        if key == "default_scope" and value is not None:
            value = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
        setattr(item, key, value.value if hasattr(value, "value") else value)
    record_audit(
        db, request, user, "ai.preferences.update", "ai_user_preference", str(user.id), {"fields": sorted(changes)}
    )
    db.commit()
    return _preference_payload(item, user)


@router.get("/admin/settings")
def get_admin_settings(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
) -> dict[str, Any]:
    del user
    return _admin_settings_payload(db)


@router.patch("/admin/settings")
def patch_admin_settings(
    payload: AiAdminSettingsPatchIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
    _: User = Depends(require_csrf),
) -> dict[str, Any]:
    item = db.scalar(select(AiAdminSetting).where(AiAdminSetting.key == "global"))
    if not item:
        item = AiAdminSetting(key="global", settings={}, updated_by_id=user.id)
        db.add(item)
    changes = payload.model_dump(exclude_unset=True)
    api_key = changes.pop("openai_api_key", None)
    clear_key = bool(changes.pop("clear_stored_openai_key", False))
    if api_key:
        item.openai_key_encrypted = encrypt_json({"api_key": api_key})
        item.openai_key_last_four = api_key[-4:]
    elif clear_key:
        item.openai_key_encrypted = None
        item.openai_key_last_four = None
    item.settings = {**(item.settings or {}), **changes}
    item.updated_by_id = user.id
    record_audit(
        db,
        request,
        user,
        "ai.admin_settings.update",
        "ai_admin_setting",
        "global",
        {"fields": sorted(changes), "key_replaced": bool(api_key), "key_cleared": clear_key},
    )
    db.commit()
    return _admin_settings_payload(db)


@router.patch("/admin/model-profiles/{profile_name}")
def patch_model_profile(
    profile_name: str,
    payload: ModelProfilePatchIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
    _: User = Depends(require_csrf),
) -> dict[str, Any]:
    item = db.scalar(select(AiModelProfile).where(AiModelProfile.name == profile_name.upper()))
    if not item:
        raise HTTPException(status_code=404, detail="Профиль модели не найден")
    changes = payload.model_dump(exclude_unset=True)
    new_model = changes.get("model_id")
    accepted_eval = changes.pop("accepted_eval_version", None)
    if new_model and new_model != item.model_id:
        if not accepted_eval or accepted_eval != item.eval_version or not item.eval_passed_at:
            raise HTTPException(
                status_code=409, detail="AI_MODEL_EVAL_REQUIRED: смена модели возможна только после успешного eval gate"
            )
    for key, value in changes.items():
        setattr(item, key, value)
    record_audit(
        db, request, user, "ai.model_profile.update", "ai_model_profile", str(item.id), {"fields": sorted(changes)}
    )
    db.commit()
    return _model_profile_payload(item)


@router.get("/admin/usage")
def get_usage(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
) -> dict[str, Any]:
    del user
    since = utcnow().date() - timedelta(days=days - 1)
    rows = list(
        db.scalars(select(AiUsageDaily).where(AiUsageDaily.usage_date >= since).order_by(AiUsageDaily.usage_date)).all()
    )
    user_ids = {item.user_id for item in rows}
    user_names = {
        user_id: username
        for user_id, username in db.execute(select(User.id, User.username).where(User.id.in_(user_ids))).all()
    } if user_ids else {}
    runs = list(db.scalars(select(AiRun).where(AiRun.created_at >= utcnow() - timedelta(days=days))).all())
    tool_calls = list(
        db.scalars(
            select(AiToolCall)
            .join(AiRun, AiRun.id == AiToolCall.run_id)
            .where(AiRun.created_at >= utcnow() - timedelta(days=days))
        ).all()
    )
    by_status: dict[str, int] = {}
    by_error: dict[str, int] = {}
    by_tool: dict[str, int] = {}
    for run in runs:
        by_status[run.status] = by_status.get(run.status, 0) + 1
        if run.error_code:
            by_error[run.error_code] = by_error.get(run.error_code, 0) + 1
    for tool_call in tool_calls:
        by_tool[tool_call.tool_name] = by_tool.get(tool_call.tool_name, 0) + 1
    latency_values = [item.latency_ms for item in runs if item.latency_ms is not None]
    return {
        "items": [
            {**_usage_payload(item), "user_name": user_names.get(item.user_id, str(item.user_id))}
            for item in rows
        ],
        "totals": {
            "requests": sum(item.requests for item in rows),
            "input_tokens": sum(item.input_tokens for item in rows),
            "output_tokens": sum(item.output_tokens for item in rows),
            "estimated_cost_usd": float(sum((Decimal(item.estimated_cost_usd or 0) for item in rows), Decimal(0))),
            "tool_calls": sum(item.tool_calls for item in rows),
            "errors": sum(item.errors for item in rows),
        },
        "budgets": {
            "daily_soft_usd": effective_ai_settings(db)["daily_soft_budget_usd"],
            "daily_hard_usd": effective_ai_settings(db)["daily_hard_budget_usd"],
            "monthly_hard_usd": effective_ai_settings(db)["monthly_hard_budget_usd"],
            "user_daily_hard_usd": effective_ai_settings(db)["user_daily_hard_budget_usd"],
            "user_monthly_hard_usd": effective_ai_settings(db)["user_monthly_hard_budget_usd"],
        },
        "run_health": {
            "average_latency_ms": round(sum(latency_values) / len(latency_values)) if latency_values else None,
            "by_status": by_status,
            "by_error_code": by_error,
            "tool_usage": by_tool,
        },
    }


@router.get("/usage")
def get_my_usage(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    since = utcnow().date() - timedelta(days=days - 1)
    rows = list(
        db.scalars(
            select(AiUsageDaily)
            .where(AiUsageDaily.usage_date >= since, AiUsageDaily.user_id == user.id)
            .order_by(AiUsageDaily.usage_date)
        ).all()
    )
    return {
        "items": [_usage_payload(item) for item in rows],
        "totals": {
            "requests": sum(item.requests for item in rows),
            "input_tokens": sum(item.input_tokens for item in rows),
            "output_tokens": sum(item.output_tokens for item in rows),
            "estimated_cost_usd": float(sum((Decimal(item.estimated_cost_usd or 0) for item in rows), Decimal(0))),
            "tool_calls": sum(item.tool_calls for item in rows),
            "errors": sum(item.errors for item in rows),
        },
    }


@router.get("/geo-profiles")
def list_geo_profiles(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict[str, Any]]:
    del user
    items = list(
        db.scalars(
            select(GeoAnalyticsProfile).order_by(
                GeoAnalyticsProfile.scope_type, GeoAnalyticsProfile.scope_id, desc(GeoAnalyticsProfile.version)
            )
        ).all()
    )
    return [_geo_profile_payload(item) for item in items]


@router.get("/geo-overrides")
def list_geo_overrides(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[dict[str, Any]]:
    del user
    items = list(
        db.scalars(
            select(GeoAnalyticsOverride).order_by(GeoAnalyticsOverride.scope_type, GeoAnalyticsOverride.scope_id)
        ).all()
    )
    return [_geo_override_payload(item) for item in items]


@router.post("/geo-profiles", status_code=status.HTTP_201_CREATED)
def create_geo_profile(
    payload: GeoAnalyticsProfileIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
    _: User = Depends(require_csrf),
) -> dict[str, Any]:
    existing = list(
        db.scalars(
            select(GeoAnalyticsProfile)
            .where(
                GeoAnalyticsProfile.scope_type == payload.scope_type, GeoAnalyticsProfile.scope_id == payload.scope_id
            )
            .order_by(desc(GeoAnalyticsProfile.version))
        ).all()
    )
    version = (existing[0].version + 1) if existing else 1
    for item in existing:
        if item.is_active:
            db.add(
                GeoAnalyticsProfileHistory(
                    profile_id=item.id,
                    version=item.version,
                    snapshot=json.loads(json.dumps(_geo_profile_payload(item), default=str)),
                    changed_by_id=user.id,
                    changed_at=utcnow(),
                )
            )
            item.is_active = False
    item = GeoAnalyticsProfile(**payload.model_dump(), version=version, is_active=True, created_by_id=user.id)
    db.add(item)
    db.flush()
    record_audit(
        db,
        request,
        user,
        "ai.geo_profile.create",
        "geo_analytics_profile",
        str(item.id),
        {"scope_type": item.scope_type, "version": item.version},
    )
    db.commit()
    return _geo_profile_payload(item)


@router.get("/geo-profiles/{profile_id}/history")
def geo_profile_history(
    profile_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[dict[str, Any]]:
    del user
    if not db.get(GeoAnalyticsProfile, profile_id):
        raise HTTPException(status_code=404, detail="GEO-профиль не найден")
    rows = list(
        db.scalars(
            select(GeoAnalyticsProfileHistory)
            .where(GeoAnalyticsProfileHistory.profile_id == profile_id)
            .order_by(desc(GeoAnalyticsProfileHistory.changed_at))
        ).all()
    )
    return [
        {
            "id": str(item.id),
            "version": item.version,
            "snapshot": item.snapshot,
            "changed_by_id": str(item.changed_by_id) if item.changed_by_id else None,
            "changed_at": item.changed_at,
        }
        for item in rows
    ]


@router.put("/geo-overrides/{scope_type}/{scope_id}")
def upsert_geo_override(
    scope_type: str,
    scope_id: UUID,
    payload: GeoAnalyticsOverrideIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
    _: User = Depends(require_csrf),
) -> dict[str, Any]:
    if payload.scope_type != scope_type.upper() or payload.scope_id != scope_id:
        raise HTTPException(status_code=422, detail="Scope в адресе и теле не совпадает")
    item = db.scalar(
        select(GeoAnalyticsOverride).where(
            GeoAnalyticsOverride.scope_type == payload.scope_type, GeoAnalyticsOverride.scope_id == payload.scope_id
        )
    )
    if not item:
        item = GeoAnalyticsOverride(scope_type=payload.scope_type, scope_id=payload.scope_id, updated_by_id=user.id)
        db.add(item)
    item.profile_id = payload.profile_id
    item.override_values = payload.override_values
    item.is_active = payload.is_active
    item.updated_by_id = user.id
    db.flush()
    record_audit(
        db,
        request,
        user,
        "ai.geo_override.update",
        "geo_analytics_override",
        str(item.id),
        {"scope_type": item.scope_type},
    )
    db.commit()
    return _geo_override_payload(item)


@router.get("/metric-source-mappings")
def list_metric_mappings(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict[str, Any]]:
    del user
    items = list(
        db.scalars(
            select(MetricSourceMapping).order_by(MetricSourceMapping.semantic_metric, MetricSourceMapping.provider)
        ).all()
    )
    return [_metric_mapping_payload(item) for item in items]


@router.post("/metric-source-mappings", status_code=status.HTTP_201_CREATED)
def create_metric_mapping(
    payload: MetricSourceMappingIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
    _: User = Depends(require_csrf),
) -> dict[str, Any]:
    item = MetricSourceMapping(
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        semantic_metric=payload.semantic_metric,
        provider=payload.provider,
        source_id=payload.source_id,
        source_name=payload.source_name,
        attribution_model=payload.attribution_model,
        is_active=payload.is_active,
        metadata_json=payload.metadata,
        created_by_id=user.id,
    )
    db.add(item)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Такое сопоставление уже существует") from exc
    record_audit(
        db,
        request,
        user,
        "ai.metric_mapping.create",
        "metric_source_mapping",
        str(item.id),
        {"semantic_metric": item.semantic_metric, "provider": item.provider},
    )
    db.commit()
    return _metric_mapping_payload(item)


@router.delete("/metric-source-mappings/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_metric_mapping(
    mapping_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
    _: User = Depends(require_csrf),
) -> None:
    item = db.get(MetricSourceMapping, mapping_id)
    if not item:
        raise HTTPException(status_code=404, detail="Сопоставление не найдено")
    item.is_active = False
    record_audit(db, request, user, "ai.metric_mapping.disable", "metric_source_mapping", str(item.id), {})
    db.commit()


@router.post("/transcribe")
def transcribe_audio(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: User = Depends(require_csrf),
) -> dict[str, Any]:
    require_ai_available(db)
    content_type = (file.content_type or "").split(";", 1)[0].lower()
    if content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(status_code=415, detail="AI_AUDIO_TYPE_UNSUPPORTED: неподдерживаемый формат записи")
    content = file.file.read(settings.ai_voice_max_bytes + 1)
    if len(content) > settings.ai_voice_max_bytes:
        raise HTTPException(status_code=413, detail="AI_AUDIO_TOO_LARGE: запись превышает 10 MB")
    if not content:
        raise HTTPException(status_code=422, detail="AI_AUDIO_EMPTY: запись пуста")
    suffix = os.path.splitext(file.filename or "voice.webm")[1][:10] or ".webm"
    duration = _audio_duration(content, suffix)
    if duration > settings.ai_voice_max_seconds:
        raise HTTPException(
            status_code=422, detail=f"AI_AUDIO_TOO_LONG: максимум {settings.ai_voice_max_seconds} секунд"
        )
    api_key = get_openai_api_key(db)
    if not api_key:
        raise HTTPException(status_code=503, detail="OPENAI_NOT_CONFIGURED: OpenAI API key не настроен")
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - packaging failure, not a runtime branch
        raise HTTPException(status_code=503, detail="OPENAI_SDK_UNAVAILABLE: OpenAI SDK не установлен") from exc
    try:
        result = OpenAI(api_key=api_key, timeout=settings.ai_interactive_timeout_seconds).audio.transcriptions.create(
            model=settings.ai_transcription_model,
            file=(f"voice{suffix}", content, content_type),
        )
    finally:
        content = b""
    text = str(redact(result.text)).strip()
    record_audit(
        db,
        request,
        user,
        "ai.voice.transcribe",
        "ai_transcription",
        None,
        {"duration_seconds": round(duration, 2), "characters": len(text), "raw_audio_retained": False},
    )
    db.commit()
    return {
        "transcript": text,
        "duration_seconds": duration,
        "editable": True,
        "sent_automatically": False,
        "raw_audio_retained": False,
    }


def _owned_conversation(db: Session, conversation_id: UUID, user: User) -> AiConversation:
    item = db.get(AiConversation, conversation_id)
    if not item or item.deleted_at or (item.owner_user_id != user.id and user.role != UserRole.ADMIN.value):
        raise HTTPException(status_code=404, detail="Диалог не найден")
    return item


def _owned_draft(db: Session, draft_id: UUID, user: User) -> AiDraft:
    item = db.get(AiDraft, draft_id)
    if not item or (item.owner_user_id != user.id and user.role != UserRole.ADMIN.value):
        raise HTTPException(status_code=404, detail="Черновик не найден")
    return item


def _owned_report(db: Session, report_id: UUID, user: User) -> AiSavedReport:
    item = db.get(AiSavedReport, report_id)
    if not item or (item.owner_user_id != user.id and user.role != UserRole.ADMIN.value):
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    return item


def _require_editable_draft(draft: AiDraft, expected_version: int, fingerprint: str | None = None) -> None:
    if draft.status not in {"EDITABLE", "READY_FOR_USER_PREVIEW"}:
        raise HTTPException(status_code=409, detail=f"Черновик уже имеет статус {draft.status}")
    if draft.expires_at < utcnow():
        draft.status = "EXPIRED"
        raise HTTPException(status_code=409, detail="AI_DRAFT_EXPIRED: создайте новый черновик")
    if draft.version != expected_version:
        raise HTTPException(status_code=409, detail="AI_DRAFT_VERSION_DRIFT: черновик был изменён")
    if fingerprint and draft.fingerprint != fingerprint:
        raise HTTPException(status_code=409, detail="AI_DRAFT_FINGERPRINT_DRIFT: содержимое черновика изменилось")


def _apply_local_draft(db: Session, draft: AiDraft, user: User) -> dict[str, Any]:
    try:
        payload = validate_draft_payload(draft.draft_type, draft.payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"AI_DRAFT_INVALID: {exc}") from exc
    _validate_draft_targets(draft, payload)
    account_ids = [UUID(value) for value in payload.get("account_ids") or []]
    accounts = (
        list(db.scalars(select(CustomerAccount).where(CustomerAccount.id.in_(account_ids))).all())
        if account_ids
        else []
    )
    if len(accounts) != len(set(account_ids)):
        raise HTTPException(status_code=409, detail="AI_DRAFT_TARGET_DRIFT: один из аккаунтов больше недоступен")
    now = utcnow()
    if draft.draft_type == "ACCOUNT_NOTE":
        pinned = bool(payload.get("pinned"))
        field = "pinned_note" if pinned else "current_note"
        for account in accounts:
            previous = getattr(account, field)
            note = str(payload.get("note") or "") or None
            db.add(
                AccountNoteHistory(
                    account_id=account.id,
                    previous_note=previous,
                    note=note,
                    note_kind="PINNED" if pinned else "REGULAR",
                    changed_by_id=user.id,
                    changed_at=now,
                )
            )
            setattr(account, field, note)
            setattr(account, f"{field}_updated_at" if pinned else "note_updated_at", now)
            setattr(account, f"{field}_updated_by_id" if pinned else "note_updated_by_id", user.id)
            db.add(
                ControlCenterEvent(
                    account_id=account.id,
                    actor_user_id=user.id,
                    event_type="PINNED_NOTE_CHANGED" if pinned else "NOTE_CHANGED",
                    source="AI_DRAFT_USER_APPLY",
                    summary="Пользователь применил AI-черновик заметки",
                    details={"draft_id": str(draft.id)},
                    occurred_at=now,
                )
            )
        return {"applied": True, "accounts": len(accounts), "field": field}
    if draft.draft_type == "WORK_STATUS":
        target = str(payload.get("work_status"))
        for account in accounts:
            previous = account.work_status
            account.work_status = target
            db.add(
                AccountWorkStatusHistory(
                    account_id=account.id,
                    previous_status=previous,
                    status=target,
                    changed_by_id=user.id,
                    source="AI_DRAFT_USER_APPLY",
                    changed_at=now,
                )
            )
            db.add(
                ControlCenterEvent(
                    account_id=account.id,
                    actor_user_id=user.id,
                    event_type="WORK_STATUS_CHANGED",
                    source="AI_DRAFT_USER_APPLY",
                    summary=f"Пользователь применил AI-черновик статуса: {previous} → {target}",
                    details={"draft_id": str(draft.id)},
                    occurred_at=now,
                )
            )
        return {"applied": True, "accounts": len(accounts), "work_status": target}
    if draft.draft_type == "TAGS":
        existing_tags = {item.name.casefold(): item for item in db.scalars(select(ControlCenterTag)).all()}
        for name in payload.get("add_tags") or []:
            normalized = " ".join(str(name).split())[:80]
            tag = existing_tags.get(normalized.casefold())
            if not tag:
                tag = ControlCenterTag(name=normalized, color="#64748b", created_by_id=user.id)
                db.add(tag)
                db.flush()
                existing_tags[normalized.casefold()] = tag
            for account in accounts:
                exists = db.scalar(
                    select(AccountTag.id).where(AccountTag.account_id == account.id, AccountTag.tag_id == tag.id)
                )
                if not exists:
                    db.add(AccountTag(account_id=account.id, tag_id=tag.id, assigned_by_id=user.id, assigned_at=now))
                    db.add(
                        AccountTagHistory(
                            account_id=account.id,
                            tag_name=tag.name,
                            action="ASSIGNED",
                            changed_by_id=user.id,
                            changed_at=now,
                        )
                    )
        for name in payload.get("remove_tags") or []:
            tag = existing_tags.get(str(name).casefold())
            if not tag:
                continue
            for account in accounts:
                link = db.scalar(
                    select(AccountTag).where(AccountTag.account_id == account.id, AccountTag.tag_id == tag.id)
                )
                if link:
                    db.delete(link)
                    db.add(
                        AccountTagHistory(
                            account_id=account.id,
                            tag_name=tag.name,
                            action="REMOVED",
                            changed_by_id=user.id,
                            changed_at=now,
                        )
                    )
        return {"applied": True, "accounts": len(accounts), "tags": True}
    if draft.draft_type == "SAVED_VIEW":
        view = ControlCenterSavedView(
            owner_user_id=user.id,
            entity_level="ACCOUNT",
            name=str(payload.get("name") or "AI view")[:120],
            config=payload.get("filters") or {},
            is_default=False,
            is_shared=False,
            description="Создано из подтверждённого AI-черновика",
        )
        db.add(view)
        db.flush()
        draft.linked_entity_type = "control_center_saved_view"
        draft.linked_entity_id = str(view.id)
        return {"applied": True, "entity_id": str(view.id), "editor_path": "/control-center"}
    if draft.draft_type == "RULE":
        rule = ControlCenterRule(
            name=str(payload.get("name") or "AI rule")[:160],
            enabled=False,
            mode="DRY_RUN",
            scope=(payload.get("scope") or {}),
            condition_logic=str(payload.get("logic") or "AND"),
            conditions=payload.get("conditions") or [],
            actions=[{"type": item} for item in payload.get("actions") or []],
            safeguards={"max_data_age_hours": 24, "conversion_lag_hours": 24},
            cooldown_minutes=1440,
            max_actions_per_run=10,
            max_actions_per_day=25,
            priority=100,
            schedule={"interval_minutes": 15},
            max_budget_change_percent=20,
            created_by_id=user.id,
        )
        db.add(rule)
        db.flush()
        draft.linked_entity_type = "control_center_rule"
        draft.linked_entity_id = str(rule.id)
        return {
            "applied": True,
            "entity_id": str(rule.id),
            "mode": "DRY_RUN",
            "enabled": False,
            "editor_path": "/control-center",
        }
    if draft.draft_type == "REPORT":
        assistant_message = (
            db.scalar(
                select(AiMessage)
                .where(AiMessage.run_id == draft.run_id, AiMessage.role == "ASSISTANT")
                .order_by(desc(AiMessage.created_at))
            )
            if draft.run_id
            else None
        )
        report = AiSavedReport(
            owner_user_id=user.id,
            conversation_id=draft.conversation_id,
            run_id=draft.run_id,
            title=str(payload.get("title") or "AI report")[:180],
            report={
                "configuration": payload,
                "content": assistant_message.structured_content if assistant_message else {},
            },
            scope=draft.scope,
            observed_at=now,
            expires_at=now + timedelta(days=30),
        )
        db.add(report)
        db.flush()
        draft.linked_entity_type = "ai_saved_report"
        draft.linked_entity_id = str(report.id)
        return {"applied": True, "entity_id": str(report.id), "editor_path": "/ai-analyst"}
    return {
        "applied": False,
        "editor_path": _ordinary_editor_path(db, draft, payload),
        "reason": "REQUIRES_ORDINARY_EDITOR",
    }


def _ordinary_editor_path(db: Session, draft: AiDraft, payload: dict[str, Any]) -> str:
    marker = f"ai_draft={draft.id}"
    if draft.draft_type == "DEMAND_GEN_PLAN":
        return f"/uploads/{payload['upload_id']}?{marker}"
    if draft.draft_type == "SCHEDULE":
        plan = db.get(DeploymentPlan, UUID(str(payload["deployment_plan_id"])))
        if not plan:
            raise HTTPException(status_code=409, detail="AI_DRAFT_TARGET_DRIFT: deployment plan больше недоступен")
        return f"/uploads/{plan.upload_id}?{marker}&step=schedule"
    if draft.draft_type == "ACTION_SELECTION":
        return f"/control-center?{marker}&tab=campaigns"
    return f"/ai-analyst?{marker}"


def _validate_draft_targets(draft: AiDraft, payload: dict[str, Any]) -> None:
    for payload_key, scope_key, lock_key, label in (
        ("account_ids", "account_ids", "locked_account_ids", "account"),
        ("campaign_ids", "campaign_ids", "locked_campaign_ids", "campaign"),
    ):
        requested = {str(item) for item in payload.get(payload_key) or []}
        allowed_scope = {str(item) for item in (draft.scope or {}).get(scope_key) or []}
        if allowed_scope and requested - allowed_scope:
            raise HTTPException(status_code=403, detail=f"AI_SCOPE_ESCAPE: недоступный {label}")
        snapshot = draft.source_snapshot or {}
        locked = {str(item) for item in snapshot.get(lock_key) or []}
        if snapshot.get("target_set_locked") and requested - locked:
            raise HTTPException(
                status_code=409,
                detail=f"AI_DRAFT_TARGET_EXPANSION: набор {label} нельзя расширить после preview",
            )


def _conversation_payload(item: AiConversation) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "title": item.title,
        "authority_mode": item.authority_mode,
        "google_environment": item.google_environment,
        "scope": item.scope,
        "locale": item.locale,
        "time_zone": item.time_zone,
        "last_message_at": item.last_message_at,
        "archived_at": item.archived_at,
        "retention_until": item.retention_until,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _report_payload(item: AiSavedReport) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "conversation_id": str(item.conversation_id) if item.conversation_id else None,
        "run_id": str(item.run_id) if item.run_id else None,
        "title": item.title,
        "report": item.report,
        "scope": item.scope,
        "observed_at": item.observed_at,
        "expires_at": item.expires_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _message_payload(item: AiMessage, tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "role": item.role,
        "content": item.content,
        "structured_content": item.structured_content,
        "status": item.status,
        "run_id": str(item.run_id) if item.run_id else None,
        "tool_timeline": tool_calls,
        "created_at": item.created_at,
    }


def _tool_call_payload(item: AiToolCall) -> dict[str, Any]:
    job_id = item.result.get("job_id") if isinstance(item.result, dict) else None
    job_status = item.result.get("status") if isinstance(item.result, dict) else None
    return {
        "id": str(item.id),
        "tool_name": item.tool_name,
        "tool_version": item.tool_version,
        "risk_class": item.risk_class,
        "status": item.status,
        "error_code": item.error_code,
        "duration_ms": item.duration_ms,
        "job_id": str(job_id) if job_id else None,
        "job_status": str(job_status) if job_status else None,
        "job_path": "/jobs" if job_id else None,
        "created_at": item.created_at,
    }


def _draft_payload(item: AiDraft) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "conversation_id": str(item.conversation_id) if item.conversation_id else None,
        "draft_type": item.draft_type,
        "status": item.status,
        "authority_mode": item.authority_mode,
        "google_environment": item.google_environment,
        "scope": item.scope,
        "payload": item.payload,
        "source_snapshot": item.source_snapshot,
        "fingerprint": item.fingerprint,
        "version": item.version,
        "expires_at": item.expires_at,
        "linked_entity_type": item.linked_entity_type,
        "linked_entity_id": item.linked_entity_id,
        "action_request_id": str(item.action_request_id) if item.action_request_id else None,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _preference_payload(item: AiUserPreference | None, user: User) -> dict[str, Any]:
    return {
        "default_authority_mode": item.default_authority_mode if item else "READ_ONLY",
        "default_environment": item.default_environment if item else "SIMULATION",
        "default_model_profile": item.default_model_profile if item else "BALANCED",
        "default_scope": item.default_scope if item else {},
        "locale": item.locale if item else "ru",
        "time_zone": item.time_zone if item else user.time_zone,
    }


def _admin_settings_payload(db: Session) -> dict[str, Any]:
    item = db.scalar(select(AiAdminSetting).where(AiAdminSetting.key == "global"))
    return {
        **effective_ai_settings(db),
        "openai_key_configured": bool(settings.openai_api_key or (item and item.openai_key_encrypted)),
        "openai_key_source": "SERVER_ENV"
        if settings.openai_api_key
        else "ENCRYPTED_SERVER_SETTING"
        if item and item.openai_key_encrypted
        else "NOT_CONFIGURED",
        "openai_key_last_four": item.openai_key_last_four
        if item and item.openai_key_encrypted and not settings.openai_api_key
        else None,
        "models": [
            _model_profile_payload(model)
            for model in db.scalars(select(AiModelProfile).order_by(AiModelProfile.name)).all()
        ],
    }


def _model_profile_payload(item: AiModelProfile) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "name": item.name,
        "model_id": item.model_id,
        "reasoning_effort": item.reasoning_effort,
        "verbosity": item.verbosity,
        "timeout_seconds": item.timeout_seconds,
        "max_input_tokens": item.max_input_tokens,
        "max_output_tokens": item.max_output_tokens,
        "enabled": item.enabled,
        "price_metadata": item.price_metadata,
        "eval_version": item.eval_version,
        "eval_passed_at": item.eval_passed_at,
    }


def _usage_payload(item: AiUsageDaily) -> dict[str, Any]:
    return {
        "date": item.usage_date,
        "user_id": str(item.user_id),
        "model_id": item.model_id,
        "requests": item.requests,
        "input_tokens": item.input_tokens,
        "output_tokens": item.output_tokens,
        "estimated_cost_usd": float(item.estimated_cost_usd),
        "tool_calls": item.tool_calls,
        "errors": item.errors,
        "latency_ms_total": item.latency_ms_total,
    }


def _geo_profile_payload(item: GeoAnalyticsProfile) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "scope_type": item.scope_type,
        "scope_id": str(item.scope_id) if item.scope_id else None,
        "geo_id": str(item.geo_id) if item.geo_id else None,
        "version": item.version,
        "is_active": item.is_active,
        "effective_from": item.effective_from,
        "effective_until": item.effective_until,
        "time_zone": item.time_zone,
        "expected_currencies": item.expected_currencies,
        "default_reporting_period": item.default_reporting_period,
        "primary_metric_source": item.primary_metric_source,
        "target_cpl": _number(item.target_cpl),
        "target_registration_cpa": _number(item.target_registration_cpa),
        "target_deposit_cpa": _number(item.target_deposit_cpa),
        "target_roas": _number(item.target_roas),
        "max_spend_without_lead": _number(item.max_spend_without_lead),
        "max_spend_without_registration": _number(item.max_spend_without_registration),
        "max_spend_without_deposit": _number(item.max_spend_without_deposit),
        "minimum_clicks": item.minimum_clicks,
        "minimum_impressions": item.minimum_impressions,
        "minimum_spend": _number(item.minimum_spend),
        "conversion_lag_hours": item.conversion_lag_hours,
        "alert_thresholds": item.alert_thresholds,
        "owner_comment": item.owner_comment,
        "created_by_id": str(item.created_by_id),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _geo_override_payload(item: GeoAnalyticsOverride) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "scope_type": item.scope_type,
        "scope_id": str(item.scope_id),
        "profile_id": str(item.profile_id) if item.profile_id else None,
        "override_values": item.override_values,
        "is_active": item.is_active,
    }


def _metric_mapping_payload(item: MetricSourceMapping) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "scope_type": item.scope_type,
        "scope_id": str(item.scope_id) if item.scope_id else None,
        "semantic_metric": item.semantic_metric,
        "provider": item.provider,
        "source_id": item.source_id,
        "source_name": item.source_name,
        "attribution_model": item.attribution_model,
        "is_active": item.is_active,
        "metadata": item.metadata_json,
    }


def _draft_fingerprint(draft_type: str, payload: dict[str, Any], scope: dict[str, Any], version: int) -> str:
    return hashlib.sha256(
        json.dumps(
            {"type": draft_type, "payload": payload, "scope": scope, "version": version}, sort_keys=True, default=str
        ).encode()
    ).hexdigest()


def _audio_duration(content: bytes, suffix: str) -> float:
    path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            path = handle.name
            handle.write(content)
        completed = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if completed.returncode != 0:
            raise HTTPException(status_code=422, detail="AI_AUDIO_INVALID: не удалось прочитать длительность записи")
        return float(completed.stdout.strip())
    finally:
        if path:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(redact(data), ensure_ascii=False, default=str)}\n\n"


def _replay_stream(run: AiRun, message: AiMessage | None):
    yield _sse("connected", {"run_id": str(run.id), "status": run.status, "reused": True})
    if message:
        yield _sse("message.completed", message.structured_content)
    elif run.status == AiRunStatus.FAILED.value:
        yield _sse("run.error", {"code": run.error_code, "message": run.error_message})
    else:
        yield _sse("run.status", {"status": run.status})


def _number(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None
