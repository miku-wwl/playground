import argparse
import asyncio
import json

from agent_lab.core.agent import AgentLoop
from agent_lab.models.ollama_model import OllamaModelClient
from agent_lab.tools.demo_tools import create_demo_tool_registry
from agent_lab.tools.dispatcher import ToolDispatcher


SCENARIOS = {
    "balance": "What is my USDT balance?",
    "order": "What is the status of my order ORD-001?",
    "unsupported": "Can you predict tomorrow's Bitcoin price?",
    "support-ticket": (
        "Please create a support ticket for order ORD-001 because its status "
        "has not updated for several days."
    ),
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

    dispatcher = ToolDispatcher(create_demo_tool_registry())
    agent = AgentLoop(
        model=model,
        dispatcher=dispatcher,
        max_steps=3,
    )
    answer = asyncio.run(
        agent.run(user_request=user_request, authenticated_user_id="user-123")
    )
    print(f"FINAL ANSWER: {answer}")
    for request in dispatcher.pending_approvals():
        print("HUMAN_REVIEW_REQUEST: " + json.dumps(request, ensure_ascii=False))
        decision = input("Review this exact request. Type APPROVE or REJECT: ").strip().upper()
        if decision not in {"APPROVE", "REJECT"}:
            raise ValueError("Enter APPROVE or REJECT")
        result = asyncio.run(
            dispatcher.resolve_approval(
                str(request["approval_id"]),
                approved=decision == "APPROVE",
                approver_id="local-operator",
            )
        )
        print("APPROVAL_RESULT: " + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
