from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.schemas import AiStructuredAnswer
from app.core.config import settings
from app.core.security import decrypt_json
from app.db.models import AiAdminSetting, AiModelProfile


class AiProviderUnavailable(RuntimeError):
    code = "OPENAI_NOT_CONFIGURED"


@dataclass(frozen=True)
class FunctionCall:
    call_id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class GatewayTurn:
    output_items: list[dict[str, Any]]
    function_calls: list[FunctionCall]
    answer: AiStructuredAnswer | None
    output_text: str
    input_tokens: int
    output_tokens: int


class ResponsesGateway(Protocol):
    def turn(
        self,
        *,
        profile: AiModelProfile,
        instructions: str,
        input_items: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> GatewayTurn: ...


class OpenAIResponsesGateway:
    def __init__(self, api_key: str) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - packaging failure, not a runtime branch
            raise AiProviderUnavailable("OpenAI SDK не установлен на сервере") from exc
        self.client = OpenAI(api_key=api_key)

    def turn(
        self,
        *,
        profile: AiModelProfile,
        instructions: str,
        input_items: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> GatewayTurn:
        response = self.client.responses.parse(
            model=profile.model_id,
            instructions=instructions,
            input=input_items,
            tools=tools,
            text_format=AiStructuredAnswer,
            parallel_tool_calls=False,
            store=False,
            max_output_tokens=profile.max_output_tokens,
            max_tool_calls=settings.ai_max_read_tool_calls + settings.ai_max_draft_tool_calls,
            reasoning={"effort": profile.reasoning_effort},
            verbosity=profile.verbosity,
            timeout=profile.timeout_seconds,
        )
        calls: list[FunctionCall] = []
        output_items: list[dict[str, Any]] = []
        for item in response.output:
            dumped = item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item)
            output_items.append(dumped)
            if getattr(item, "type", None) == "function_call":
                calls.append(
                    FunctionCall(
                        call_id=str(item.call_id),
                        name=str(item.name),
                        arguments=str(item.arguments),
                    )
                )
        parsed = getattr(response, "output_parsed", None)
        if parsed is not None and not isinstance(parsed, AiStructuredAnswer):
            parsed = AiStructuredAnswer.model_validate(parsed)
        usage = getattr(response, "usage", None)
        return GatewayTurn(
            output_items=output_items,
            function_calls=calls,
            answer=parsed,
            output_text=str(getattr(response, "output_text", "") or ""),
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        )


def get_openai_api_key(db: Session) -> str | None:
    if settings.openai_api_key:
        return settings.openai_api_key.get_secret_value()
    item = db.scalar(select(AiAdminSetting).where(AiAdminSetting.key == "global"))
    if not item or not item.openai_key_encrypted:
        return None
    payload = decrypt_json(item.openai_key_encrypted)
    value = payload.get("api_key")
    return str(value) if value else None


def build_gateway(db: Session) -> ResponsesGateway:
    api_key = get_openai_api_key(db)
    if not api_key:
        raise AiProviderUnavailable("OpenAI API key не настроен на сервере")
    return OpenAIResponsesGateway(api_key)


def model_profile(db: Session, name: str) -> AiModelProfile:
    profile = db.scalar(select(AiModelProfile).where(AiModelProfile.name == name, AiModelProfile.enabled.is_(True)))
    if not profile:
        raise ValueError(f"AI_MODEL_PROFILE_UNAVAILABLE: {name}")
    return profile


def tool_output_item(call_id: str, output: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function_call_output",
        "call_id": call_id,
        "output": json.dumps(output, ensure_ascii=False, default=str),
    }
