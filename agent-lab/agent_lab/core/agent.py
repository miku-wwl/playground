import asyncio
from typing import Any, Protocol
from uuid import uuid4

from agent_lab.core.history import MessageHistory
from agent_lab.models.decisions import FinalAnswerDecision, ToolCallDecision
from agent_lab.models.decisions import ModelDecision
from agent_lab.tools.approval import PENDING_APPROVAL
from agent_lab.tools.dispatcher import ToolDispatcher, ToolExecutionTimeout


class MaxStepsExceeded(RuntimeError):
    pass


class ModelDecisionTimeout(TimeoutError):
    pass


class ModelClient(Protocol):
    def decide(self, history: MessageHistory) -> ModelDecision:
        """Return the model's next structured decision."""


class TraceSink(Protocol):
    def record(self, run_id: str, event: str, **fields: Any) -> None:
        """Record one structured Agent event."""


class AgentLoop:
    """Repeats model decision → optional tool execution until a final answer."""

    def __init__(
        self,
        model: ModelClient,
        dispatcher: ToolDispatcher,
        max_steps: int = 5,
        model_timeout_seconds: float = 65,
    ) -> None:
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")
        if model_timeout_seconds <= 0:
            raise ValueError("model_timeout_seconds must be positive")
        self._model = model
        self._dispatcher = dispatcher
        self._max_steps = max_steps
        self._model_timeout_seconds = model_timeout_seconds

    async def run(
        self,
        user_request: str,
        authenticated_user_id: str,
        *,
        trace: TraceSink | None = None,
        run_id: str | None = None,
    ) -> str:
        active_run_id = run_id or uuid4().hex
        history = MessageHistory()
        history.add_user(user_request)
        tool_call_history: list[dict[str, object]] = []
        step_count = 0
        if trace is not None:
            trace.record(
                active_run_id,
                "run_started",
                authenticated_user_id=authenticated_user_id,
                user_request=user_request,
            )

        final_status = "FAILED"
        answer: str | None = None
        try:
            for step_number in range(1, self._max_steps + 1):
                step_count = step_number
                try:
                    decision = await asyncio.wait_for(
                        asyncio.to_thread(self._model.decide, history),
                        timeout=self._model_timeout_seconds,
                    )
                except TimeoutError as error:
                    raise ModelDecisionTimeout(
                        f"Model decision exceeded {self._model_timeout_seconds:g} seconds"
                    ) from error

                if isinstance(decision, ToolCallDecision):
                    decision_type = "tool_call"
                elif isinstance(decision, FinalAnswerDecision):
                    decision_type = "final"
                else:
                    decision_type = "unsupported"
                if trace is not None:
                    trace.record(
                        active_run_id,
                        "model_decision",
                        step=step_number,
                        decision_type=decision_type,
                    )

                if isinstance(decision, ToolCallDecision):
                    history.add_tool_call(decision.tool_name, decision.arguments)
                    tool_call = {
                        "step": step_number,
                        "tool_name": decision.tool_name,
                        "arguments": decision.arguments,
                    }
                    tool_call_history.append(tool_call)
                    if trace is not None:
                        trace.record(
                            active_run_id,
                            "tool_call_requested",
                            step=step_number,
                            tool_name=decision.tool_name,
                            arguments=decision.arguments,
                            authenticated_user_id=authenticated_user_id,
                        )
                    print(
                        f"TRACE step={step_number} model_decision=tool_call "
                        f"tool={decision.tool_name} arguments={decision.arguments}"
                    )
                    try:
                        result = await self._dispatcher.dispatch(
                            decision.tool_name,
                            decision.arguments,
                            authenticated_user_id,
                        )
                    except Exception as error:
                        if trace is not None:
                            trace.record(
                                active_run_id,
                                "tool_error",
                                step=step_number,
                                tool_name=decision.tool_name,
                                error_type=type(error).__name__,
                                error_message=str(error),
                            )
                        raise

                    history.add_tool_result(decision.tool_name, result)
                    print(f"TRACE step={step_number} tool_result={result}")
                    if trace is not None:
                        trace.record(
                            active_run_id,
                            "tool_result",
                            step=step_number,
                            tool_name=decision.tool_name,
                            authenticated_user_id=authenticated_user_id,
                            result=result,
                        )
                    if isinstance(result, dict) and result.get("status") == PENDING_APPROVAL:
                        approval_id = result["approval_id"]
                        print(f"TRACE step={step_number} agent_state={PENDING_APPROVAL}")
                        answer = (
                            f"Action {decision.tool_name} is pending human approval "
                            f"(approval_id={approval_id}); nothing has been executed."
                        )
                        final_status = PENDING_APPROVAL
                        break
                    continue

                if isinstance(decision, FinalAnswerDecision):
                    history.add_final_answer(decision.answer)
                    print(f"TRACE step={step_number} final_answer={decision.answer}")
                    answer = decision.answer
                    final_status = "SUCCEEDED"
                    break

                raise TypeError(f"Unsupported model decision: {type(decision).__name__}")
            else:
                raise MaxStepsExceeded(
                    f"Agent stopped after reaching max_steps={self._max_steps}"
                )
        except Exception as error:
            if trace is not None:
                trace.record(
                    active_run_id,
                    "run_finished",
                    step_count=step_count,
                    final_status=self._error_status(error),
                    tool_call_history=tool_call_history,
                    error_type=type(error).__name__,
                    error_message=str(error),
                )
            raise

        if trace is not None:
            trace.record(
                active_run_id,
                "run_finished",
                step_count=step_count,
                final_status=final_status,
                tool_call_history=tool_call_history,
                final_answer=answer,
            )
        if answer is None:
            raise RuntimeError("Agent completed without an answer")
        return answer

    @staticmethod
    def _error_status(error: Exception) -> str:
        if isinstance(error, MaxStepsExceeded):
            return "MAX_STEPS_EXCEEDED"
        if isinstance(error, ModelDecisionTimeout):
            return "MODEL_TIMEOUT"
        if isinstance(error, ToolExecutionTimeout):
            return "TOOL_TIMEOUT"
        if isinstance(error, (ValueError, PermissionError)):
            return "TOOL_REJECTED"
        if type(error).__name__.startswith(("ModelCall", "InvalidModel")):
            return "MODEL_ERROR"
        return "FAILED"
