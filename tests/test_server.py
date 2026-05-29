import pytest
from unittest.mock import MagicMock, AsyncMock
import src.server as server
import mcp.types as types
from src.client import ColruytClient

@pytest.mark.asyncio
async def test_handle_call_tool_missing_session_id():
    # Save original client
    orig_client = server.client
    
    try:
        # Set client to None
        server.client = None
        
        # Call a tool
        result = await server.handle_call_tool("get_most_bought_products", {})
        assert len(result) == 1
        assert isinstance(result[0], types.TextContent)
        assert "Error: Colruyt client not properly initialized" in result[0].text
        
        # Set client with no session_id
        server.client = ColruytClient(session_id="")
        result = await server.handle_call_tool("get_most_bought_products", {})
        assert len(result) == 1
        assert isinstance(result[0], types.TextContent)
        assert "Error: Colruyt client not properly initialized" in result[0].text
        
    finally:
        server.client = orig_client
