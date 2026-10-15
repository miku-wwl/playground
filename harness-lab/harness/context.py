"""Load a small, explicit set of files into a Coding Agent context package."""

from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class ContextPackage:
    """The task and selected repository information passed to an Agent."""

    task_description: str
    repository_instructions: str
    relevant_files: dict[str, str]
    acceptance_criteria: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly view for display, logging, or a model adapter."""
        return asdict(self)


class ContextLoader:
    """Build context from an explicit file list instead of reading the whole repo."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)

    def load(self) -> ContextPackage:
        """Read the task, project guidance, one relevant source file, and criteria."""
        return ContextPackage(
            task_description=self._read("TASK.md"),
            repository_instructions=self._read("AGENTS.md"),
            relevant_files={
                "sample_app/pricing.py": self._read("sample_app/pricing.py"),
            },
            acceptance_criteria=self._read("sample_app/ACCEPTANCE.md"),
        )

    def _read(self, relative_path: str) -> str:
        return (self.project_root / relative_path).read_text(encoding="utf-8")
