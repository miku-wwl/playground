from dataclasses import dataclass
from typing import TypeAlias


@dataclass(frozen=True)
class ToolCallDecision:
    tool_name: str
    arguments: dict[str, object]


@dataclass(frozen=True)
class FinalAnswerDecision:
    answer: str


ModelDecision: TypeAlias = ToolCallDecision | FinalAnswerDecision
