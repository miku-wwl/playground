import asyncio
import json
import time

import pytest

from agent_lab.core.agent import AgentLoop, MaxStepsExceeded, ModelDecisionTimeout
from agent_lab.models.decisions import FinalAnswerDecision, ToolCallDecision
from agent_lab.tools.demo_tools import create_demo_tool_registry
from agent_lab.tools.dispatcher import ToolDispatcher, ToolExecutionTimeout
from agent_lab.tools.registry import ToolRegistry
from agent_lab.evaluation.runner import run_evaluation
from agent_lab.evaluation.tracing import JsonlTraceWriter


def _read_trace(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_trace_summarizes_tool_calls_steps_and_final_status(tmp_path) -> None:
    class OneBalanceCall:
        def decide(self, history):
            return ToolCallDecision("get_my_balance", {"asset": "USDT"})

    trace_path = tmp_path / "agent.jsonl"
    agent = AgentLoop(
        OneBalanceCall(),
        ToolDispatcher(create_demo_tool_registry()),
        max_steps=1,
    )

    with pytest.raises(MaxStepsExceeded, match="max_steps=1"):
        asyncio.run(
            agent.run(
                "Read my balance",
                "user-123",
                trace=JsonlTraceWriter(trace_path),
                run_id="run-max-steps",
            )
        )

    records = _read_trace(trace_path)
    summary = next(row for row in records if row["event"] == "run_finished")
    assert summary["step_count"] == 1
    assert summary["final_status"] == "MAX_STEPS_EXCEEDED"
    assert summary["tool_call_history"] == [
        {
            "step": 1,
            "tool_name": "get_my_balance",
            "arguments": {"asset": "USDT"},
        }
    ]


def test_tool_rejection_is_written_to_jsonl_trace(tmp_path) -> None:
    class InvalidCallModel:
        def decide(self, history):
            return ToolCallDecision("delete_account", {})

    trace_path = tmp_path / "rejected.jsonl"
    agent = AgentLoop(
        InvalidCallModel(),
        ToolDispatcher(create_demo_tool_registry()),
        max_steps=1,
    )

    with pytest.raises(ValueError, match="Tool is not allowed"):
        asyncio.run(
            agent.run(
                "Delete account",
                "user-123",
                trace=JsonlTraceWriter(trace_path),
                run_id="run-rejected-tool",
            )
        )

    records = _read_trace(trace_path)
    assert any(row["event"] == "tool_error" for row in records)
    summary = next(row for row in records if row["event"] == "run_finished")
    assert summary["final_status"] == "TOOL_REJECTED"
    assert summary["error_type"] == "ValueError"


def test_fake_evaluation_runs_all_six_cases_and_reports_metrics(tmp_path) -> None:
    result = asyncio.run(
        run_evaluation(
            mode="fake",
            trace_path=tmp_path / "evaluation.jsonl",
        )
    )

    assert len(result["scenarios"]) == 6
    assert all(row["passed"] for row in result["scenarios"])
    assert result["metrics"]["task_success_rate"] == {
        "passed": 6,
        "total": 6,
        "rate": 1.0,
    }
    assert result["metrics"]["tool_selection_accuracy"] == {
        "correct": 4,
        "total": 4,
        "rate": 1.0,
    }
    assert result["metrics"]["unauthorized_action_count"] == 0
    assert result["metrics"]["unauthorized_attempt_count"] == 1


def test_model_timeout_has_a_distinct_final_trace_status(tmp_path) -> None:
    class SlowModel:
        def decide(self, history):
            time.sleep(0.05)
            return FinalAnswerDecision("late response")

    trace_path = tmp_path / "model-timeout.jsonl"
    agent = AgentLoop(
        SlowModel(),
        ToolDispatcher(create_demo_tool_registry()),
        max_steps=1,
        model_timeout_seconds=0.005,
    )

    with pytest.raises(ModelDecisionTimeout):
        asyncio.run(
            agent.run(
                "Wait for a slow model",
                "user-123",
                trace=JsonlTraceWriter(trace_path),
                run_id="model-timeout",
            )
        )

    summary = next(
        row for row in _read_trace(trace_path) if row["event"] == "run_finished"
    )
    assert summary["final_status"] == "MODEL_TIMEOUT"


def test_tool_timeout_has_a_distinct_final_trace_status(tmp_path) -> None:
    class BalanceCallModel:
        def decide(self, history):
            return ToolCallDecision("slow_tool", {})

    async def slow_tool(*, user_id):
        await asyncio.sleep(0.05)
        return {"user_id": user_id}

    registry = ToolRegistry()
    registry.register(
        "slow_tool",
        slow_tool,
        {"type": "object", "properties": {}, "additionalProperties": False},
    )
    trace_path = tmp_path / "tool-timeout.jsonl"
    agent = AgentLoop(
        BalanceCallModel(),
        ToolDispatcher(registry, tool_timeout_seconds=0.005),
        max_steps=1,
    )

    with pytest.raises(ToolExecutionTimeout):
        asyncio.run(
            agent.run(
                "Call a slow tool",
                "user-123",
                trace=JsonlTraceWriter(trace_path),
                run_id="tool-timeout",
            )
        )

    summary = next(
        row for row in _read_trace(trace_path) if row["event"] == "run_finished"
    )
    assert summary["final_status"] == "TOOL_TIMEOUT"
