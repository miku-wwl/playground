import asyncio
import time

import pytest

from agent_lab.core.agent import AgentLoop, MaxStepsExceeded, ModelDecisionTimeout
from agent_lab.core.history import MessageHistory
from agent_lab.models.decisions import FinalAnswerDecision, ToolCallDecision
from agent_lab.models.fake_model import FakeModelClient
from agent_lab.tools.demo_tools import (
    create_demo_tool_registry,
    get_my_balance,
    get_order_status,
)
from agent_lab.tools.dispatcher import ToolDispatcher
from agent_lab.tools.registry import ToolRegistry
from agent_lab.tools.schemas import TOOL_ARGUMENT_SCHEMAS


def test_demo_balance_tool_reads_simulated_user_data() -> None:
    assert asyncio.run(get_my_balance(user_id="user-123", asset="USDT")) == {
        "asset": "USDT",
        "balance": 500,
    }


def test_demo_order_tool_reads_current_users_simulated_order() -> None:
    assert asyncio.run(get_order_status(user_id="user-123", order_id="ORD-001")) == {
        "order_id": "ORD-001",
        "status": "FILLED",
    }


def test_agent_runs_tool_and_uses_tool_result_for_final_answer(
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry = ToolRegistry()
    calls: list[tuple[str, str]] = []

    async def balance_tool(*, user_id: str, asset: str) -> dict[str, object]:
        calls.append((user_id, asset))
        return {"asset": asset, "balance": 275}

    registry.register(
        "get_my_balance",
        balance_tool,
        TOOL_ARGUMENT_SCHEMAS["get_my_balance"],
    )
    agent = AgentLoop(FakeModelClient(), ToolDispatcher(registry), max_steps=3)

    answer = asyncio.run(
        agent.run("What is my USDT balance?", authenticated_user_id="user-123")
    )

    assert answer == "Your USDT balance is 275."
    assert calls == [("user-123", "USDT")]
    trace = capsys.readouterr().out
    assert "model_decision=tool_call" in trace
    assert "tool_result={'asset': 'USDT', 'balance': 275}" in trace
    assert "final_answer=Your USDT balance is 275." in trace


def test_dispatcher_rejects_tool_outside_registry() -> None:
    dispatcher = ToolDispatcher(create_demo_tool_registry())

    with pytest.raises(ValueError, match="Tool is not allowed"):
        asyncio.run(
            dispatcher.dispatch(
                "delete_account",
                {},
                authenticated_user_id="user-123",
            )
        )


def test_agent_stops_when_max_steps_is_reached() -> None:
    class RepeatingToolModel(FakeModelClient):
        def decide(self, history: MessageHistory) -> ToolCallDecision:
            return ToolCallDecision("get_my_balance", {"asset": "USDT"})

    agent = AgentLoop(
        RepeatingToolModel(),
        ToolDispatcher(create_demo_tool_registry()),
        max_steps=2,
    )

    with pytest.raises(MaxStepsExceeded, match="max_steps=2"):
        asyncio.run(agent.run("Keep calling the tool", authenticated_user_id="user-123"))


def test_agent_stops_when_model_decision_times_out() -> None:
    class SlowModel:
        def decide(self, history: MessageHistory) -> FinalAnswerDecision:
            time.sleep(0.05)
            return FinalAnswerDecision("too late")

    agent = AgentLoop(
        SlowModel(),
        ToolDispatcher(create_demo_tool_registry()),
        max_steps=1,
        model_timeout_seconds=0.005,
    )

    with pytest.raises(ModelDecisionTimeout, match="exceeded"):
        asyncio.run(agent.run("Wait", authenticated_user_id="user-123"))


def test_agent_returns_runtime_pending_message_without_trusting_model_claims() -> None:
    class TicketModel:
        calls = 0

        def decide(self, history: MessageHistory) -> FinalAnswerDecision | ToolCallDecision:
            self.calls += 1
            if self.calls == 1:
                return ToolCallDecision(
                    "create_support_ticket",
                    {
                        "order_id": "ORD-001",
                        "reason": "The order status has not updated for several days.",
                    },
                )
            return FinalAnswerDecision("The ticket has been created.")

    model = TicketModel()
    dispatcher = ToolDispatcher(create_demo_tool_registry())
    agent = AgentLoop(model, dispatcher, max_steps=3)

    answer = asyncio.run(
        agent.run("Create a support ticket.", authenticated_user_id="user-123")
    )

    assert "pending human approval" in answer
    assert "nothing has been executed" in answer
    assert model.calls == 1
