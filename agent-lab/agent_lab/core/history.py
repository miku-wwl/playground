class MessageHistory:
    """Keeps the messages exchanged during one Agent run."""

    def __init__(self) -> None:
        self._messages: list[dict[str, object]] = []

    def add_user(self, text: str) -> None:
        self._messages.append({"role": "user", "content": text})

    def add_tool_call(self, tool_name: str, arguments: dict[str, object]) -> None:
        self._messages.append({
            "role": "assistant",
            "type": "tool_call",
            "tool_name": tool_name,
            "arguments": arguments,
        })

    def add_tool_result(self, tool_name: str, result: object) -> None:
        self._messages.append({
            "role": "tool",
            "tool_name": tool_name,
            "content": result,
        })

    def add_final_answer(self, text: str) -> None:
        self._messages.append({"role": "assistant", "type": "final", "content": text})

    def latest_tool_result(self) -> object | None:
        for message in reversed(self._messages):
            if message["role"] == "tool":
                return message["content"]
        return None

    @property
    def messages(self) -> list[dict[str, object]]:
        return list(self._messages)
