import argparse

from agent_lab.core.agent import AgentLoop
from agent_lab.models.ollama_model import OllamaModelClient
from agent_lab.tools.demo_tools import create_demo_tool_registry
from agent_lab.tools.dispatcher import ToolDispatcher


SCENARIOS = {
    "balance": "What is my USDT balance?",
    "order": "What is the status of my order ORD-001?",
    "unsupported": "Can you predict tomorrow's Bitcoin price?",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Mini Trading Support Agent demo")
    parser.add_argument("--scenario", choices=SCENARIOS, default="balance")
    parser.add_argument("--model-name", default="phi4-mini:latest")
    args = parser.parse_args()

    model = OllamaModelClient(args.model_name)
    user_request = SCENARIOS[args.scenario]
    print(f"MODEL_CLIENT: Ollama ({args.model_name})")
    print(f"USER_REQUEST: {user_request}")

    agent = AgentLoop(
        model=model,
        dispatcher=ToolDispatcher(create_demo_tool_registry()),
        max_steps=3,
    )
    answer = agent.run(user_request=user_request, authenticated_user_id="user-123")
    print(f"FINAL ANSWER: {answer}")


if __name__ == "__main__":
    main()
