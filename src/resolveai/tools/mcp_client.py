"""Thin MCP client: spawns a tool server as a subprocess over stdio and calls tools on it.

This is the real MCP wire protocol (JSON-RPC over stdio), not a fake -- the
same client code would talk to any compliant MCP server, mock or production.
A `contextlib.AsyncExitStack`-based connection pool would be a reasonable
V2 optimization to avoid respawning a subprocess per call; V1 keeps it simple
and explicit (one call = one clean subprocess lifecycle = no shared-state bugs).
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

MCP_SERVERS: dict[str, str] = {
    "crm": "resolveai.tools.mcp_crm_server",
    "ticketing": "resolveai.tools.mcp_ticketing_server",
}

# The MCP server runs as a *subprocess*, so it needs `resolveai` importable
# even though it wasn't `pip install -e`'d -- ensure its PYTHONPATH includes
# our own src/ directory (three parents up from this file: tools -> resolveai -> src).
_SRC_DIR = str(Path(__file__).resolve().parents[2])


@asynccontextmanager
async def mcp_session(server_key: str):
    module = MCP_SERVERS[server_key]
    env = {**os.environ, "PYTHONPATH": _SRC_DIR + os.pathsep + os.environ.get("PYTHONPATH", "")}
    params = StdioServerParameters(command=sys.executable, args=["-m", module], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def call_mcp_tool(server_key: str, tool_name: str, arguments: dict) -> dict:
    """Spawn `server_key`'s MCP server, call `tool_name`, return its parsed JSON result."""
    async with mcp_session(server_key) as session:
        result = await session.call_tool(tool_name, arguments)
        if result.is_error:
            texts = [block.text for block in result.content if hasattr(block, "text")]
            raise RuntimeError(f"MCP tool '{tool_name}' on '{server_key}' errored: {'; '.join(texts)}")
        for block in result.content:
            if hasattr(block, "text"):
                try:
                    return json.loads(block.text)
                except json.JSONDecodeError:
                    return {"raw": block.text}
        return {}
