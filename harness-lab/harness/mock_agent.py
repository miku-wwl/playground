"""Deterministic stand-in that demonstrates the Agent receives the context."""

from typing import Any

from harness.context import ContextPackage


class MockCodingAgent:
    """Receive and summarize a ContextPackage; it does not modify the project."""

    def __init__(self) -> None:
        self.last_context: ContextPackage | None = None

    def receive_context(self, context: ContextPackage) -> dict[str, Any]:
        self.last_context = context
        title = next(
            (line.removeprefix("# ") for line in context.task_description.splitlines() if line.startswith("# ")),
            "(no task title)",
        )
        return {
            "received_task": title,
            "source_files": list(context.relevant_files),
            "has_repository_instructions": bool(context.repository_instructions.strip()),
            "has_acceptance_criteria": bool(context.acceptance_criteria.strip()),
            "proposed_change": None,
        }
