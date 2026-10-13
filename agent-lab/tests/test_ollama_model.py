import json

import pytest
import requests

from agent_lab.core.history import MessageHistory
from agent_lab.models.decisions import ToolCallDecision
from agent_lab.models.ollama_model import (
    InvalidModelResponse,
    MODEL_DECISION_SCHEMA,
    ModelCallError,
    OllamaModelClient,
)


class FakeHttpResponse:
    def __init__(self, body: object, status_error: Exception | None = None) -> None:
        self._body = body
        self._status_error = status_error

    def raise_for_status(self) -> None:
        if self._status_error:
            raise self._status_error

    def json(self) -> object:
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


def test_ollama_client_sends_schema_and_parses_a_tool_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request: dict[str, object] = {}
    response_body = {
        "message": {
            "content": json.dumps(
                {
                    "type": "tool_call",
                    "tool": "get_my_balance",
                    "arguments": {"asset": "USDT"},
                }
            )
        }
    }

    def fake_post(url: str, *, json: dict[str, object], timeout: float) -> FakeHttpResponse:
        request.update({"url": url, "json": json, "timeout": timeout})
        return FakeHttpResponse(response_body)

    monkeypatch.setattr("agent_lab.models.ollama_model.requests.post", fake_post)
    history = MessageHistory()
    history.add_user("What is my USDT balance?")

    decision = OllamaModelClient(timeout_seconds=12).decide(history)

    assert decision == ToolCallDecision("get_my_balance", {"asset": "USDT"})
    assert request["url"] == "http://127.0.0.1:11434/api/chat"
    assert request["timeout"] == 12
    assert request["json"]["format"] == MODEL_DECISION_SCHEMA
    assert request["json"]["stream"] is False


def test_ollama_client_sends_previous_tool_result_back_to_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request: dict[str, object] = {}

    def fake_post(url: str, *, json: dict[str, object], timeout: float) -> FakeHttpResponse:
        request.update(json)
        return FakeHttpResponse({"message": {"content": '{"type":"final","answer":"Done."}'}})

    monkeypatch.setattr("agent_lab.models.ollama_model.requests.post", fake_post)
    history = MessageHistory()
    history.add_user("What is my USDT balance?")
    history.add_tool_call("get_my_balance", {"asset": "USDT"})
    history.add_tool_result("get_my_balance", {"asset": "USDT", "balance": 500})

    OllamaModelClient().decide(history)

    messages = request["messages"]
    assert messages[-1] == {
        "role": "user",
        "content": 'Tool result from get_my_balance: {"asset": "USDT", "balance": 500}',
    }


def test_ollama_client_rejects_non_json_model_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "agent_lab.models.ollama_model.requests.post",
        lambda *args, **kwargs: FakeHttpResponse({"message": {"content": "not JSON"}}),
    )

    with pytest.raises(InvalidModelResponse, match="not valid JSON"):
        OllamaModelClient().decide(MessageHistory())


def test_ollama_client_rejects_tool_call_outside_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = json.dumps(
        {"type": "tool_call", "tool": "delete_account", "arguments": {}}
    )
    monkeypatch.setattr(
        "agent_lab.models.ollama_model.requests.post",
        lambda *args, **kwargs: FakeHttpResponse({"message": {"content": content}}),
    )

    with pytest.raises(InvalidModelResponse, match="JSON Schema"):
        OllamaModelClient().decide(MessageHistory())


def test_ollama_client_reports_timeout_and_server_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def timeout(*args: object, **kwargs: object) -> None:
        raise requests.Timeout("slow local model")

    monkeypatch.setattr("agent_lab.models.ollama_model.requests.post", timeout)
    with pytest.raises(ModelCallError, match="timed out"):
        OllamaModelClient(timeout_seconds=1).decide(MessageHistory())

    server_error = requests.HTTPError("500 Server Error")
    monkeypatch.setattr(
        "agent_lab.models.ollama_model.requests.post",
        lambda *args, **kwargs: FakeHttpResponse({}, server_error),
    )
    with pytest.raises(ModelCallError, match="request failed"):
        OllamaModelClient().decide(MessageHistory())
