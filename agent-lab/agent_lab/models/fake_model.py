from agent_lab.core.history import MessageHistory
from agent_lab.models.decisions import FinalAnswerDecision, ModelDecision, ToolCallDecision


class FakeModelClient:
    """A scripted model: call the balance tool, then answer from its result."""

    def decide(self, history: MessageHistory) -> ModelDecision:
        result = history.latest_tool_result()
        if result is None:
            return ToolCallDecision(
                tool_name="get_my_balance",
                arguments={"asset": "USDT"},
            )

        if not isinstance(result, dict):
            raise TypeError("The balance tool must return a dictionary")

        return FinalAnswerDecision(
            answer=f"Your {result['asset']} balance is {result['balance']}."
        )
