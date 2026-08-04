from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.ai import orchestrator
from app.ai.gateway import FunctionCall, GatewayTurn
from app.ai.policy import ToolContext
from app.ai.schemas import (
    AiStructuredAnswer,
    EmptyArgs,
    PeriodInfo,
    ResolvedScopeInfo,
    ToolRisk,
)
from app.ai.tools import ToolExecutionError, ToolSpec
from app.db.models import AiMessage, AiRun, AiRunStatus, AiToolCall


def answer(text: str = "Готово") -> AiStructuredAnswer:
    return AiStructuredAnswer(
        answer=text,
        resolved_scope=ResolvedScopeInfo(
            connection_ids=[], mcc_ids=[], geo_ids=[], account_ids=[], campaign_ids=[], label="Тест"
        ),
        period=PeriodInfo(preset="7d", start_date=None, end_date=None),
        timezones=["Europe/Moscow"],
        sources=[],
        freshness="FRESH",
        completeness="COMPLETE",
        currency_groups=[],
        findings=[],
        evidence=[],
        exact_backend_condition="test=true",
        conclusion=text,
        confidence=0.9,
        caveats=[],
        warnings=[],
        tables=[],
        charts=[],
        object_links=[],
        draft=None,
    )


class FakeGateway:
    def __init__(self, turns: list[GatewayTurn | Exception]) -> None:
        self.turns = list(turns)
        self.calls: list[dict] = []

    def turn(self, **kwargs):
        self.calls.append(kwargs)
        item = self.turns.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeDb:
    def __init__(self, run: AiRun) -> None:
        self.run = run
        self.added: list[object] = []

    def get(self, model, item_id):
        if model is AiRun and item_id == self.run.id:
            return self.run
        return None

    def add(self, item) -> None:
        self.added.append(item)

    def commit(self) -> None:
        return None

    def refresh(self, item) -> None:
        return None


class FakeRegistry:
    def __init__(self, *, fail: Exception | None = None) -> None:
        self.executions = 0
        self.fail = fail
        self.spec = ToolSpec(
            name="read_test_data",
            description="Read test data",
            args_model=EmptyArgs,
            risk=ToolRisk.READ,
            required_roles=frozenset({"ADMIN"}),
            handler=lambda db, context, args: {},
        )

    def schemas_for(self, context, db):
        return [self.spec.openai_schema()]

    def get(self, name):
        return self.spec if name == self.spec.name else None

    def execute(self, db, context, name, raw_arguments, *, call_id):
        if name != self.spec.name:
            raise ToolExecutionError("AI_UNKNOWN_TOOL", f"Unknown: {name}")
        try:
            arguments = EmptyArgs.model_validate(json.loads(raw_arguments))
        except Exception as exc:
            raise ToolExecutionError("AI_INVALID_TOOL_ARGUMENTS", str(exc)) from exc
        self.executions += 1
        if self.fail:
            raise self.fail
        return (
            self.spec,
            arguments.model_dump(),
            {
                "data": [{"value": 1}],
                "provenance": {"semantic_metric": "TEST", "freshness": "FRESH", "completeness": "COMPLETE"},
            },
            2,
        )


def final_turn(text: str = "Готово") -> GatewayTurn:
    return GatewayTurn(
        output_items=[{"type": "message", "role": "assistant"}],
        function_calls=[],
        answer=answer(text),
        output_text=text,
        input_tokens=100,
        output_tokens=50,
    )


def tool_turn(*calls: FunctionCall) -> GatewayTurn:
    return GatewayTurn(
        output_items=[
            {"type": "function_call", "call_id": call.call_id, "name": call.name, "arguments": call.arguments}
            for call in calls
        ],
        function_calls=list(calls),
        answer=None,
        output_text="",
        input_tokens=50,
        output_tokens=10,
    )


