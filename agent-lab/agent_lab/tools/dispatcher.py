from agent_lab.tools.registry import ToolRegistry


class ToolDispatcher:
    """Finds a registered tool and calls it with runtime user identity."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def dispatch(
        self,
        tool_name: str,
        arguments: dict[str, object],
        authenticated_user_id: str,
    ) -> object:
        tool = self._registry.get(tool_name)
        return tool(user_id=authenticated_user_id, **arguments)
