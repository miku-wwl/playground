"""Fake LLM: a predictable Plan proposal for learning the AIG security pipeline."""

import json


class DeterministicHelloProvider:
    """Implements AIG's ModelProvider protocol, WITHOUT contacting any model.

    The runtime still performs normal schema, semantic, and risk validation.
    A real LLM adapter could replace this object at composition time.
    """

    async def generate_plan(self, intent, *, tools, plan_schema, timeout_seconds) -> str:
        del tools, plan_schema, timeout_seconds
        return json.dumps(
            {
                "goal": "Persist one explicitly approved greeting",
                "target": "hello-world",
                "steps": [
                    {
                        "tool_name": "write_greeting",
                        "tool_version": "1",
                        "arguments": {"message": intent.text},
                    }
                ],
                "risk_class": "SIDE_EFFECT",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
