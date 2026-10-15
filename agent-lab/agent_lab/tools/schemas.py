from typing import Any


TOOL_ARGUMENT_SCHEMAS: dict[str, dict[str, Any]] = {
    "get_my_balance": {
        "type": "object",
        "properties": {"asset": {"type": "string", "enum": ["USDT"]}},
        "required": ["asset"],
        "additionalProperties": False,
    },
    "get_order_status": {
        "type": "object",
        "properties": {
            "order_id": {"type": "string", "minLength": 1, "maxLength": 32}
        },
        "required": ["order_id"],
        "additionalProperties": False,
    },
    "create_support_ticket": {
        "type": "object",
        "properties": {
            "order_id": {"type": "string", "minLength": 1, "maxLength": 32},
            "reason": {"type": "string", "minLength": 10, "maxLength": 500},
        },
        "required": ["order_id", "reason"],
        "additionalProperties": False,
    },
}


def build_model_decision_schema() -> dict[str, Any]:
    tool_call_schemas = []
    for tool_name, arguments_schema in TOOL_ARGUMENT_SCHEMAS.items():
        tool_call_schemas.append(
            {
                "type": "object",
                "properties": {
                    "type": {"enum": ["tool_call"]},
                    "tool": {"enum": [tool_name]},
                    "arguments": arguments_schema,
                },
                "required": ["type", "tool", "arguments"],
                "additionalProperties": False,
            }
        )

    final_answer_schema = {
        "type": "object",
        "properties": {
            "type": {"enum": ["final"]},
            "answer": {"type": "string", "minLength": 1},
        },
        "required": ["type", "answer"],
        "additionalProperties": False,
    }
    return {"oneOf": [*tool_call_schemas, final_answer_schema]}
