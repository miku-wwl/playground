import json

import requests
from jsonschema import ValidationError, validate

from agent_lab.core.history import MessageHistory
from agent_lab.models.decisions import (
    FinalAnswerDecision,
    ModelDecision,
    ToolCallDecision,
)
from agent_lab.tools.schemas import build_model_decision_schema


MODEL_DECISION_SCHEMA: dict[str, object] = build_model_decision_schema()

SYSTEM_PROMPT = """You are a small trading support assistant. You do not know account data.
You may use only these registered tools:
- get_my_balance(asset): reads the user's simulated asset balance; asset must be USDT.
- get_order_status(order_id): reads the user's simulated order status.
- create_support_ticket(order_id, reason): proposes a simulated support ticket and always requires human approval before execution.

IMPORTANT RULES:
- If the user asks for a balance or order status, you MUST first return a tool_call.
- If the user asks to create a support ticket, propose a tool_call; the runtime will require human approval.
- Do not answer balance or order questions from memory or guess a value.
- After a tool result appears in the conversation, return a final answer based on that result.
- A create_support_ticket call only requests human approval; do not say a ticket was created unless its result says EXECUTED.
- For an unsupported request, return a final answer that says this demo cannot help.
- Return only the JSON decision required by the schema.

Examples:
User: What is my USDT balance?
Assistant: {"type":"tool_call","tool":"get_my_balance","arguments":{"asset":"USDT"}}
User: Tool result from get_my_balance: {"asset":"USDT","balance":500}
Assistant: {"type":"final","answer":"Your USDT balance is 500."}
User: Can you predict tomorrow's Bitcoin price?
Assistant: {"type":"final","answer":"This demo cannot predict Bitcoin prices."}"""


class ModelCallError(RuntimeError):
    """Ollama could not complete an API request."""


class InvalidModelResponse(RuntimeError):
    """Ollama returned content that does not match the decision protocol."""


class OllamaModelClient:
    """Gets JSON decisions from the local Ollama chat API."""

    def __init__(
        self,
        model_name: str = "phi4-mini:latest",
        base_url: str = "http://127.0.0.1:11434",
        timeout_seconds: float = 60,
    ) -> None:
        self._model_name = model_name
        self._chat_url = f"{base_url.rstrip('/')}/api/chat"
        self._timeout_seconds = timeout_seconds

    def decide(self, history: MessageHistory) -> ModelDecision:
        payload = {
            "model": self._model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                *self._format_history(history),
            ],
            "format": MODEL_DECISION_SCHEMA,
            "stream": False,
            "options": {"temperature": 0},
        }

        try:
            response = requests.post(
                self._chat_url,
                json=payload,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except requests.Timeout as error:
            raise ModelCallError(
                f"Ollama request timed out after {self._timeout_seconds:g} seconds"
            ) from error
        except requests.RequestException as error:
            raise ModelCallError(f"Ollama request failed: {error}") from error

        try:
            response_body = response.json()
        except ValueError as error:
            raise InvalidModelResponse("Ollama returned invalid HTTP JSON") from error

        message = response_body.get("message") if isinstance(response_body, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise InvalidModelResponse("Ollama response is missing message.content")

        print(f"MODEL JSON: {content}")
        try:
            decision_data = json.loads(content)
        except json.JSONDecodeError as error:
            raise InvalidModelResponse("Model decision is not valid JSON") from error

        try:
            validate(instance=decision_data, schema=MODEL_DECISION_SCHEMA)
        except ValidationError as error:
            raise InvalidModelResponse(
                f"Model decision does not match the JSON Schema: {error.message}"
            ) from error

        if decision_data["type"] == "tool_call":
            return ToolCallDecision(
                tool_name=decision_data["tool"],
                arguments=decision_data["arguments"],
            )

        return FinalAnswerDecision(answer=decision_data["answer"])

    @staticmethod
    def _format_history(history: MessageHistory) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        for item in history.messages:
            if item["role"] == "user":
                messages.append({"role": "user", "content": str(item["content"])})
            elif item.get("type") == "tool_call":
                call = {
                    "tool": item["tool_name"],
                    "arguments": item["arguments"],
                }
                messages.append(
                    {
                        "role": "assistant",
                        "content": f"I requested this tool call: {json.dumps(call)}",
                    }
                )
            elif item["role"] == "tool":
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"Tool result from {item['tool_name']}: "
                            f"{json.dumps(item['content'], ensure_ascii=False)}"
                        ),
                    }
                )
        return messages