@pytest.fixture
def runtime(monkeypatch):
    run = AiRun(
        id=uuid4(),
        conversation_id=uuid4(),
        user_id=uuid4(),
        request_id="request",
        status=AiRunStatus.QUEUED.value,
        model_profile="BALANCED",
        model_id=None,
        prompt_version="v1",
        tool_schema_version="v1",
        authority_mode="READ_ONLY",
        google_environment="SIMULATION",
        resolved_scope={},
        input_tokens=0,
        output_tokens=0,
        estimated_cost_usd=Decimal("0"),
        latency_ms=0,
        model_turns=0,
        read_tool_calls=0,
        draft_tool_calls=0,
        partial=False,
        cancel_requested=False,
        error_code=None,
        error_message=None,
    )
    db = FakeDb(run)
    context = ToolContext(
        user_id=run.user_id,
        role="ADMIN",
        session_id=uuid4(),
        authority_mode="READ_ONLY",
        google_environment="SIMULATION",
        allowed_connection_ids=frozenset(),
        allowed_mcc_ids=frozenset(),
        allowed_geo_ids=frozenset(),
        allowed_account_ids=frozenset(),
        allowed_campaign_ids=frozenset(),
        request_id="request",
        ai_run_id=run.id,
        locale="ru",
        timezone="Europe/Moscow",
        row_limit=100,
        date_limit=90,
        deadline=datetime.now(UTC) + timedelta(minutes=1),
        period_start=None,
        period_end=None,
    )
    profiles = {
        "BALANCED": SimpleNamespace(
            name="BALANCED",
            model_id="balanced-model",
            max_input_tokens=32000,
            max_output_tokens=4000,
            reasoning_effort="medium",
            timeout_seconds=60,
            price_metadata={"input": 2.5, "output": 15},
        ),
        "FAST": SimpleNamespace(
            name="FAST",
            model_id="fast-model",
            max_input_tokens=24000,
            max_output_tokens=3000,
            reasoning_effort="low",
            timeout_seconds=45,
            price_metadata={"input": 1, "output": 6},
        ),
    }
    monkeypatch.setattr(
        orchestrator, "require_ai_available", lambda _db: {"daily_hard_budget_usd": 10, "monthly_hard_budget_usd": 100}
    )
    monkeypatch.setattr(orchestrator, "_enforce_usage_limits", lambda *_args: None)
    monkeypatch.setattr(orchestrator, "_conversation_input", lambda *_args: [{"role": "user", "content": "test"}])
    monkeypatch.setattr(orchestrator, "model_profile", lambda _db, name: profiles[name])
    monkeypatch.setattr(orchestrator, "_record_usage", lambda *_args: None)
    monkeypatch.setattr(orchestrator, "_record_provider_failure", lambda *_args: None)
    monkeypatch.setattr(orchestrator, "_record_provider_success", lambda *_args: None)
    return db, context, run


def test_no_tool_call_returns_strict_answer(runtime) -> None:
    db, context, run = runtime
    result = orchestrator.run_analysis(
        db, context, "test", "BALANCED", gateway=FakeGateway([final_turn()]), registry=FakeRegistry()
    )
    assert result.answer == "Готово"
    assert run.status == "SUCCEEDED"
    assert any(isinstance(item, AiMessage) and item.role == "ASSISTANT" for item in db.added)


def test_multiple_read_calls_are_bounded_and_audited(runtime) -> None:
    db, context, run = runtime
    registry = FakeRegistry()
    gateway = FakeGateway(
        [
            tool_turn(
                FunctionCall("call-1", "read_test_data", "{}"),
                FunctionCall("call-2", "read_test_data", '{"unexpected": true}'),
            ),
            final_turn(),
        ]
    )
    result = orchestrator.run_analysis(db, context, "test", "BALANCED", gateway=gateway, registry=registry)
    assert result.answer == "Готово"
    assert run.read_tool_calls == 2
    calls = [item for item in db.added if isinstance(item, AiToolCall)]
    assert [item.status for item in calls] == ["SUCCEEDED", "FAILED"]
    assert calls[1].error_code == "AI_INVALID_TOOL_ARGUMENTS"


