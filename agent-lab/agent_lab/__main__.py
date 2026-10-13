from agent_lab.core.agent import AgentLoop
from agent_lab.models.fake_model import FakeModelClient
from agent_lab.tools.demo_tools import create_demo_tool_registry
from agent_lab.tools.dispatcher import ToolDispatcher


def main() -> None:
    agent = AgentLoop(
        model=FakeModelClient(),
        dispatcher=ToolDispatcher(create_demo_tool_registry()),
        max_steps=3,
    )
    answer = agent.run(
        user_request="What is my USDT balance?",
        authenticated_user_id="user-123",
    )
    print(f"FINAL ANSWER: {answer}")


if __name__ == "__main__":
    main()
