import asyncio
from typing import Any

from agent_lab.tools.registry import ToolRegistry
from agent_lab.tools.schemas import TOOL_ARGUMENT_SCHEMAS


SIMULATED_BALANCES: dict[str, dict[str, int]] = {
    "user-123": {"USDT": 500},
}

SIMULATED_ORDERS: dict[str, dict[str, str]] = {
    "user-123": {"ORD-001": "FILLED"},
    "user-456": {"ORD-999": "OPEN"},
}

SIMULATED_TICKETS: list[dict[str, str]] = []


async def get_my_balance(*, user_id: str, asset: str) -> dict[str, Any]:
    """Read a balance from the in-memory demo data."""
    await asyncio.sleep(0)
    balance = SIMULATED_BALANCES.get(user_id, {}).get(asset, 0)
    return {"asset": asset, "balance": balance}


async def get_order_status(*, user_id: str, order_id: str) -> dict[str, str]:
    """Read one of the current user's orders from the in-memory demo data."""
    await asyncio.sleep(0)
    status = SIMULATED_ORDERS.get(user_id, {}).get(order_id)
    return {"order_id": order_id, "status": status or "NOT_FOUND"}


async def create_support_ticket(
    *,
    user_id: str,
    order_id: str,
    reason: str,
) -> dict[str, str]:
    """Create a simulated ticket; ToolDispatcher gates this behind approval."""
    await asyncio.sleep(0)
    if order_id not in SIMULATED_ORDERS.get(user_id, {}):
        return {"status": "ORDER_NOT_FOUND", "order_id": order_id}

    ticket = {
        "ticket_id": f"TICKET-{len(SIMULATED_TICKETS) + 1:03d}",
        "user_id": user_id,
        "order_id": order_id,
        "reason": reason,
        "status": "OPEN",
    }
    SIMULATED_TICKETS.append(ticket)
    return ticket


def create_demo_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        "get_my_balance",
        get_my_balance,
        TOOL_ARGUMENT_SCHEMAS["get_my_balance"],
    )
    registry.register(
        "get_order_status",
        get_order_status,
        TOOL_ARGUMENT_SCHEMAS["get_order_status"],
    )
    registry.register(
        "create_support_ticket",
        create_support_ticket,
        TOOL_ARGUMENT_SCHEMAS["create_support_ticket"],
        requires_approval=True,
    )
    return registry
