from typing import Any

from agent_lab.tools.registry import ToolRegistry


SIMULATED_BALANCES: dict[str, dict[str, int]] = {
    "user-123": {"USDT": 500},
}


def get_my_balance(*, user_id: str, asset: str) -> dict[str, Any]:
    """Read a balance from the in-memory demo data."""
    balance = SIMULATED_BALANCES.get(user_id, {}).get(asset, 0)
    return {"asset": asset, "balance": balance}


def create_demo_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register("get_my_balance", get_my_balance)
    return registry
