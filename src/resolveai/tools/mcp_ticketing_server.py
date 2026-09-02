"""MCP tool server exposing ticketing history and refund actions.

Run standalone for manual testing:
    python -m resolveai.tools.mcp_ticketing_server
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from resolveai.tools.mock_data import TICKETS

server = MCPServer(name="resolveai-ticketing")

_refund_log: list[dict] = []  # in-memory audit log for this process's lifetime


@server.tool()
def get_ticket_history(customer_id: str) -> dict:
    """Return the list of prior support tickets filed by a customer_id."""
    return {"customer_id": customer_id, "tickets": TICKETS.get(customer_id, [])}


@server.tool()
def create_refund(order_id: str, amount_usd: float, reason: str) -> dict:
    """File a refund for an order. Mocked -- records to an in-memory audit log
    and returns a confirmation id rather than calling a real payments API."""
    confirmation_id = f"rfnd_{len(_refund_log) + 1:04d}"
    entry = {
        "confirmation_id": confirmation_id,
        "order_id": order_id,
        "amount_usd": amount_usd,
        "reason": reason,
    }
    _refund_log.append(entry)
    return {"status": "issued", **entry}


if __name__ == "__main__":
    import asyncio

    asyncio.run(server.run_stdio_async())
