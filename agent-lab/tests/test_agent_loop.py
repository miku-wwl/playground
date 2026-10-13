import pytest

from agent_lab.core.agent import AgentLoop, MaxStepsExceeded
from agent_lab.core.history import MessageHistory
from agent_lab.models.decisions import ToolCallDecision
from agent_lab.models.fake_model import FakeModelClient
from agent_lab.tools.demo_tools import create_demo_tool_registry, get_my_balance
from agent_lab.tools.dispatcher import ToolDispatcher
from agent_lab.tools.registry import ToolRegistry


def test_demo_balance_tool_reads_simulated_user_data() -> None:
    assert get_my_balance(user_id="user-123", asset="USDT") == {
        "asset": "USDT",
        "balance": 500,
    }


def test_agent_runs_tool_and_uses_tool_result_for_final_answer(capsys: pytest.CaptureFixture[str]) -> None:
    registry = ToolRegistry()
    calls: list[tuple[str, str]] = []

    def balance_tool(*, user_id: str, asset: str) -> dict[str, object]:
        calls.append((user_id, asset))
        return {"asset": asset, "balance": 275}

    registry.register("get_my_balance", balance_tool)
    agent = AgentLoop(FakeModelClient(), ToolDispatcher(registry), max_steps=3)

    answer = agent.run("What is my USDT balance?", authenticated_user_id="user-123")

    assert answer == "Your USDT balance is 275."
    assert calls == [("user-123", "USDT")]
    trace = capsys.readouterr().out
    assert "model_decision=tool_call" in trace
    assert "tool_result={'asset': 'USDT', 'balance': 275}" in trace
    assert "final_answer=Your USDT balance is 275." in trace


def test_dispatcher_rejects_tool_outside_registry() -> None:
    dispatcher = ToolDispatcher(create_demo_tool_registry())

    with pytest.raises(ValueError, match="Tool is not allowed"):
        dispatcher.dispatch("delete_account", {}, authenticated_user_id="user-123")


def test_agent_stops_when_max_steps_is_reached() -> None:
    class RepeatingToolModel(FakeModelClient):
        def decide(self, history: MessageHistory) -> ToolCallDecision:
            return ToolCallDecision("get_my_balance", {"asset": "USDT"})

    registry = create_demo_tool_registry()
    agent = AgentLoop(RepeatingToolModel(), ToolDispatcher(registry), max_steps=2)

    with pytest.raises(MaxStepsExceeded, match="max_steps=2"):
        agent.run("Keep calling the tool", authenticated_user_id="user-123")
