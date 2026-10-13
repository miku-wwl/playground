from collections.abc import Callable


ToolFunction = Callable[..., object]


class ToolRegistry:
    """Stores the Python functions that the Agent is allowed to call."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolFunction] = {}

    def register(self, name: str, function: ToolFunction) -> None:
        if name in self._tools:
            raise ValueError(f"Tool is already registered: {name}")
        self._tools[name] = function

    def get(self, name: str) -> ToolFunction:
        if name not in self._tools:
            raise ValueError(f"Tool is not allowed: {name}")
        return self._tools[name]
