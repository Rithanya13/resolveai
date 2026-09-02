"""Exercises the real MCP wire protocol: spawns each tool server as an actual
subprocess and talks JSON-RPC over stdio to it. Slower than the stubbed unit
tests (subprocess startup cost) but this is what proves the MCP integration
itself works, not just the code that calls it.
"""

import pytest

from resolveai.tools.mcp_client import call_mcp_tool


@pytest.mark.asyncio
async def test_crm_get_customer_found():
    result = await call_mcp_tool("crm", "get_customer", {"customer_id": "cust_1001"})
    assert result["found"] is True
    assert result["name"] == "Jordan Alvarez"


@pytest.mark.asyncio
async def test_crm_get_customer_not_found():
    result = await call_mcp_tool("crm", "get_customer", {"customer_id": "does_not_exist"})
    assert result["found"] is False


@pytest.mark.asyncio
async def test_crm_get_order_found():
    result = await call_mcp_tool("crm", "get_order", {"order_id": "order_5001"})
    assert result["found"] is True
    assert result["amount_usd"] == 84.99


@pytest.mark.asyncio
async def test_ticketing_get_ticket_history():
    result = await call_mcp_tool("ticketing", "get_ticket_history", {"customer_id": "cust_1002"})
    assert len(result["tickets"]) == 1


@pytest.mark.asyncio
async def test_ticketing_create_refund_returns_confirmation():
    result = await call_mcp_tool(
        "ticketing", "create_refund", {"order_id": "order_5002", "amount_usd": 42.5, "reason": "test"}
    )
    assert result["status"] == "issued"
    assert result["confirmation_id"].startswith("rfnd_")
