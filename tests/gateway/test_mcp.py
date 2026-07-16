import pytest
import json
from main import create_mcp_server

@pytest.mark.asyncio
async def test_mcp_tool_execution():
    mcp = create_mcp_server()
    # It has 'execute_neelvak_agent_matrix' tool
    tools = await mcp.list_tools()
    assert "execute_neelvak_agent_matrix" in [t.name for t in tools]

@pytest.mark.asyncio
async def test_mcp_resource_execution():
    mcp = create_mcp_server()
    # It has 'neelvak://history' resource
    resources = await mcp.list_resources()
    assert "neelvak://history" in [str(r.uri) for r in resources]
