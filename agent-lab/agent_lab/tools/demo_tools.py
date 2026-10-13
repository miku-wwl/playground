from typing import Any

from agent_lab.tools.registry import ToolRegistry


SIMULATED_BALANCES: dict[str, dict[str, int]] = {
    "user-123": {"USDT": 500},
}

SIMULATED_ORDERS: dict[str, dict[str, str]] = {
    "user-123": {"ORD-001": "FILLED"},
}


def get_my_balance(*, user_id: str, asset: str) -> dict[str, Any]:
    """Read a balance from the in-memory demo data."""
    balance = SIMULATED_BALANCES.get(user_id, {}).get(asset, 0)
    return {"asset": asset, "balance": balance}


def get_order_status(*, user_id: str, order_id: str) -> dict[str, str]:
    """Read one of the current user's orders from the in-memory demo data."""
    status = SIMULATED_ORDERS.get(user_id, {}).get(order_id)
    return {"order_id": order_id, "status": status or "NOT_FOUND"}


def create_demo_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register("get_my_balance", get_my_balance)
    registry.register("get_order_status", get_order_status)
    return registry
