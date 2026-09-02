"""MCP tool server exposing CRM data (customer profile + order lookups).

Run standalone for manual testing:
    python -m resolveai.tools.mcp_crm_server

In the graph, this is spawned as a subprocess and talked to over stdio via
`resolveai.tools.mcp_client` -- the same integration pattern used for any
real enterprise MCP server (this one just serves mock data instead of a live
CRM API).
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from resolveai.tools.mock_data import CUSTOMERS, ORDERS

server = MCPServer(name="resolveai-crm")


@server.tool()
def get_customer(customer_id: str) -> dict:
    """Look up a customer's profile and their order IDs by customer_id."""
    customer = CUSTOMERS.get(customer_id)
    if customer is None:
        return {"found": False, "customer_id": customer_id}
    return {"found": True, **customer}


@server.tool()
def get_order(order_id: str) -> dict:
    """Look up an order's amount, fulfillment status, and tracking status by order_id."""
    order = ORDERS.get(order_id)
    if order is None:
        return {"found": False, "order_id": order_id}
    return {"found": True, **order}


if __name__ == "__main__":
    import asyncio

    asyncio.run(server.run_stdio_async())
