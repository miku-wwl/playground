import asyncio
from jsonschema import ValidationError, validate

from agent_lab.tools.approval import ApprovalStore, PENDING_APPROVAL
from agent_lab.tools.registry import ToolRegistry


class InvalidToolArguments(ValueError):
    """The requested tool arguments do not match its schema."""


class ToolExecutionTimeout(TimeoutError):
    """A tool did not finish before its configured timeout."""


class ToolDispatcher:
    """Validates, authorizes, and executes only registered tool functions."""

    def __init__(self, registry: ToolRegistry, tool_timeout_seconds: float = 5) -> None:
        if tool_timeout_seconds <= 0:
            raise ValueError("tool_timeout_seconds must be positive")
        self._registry = registry
        self._tool_timeout_seconds = tool_timeout_seconds
        self._approvals = ApprovalStore()

    async def dispatch(
        self,
        tool_name: str,
        arguments: dict[str, object],
        authenticated_user_id: str,
    ) -> object:
        if not authenticated_user_id:
            raise PermissionError("An authenticated user is required")
        definition = self._registry.get(tool_name)
        self._validate_arguments(definition.name, arguments, definition.arguments_schema)

        if definition.requires_approval:
            request = self._approvals.create(
                definition.name,
                arguments,
                authenticated_user_id,
            )
            return {
                "status": PENDING_APPROVAL,
                "approval_id": request["approval_id"],
                "tool_name": request["tool_name"],
                "arguments": request["arguments"],
                "authenticated_user_id": request["authenticated_user_id"],
            }

        return await self._execute(
            definition.name,
            arguments,
            authenticated_user_id,
        )

    def pending_approvals(self) -> list[dict[str, object]]:
        return self._approvals.pending()

    async def resolve_approval(
        self,
        approval_id: str,
        *,
        approved: bool,
        approver_id: str,
    ) -> dict[str, object]:
        if not approver_id:
            raise PermissionError("An identified human approver is required")
        request = self._approvals.decide(
            approval_id,
            approved=approved,
            approver_id=approver_id,
        )
        if not approved:
            return request

        tool_name = str(request["tool_name"])
        arguments = request["arguments"]
        user_id = str(request["authenticated_user_id"])
        definition = self._registry.get(tool_name)
        self._validate_arguments(tool_name, arguments, definition.arguments_schema)
        try:
            result = await self._execute(tool_name, arguments, user_id)
        except Exception as error:
            self._approvals.mark_failed(approval_id, str(error))
            raise
        self._approvals.mark_executed(approval_id, result)
        return {
            **request,
            "status": "EXECUTED",
            "result": result,
        }

    async def _execute(
        self,
        tool_name: str,
        arguments: dict[str, object],
        authenticated_user_id: str,
    ) -> object:
        definition = self._registry.get(tool_name)
        try:
            return await asyncio.wait_for(
                definition.function(
                    user_id=authenticated_user_id,
                    **arguments,
                ),
                timeout=self._tool_timeout_seconds,
            )
        except TimeoutError as error:
            raise ToolExecutionTimeout(
                f"Tool {tool_name} exceeded {self._tool_timeout_seconds:g} seconds"
            ) from error

    @staticmethod
    def _validate_arguments(
        tool_name: str,
        arguments: object,
        schema: dict[str, object],
    ) -> None:
        try:
            validate(instance=arguments, schema=schema)
        except ValidationError as error:
            raise InvalidToolArguments(
                f"Invalid arguments for {tool_name} at {error.json_path}: {error.message}"
            ) from error
