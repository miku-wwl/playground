import asyncio
from agent_lab.core.history import MessageHistory
from agent_lab.models.decisions import FinalAnswerDecision, ToolCallDecision
from typing import Protocol

from agent_lab.models.decisions import ModelDecision
from agent_lab.tools.approval import PENDING_APPROVAL
from agent_lab.tools.dispatcher import ToolDispatcher


class MaxStepsExceeded(RuntimeError):
    pass


class ModelDecisionTimeout(TimeoutError):
    pass


class ModelClient(Protocol):
    def decide(self, history: MessageHistory) -> ModelDecision:
        """Return the model's next structured decision."""


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

    async def run(self, user_request: str, authenticated_user_id: str) -> str:
        history = MessageHistory()
        history.add_user(user_request)

        for step_number in range(1, self._max_steps + 1):
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
                history.add_tool_call(decision.tool_name, decision.arguments)
                print(
                    f"TRACE step={step_number} model_decision=tool_call "
                    f"tool={decision.tool_name} arguments={decision.arguments}"
                )
                result = await self._dispatcher.dispatch(
                    decision.tool_name,
                    decision.arguments,
                    authenticated_user_id,
                )
                history.add_tool_result(decision.tool_name, result)
                print(f"TRACE step={step_number} tool_result={result}")
                if isinstance(result, dict) and result.get("status") == PENDING_APPROVAL:
                    approval_id = result["approval_id"]
                    print(f"TRACE step={step_number} agent_state={PENDING_APPROVAL}")
                    return (
                        f"Action {decision.tool_name} is pending human approval "
                        f"(approval_id={approval_id}); nothing has been executed."
                    )
                continue

            if isinstance(decision, FinalAnswerDecision):
                history.add_final_answer(decision.answer)
                print(f"TRACE step={step_number} final_answer={decision.answer}")
                return decision.answer

            raise TypeError(f"Unsupported model decision: {type(decision).__name__}")

        raise MaxStepsExceeded(f"Agent stopped after reaching max_steps={self._max_steps}")
