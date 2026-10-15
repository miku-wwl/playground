from pathlib import Path

from harness.context import ContextLoader
from harness.mock_agent import MockCodingAgent


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_loader_reads_task_guidance_source_and_acceptance_criteria() -> None:
    package = ContextLoader(PROJECT_ROOT).load()

    assert "apply_discount" in package.task_description
    assert "Do not claim" in package.repository_instructions
    assert "intentionally contains a bug" in package.relevant_files["sample_app/pricing.py"]
    assert "80.00" in package.acceptance_criteria
    assert set(package.relevant_files) == {"sample_app/pricing.py"}


def test_mock_agent_receives_the_context_package_without_proposing_a_change() -> None:
    package = ContextLoader(PROJECT_ROOT).load()
    agent = MockCodingAgent()

    receipt = agent.receive_context(package)

    assert agent.last_context is package
    assert receipt["received_task"] == "Task: Fix the pricing discount calculation"
    assert receipt["source_files"] == ["sample_app/pricing.py"]
    assert receipt["has_repository_instructions"] is True
    assert receipt["has_acceptance_criteria"] is True
    assert receipt["proposed_change"] is None
