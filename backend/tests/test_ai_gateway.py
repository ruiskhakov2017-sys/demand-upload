from __future__ import annotations

import json
from types import SimpleNamespace

from app.ai.gateway import OpenAIResponsesGateway, tool_output_item
from app.ai.schemas import AiStructuredAnswer, PeriodInfo, ResolvedScopeInfo


def strict_answer() -> AiStructuredAnswer:
    return AiStructuredAnswer(
        answer="ok",
        resolved_scope=ResolvedScopeInfo(
            connection_ids=[], mcc_ids=[], geo_ids=[], account_ids=[], campaign_ids=[], label="test"
        ),
        period=PeriodInfo(preset="7d", start_date=None, end_date=None),
        timezones=["UTC"],
        sources=[],
        freshness="FRESH",
        completeness="COMPLETE",
        currency_groups=[],
        findings=[],
        evidence=[],
        exact_backend_condition="true",
        conclusion="ok",
        confidence=1,
        caveats=[],
        warnings=[],
        tables=[],
        charts=[],
        object_links=[],
        draft=None,
    )


class OutputItem:
    type = "function_call"
    call_id = "call-1"
    name = "find_accounts"
    arguments = "{}"

    def model_dump(self, mode: str):
        assert mode == "json"
        return {"type": self.type, "call_id": self.call_id, "name": self.name, "arguments": self.arguments}


class Responses:
    def __init__(self) -> None:
        self.kwargs = None

    def parse(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            output=[OutputItem()],
            output_parsed=strict_answer(),
            output_text="",
            usage=SimpleNamespace(input_tokens=12, output_tokens=7),
        )


def test_responses_gateway_uses_store_false_strict_tools_and_no_parallel_calls() -> None:
    responses = Responses()
    gateway = OpenAIResponsesGateway.__new__(OpenAIResponsesGateway)
    gateway.client = SimpleNamespace(responses=responses)
    profile = SimpleNamespace(
        model_id="test-model",
        max_output_tokens=1000,
        reasoning_effort="low",
        verbosity="medium",
        timeout_seconds=20,
    )
    tools = [{"type": "function", "name": "find_accounts", "strict": True, "parameters": {}}]

    result = gateway.turn(profile=profile, instructions="safe", input_items=[], tools=tools)

    assert responses.kwargs["store"] is False
    assert responses.kwargs["parallel_tool_calls"] is False
    assert responses.kwargs["verbosity"] == "medium"
    assert responses.kwargs["max_tool_calls"] == 7
    assert responses.kwargs["tools"] == tools
    assert responses.kwargs["text_format"] is AiStructuredAnswer
    assert result.function_calls[0].name == "find_accounts"
    assert (result.input_tokens, result.output_tokens) == (12, 7)


def test_function_output_is_json_and_never_python_repr() -> None:
    item = tool_output_item("call-1", {"ok": True, "text": "данные"})
    assert item["type"] == "function_call_output"
    assert json.loads(item["output"]) == {"ok": True, "text": "данные"}
