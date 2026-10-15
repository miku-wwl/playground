import asyncio
from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any


ToolFunction = Callable[..., Awaitable[object]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    function: ToolFunction
    arguments_schema: dict[str, Any]
    requires_approval: bool = False


class ToolRegistry:
    """Stores the Python functions that the Agent is allowed to call."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        function: ToolFunction,
        arguments_schema: dict[str, Any],
        *,
        requires_approval: bool = False,
    ) -> None:
        if name in self._tools:
            raise ValueError(f"Tool is already registered: {name}")
        if not asyncio.iscoroutinefunction(function):
            raise TypeError("Tool functions must be async so their timeout can cancel execution")
        self._tools[name] = ToolDefinition(
            name=name,
            function=function,
            arguments_schema=deepcopy(arguments_schema),
            requires_approval=requires_approval,
        )

    def get(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            raise ValueError(f"Tool is not allowed: {name}")
        return self._tools[name]
