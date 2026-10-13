from agent_lab.core.history import MessageHistory
from agent_lab.models.decisions import FinalAnswerDecision, ToolCallDecision
from typing import Protocol

from agent_lab.models.decisions import ModelDecision
from agent_lab.tools.dispatcher import ToolDispatcher


class MaxStepsExceeded(RuntimeError):
    pass


class ModelClient(Protocol):
    def decide(self, history: MessageHistory) -> ModelDecision:
        """Return the model's next structured decision."""


class AgentLoop:
    """Repeats model decision → optional tool execution until a final answer."""

    def __init__(self, model: ModelClient, dispatcher: ToolDispatcher, max_steps: int = 5) -> None:
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")
        self._model = model
        self._dispatcher = dispatcher
        self._max_steps = max_steps

    def run(self, user_request: str, authenticated_user_id: str) -> str:
        history = MessageHistory()
        history.add_user(user_request)

        for step_number in range(1, self._max_steps + 1):
            decision = self._model.decide(history)

            if isinstance(decision, ToolCallDecision):
                history.add_tool_call(decision.tool_name, decision.arguments)
                print(
                    f"TRACE step={step_number} model_decision=tool_call "
                    f"tool={decision.tool_name} arguments={decision.arguments}"
                )
                result = self._dispatcher.dispatch(
                    decision.tool_name,
                    decision.arguments,
                    authenticated_user_id,
                )
                history.add_tool_result(decision.tool_name, result)
                print(f"TRACE step={step_number} tool_result={result}")
                continue

            if isinstance(decision, FinalAnswerDecision):
                history.add_final_answer(decision.answer)
                print(f"TRACE step={step_number} final_answer={decision.answer}")
                return decision.answer

            raise TypeError(f"Unsupported model decision: {type(decision).__name__}")

        raise MaxStepsExceeded(f"Agent stopped after reaching max_steps={self._max_steps}")