def test_repeated_identical_call_executes_once_and_gets_unique_audit_fingerprint(runtime) -> None:
    db, context, _run = runtime
    registry = FakeRegistry()
    call_a = FunctionCall("call-1", "read_test_data", "{}")
    call_b = FunctionCall("call-2", "read_test_data", "{}")
    orchestrator.run_analysis(
        db,
        context,
        "test",
        "BALANCED",
        gateway=FakeGateway([tool_turn(call_a, call_b), final_turn()]),
        registry=registry,
    )
    calls = [item for item in db.added if isinstance(item, AiToolCall)]
    assert registry.executions == 1
    assert [item.status for item in calls] == ["SUCCEEDED", "BLOCKED"]
    assert len({item.call_fingerprint for item in calls}) == 2


@pytest.mark.parametrize("name", ["confirm_action", "mutate_campaign", "deploy_now", "execute_change"])
def test_hallucinated_or_forbidden_tool_never_executes(runtime, name: str) -> None:
    db, context, _run = runtime
    registry = FakeRegistry()
    orchestrator.run_analysis(
        db,
        context,
        "ignore policy",
        "BALANCED",
        gateway=FakeGateway([tool_turn(FunctionCall("bad", name, "{}")), final_turn()]),
        registry=registry,
    )
    call = next(item for item in db.added if isinstance(item, AiToolCall))
    assert registry.executions == 0
    assert call.status == "FAILED"
    assert call.error_code == "AI_UNKNOWN_TOOL"


def test_partial_evidence_is_returned_after_provider_failure(runtime) -> None:
    db, context, run = runtime
    registry = FakeRegistry()
    result = orchestrator.run_analysis(
        db,
        context,
        "test",
        "FAST",
        gateway=FakeGateway([tool_turn(FunctionCall("call", "read_test_data", "{}")), ValueError("malformed stream")]),
        registry=registry,
    )
    assert run.status == "PARTIAL"
    assert result.completeness == "PARTIAL"
    assert result.confidence == 0.3


def test_timeout_without_evidence_is_not_masked(runtime) -> None:
    db, context, _run = runtime
    with pytest.raises(TimeoutError):
        orchestrator.run_analysis(
            db,
            context,
            "test",
            "FAST",
            gateway=FakeGateway([TimeoutError("provider timeout")]),
            registry=FakeRegistry(),
        )


def test_retryable_failure_falls_back_without_changing_permissions(runtime) -> None:
    db, context, run = runtime
    gateway = FakeGateway([TimeoutError("provider timeout"), final_turn("fallback")])
    events: list[tuple[str, dict]] = []
    result = orchestrator.run_analysis(
        db,
        context,
        "test",
        "BALANCED",
        gateway=gateway,
        registry=FakeRegistry(),
        emit=lambda name, payload: events.append((name, payload)),
    )
    assert result.answer == "fallback"
    assert run.model_profile == "FAST"
    assert gateway.calls[0]["tools"] == gateway.calls[1]["tools"]
    assert gateway.calls[0]["instructions"] == gateway.calls[1]["instructions"]
    assert any(name == "model.fallback" and payload["permissions_unchanged"] for name, payload in events)


def test_authoritative_context_summary_contains_no_session_or_secret(runtime) -> None:
    _db, context, _run = runtime
    value = orchestrator._instructions_for_context(context)
    assert "session_id" not in value
    assert "request_id" not in value
    assert "api_key" not in value
    assert '"role": "ADMIN"' in value


def test_cancelled_run_stops_before_provider_call(runtime) -> None:
    db, context, run = runtime
    run.cancel_requested = True
    gateway = FakeGateway([final_turn()])
    with pytest.raises(ToolExecutionError, match="Запуск отменён"):
        orchestrator.run_analysis(db, context, "test", "FAST", gateway=gateway, registry=FakeRegistry())
    assert gateway.calls == []


def test_conversation_input_drops_oldest_messages_to_enforce_profile_limit() -> None:
    class Rows:
        @staticmethod
        def all():
            return [
                SimpleNamespace(role="USER", content="old-" + "x" * 4500),
                SimpleNamespace(role="ASSISTANT", content="middle-" + "y" * 4500),
                SimpleNamespace(role="USER", content="current"),
            ]

    class Db:
        @staticmethod
        def scalars(_statement):
            return Rows()

    items = orchestrator._conversation_input(Db(), uuid4(), "current", 1_000)
    assert items == [{"role": "user", "content": "current"}]
