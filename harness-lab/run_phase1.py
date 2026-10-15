"""Print the real context package and show that the Mock Agent received it."""

import json
from pathlib import Path

from harness.context import ContextLoader
from harness.mock_agent import MockCodingAgent


def main() -> None:
    project_root = Path(__file__).resolve().parent
    context = ContextLoader(project_root).load()

    print("=== Context Package loaded from disk ===")
    print(json.dumps(context.to_dict(), ensure_ascii=False, indent=2))

    agent = MockCodingAgent()
    receipt = agent.receive_context(context)
    print("=== Mock Agent receipt ===")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    print(f"same_context_object={agent.last_context is context}")


if __name__ == "__main__":
    main()
