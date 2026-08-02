import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import xtra.server as server_module
from xtra.models import Product
import mcp.types as types
from xtra.colruyt import ColruytClient

@pytest.mark.asyncio
async def test_server_list_tools():
    tools = await server_module.handle_list_tools()
    tool_names = [t.name for t in tools]

    # Verify exposed tools
    assert "resolve_ingredient" in tool_names
    assert "add_items_to_list" in tool_names
    assert "add_recipe_to_list" in tool_names
    assert "store_resolved_product" in tool_names

    # Verify unexposed internal tools
    assert "store_product" not in tool_names
    assert "get_most_bought_products" not in tool_names
    assert "search_products" not in tool_names

@pytest.mark.asyncio
async def test_server_call_store_resolved_product_tool():
    mock_client = MagicMock()
    mock_client.session_id = "dummy_session"
    mock_client.get_product_info = AsyncMock(return_value={})
    server_module.client = mock_client

    sample_product = Product(
        normalized_name="visbouillon",
        name="Finesse bouillon vetarme vis",
        product_id="4170742",
        brand="KNORR"
    )

    with patch("xtra.server.store_resolved_product", new=AsyncMock(return_value=sample_product)):
        result = await server_module.handle_call_tool(
            "store_resolved_product",
            {
                "ingredient": "visbouillon",
                "product_id": "4170742",
                "name": "Finesse bouillon vetarme vis",
                "brand": "KNORR"
            }
        )
        assert len(result) == 1
        assert "Stored resolved product:" in result[0].text
        assert "visbouillon" in result[0].text
        assert "4170742" in result[0].text

@pytest.mark.asyncio
async def test_server_call_resolve_ingredient_tool():
    mock_client = MagicMock()
    mock_client.session_id = "dummy_session"
    mock_client.get_most_bought_products = AsyncMock(return_value=[])
    server_module.client = mock_client

    sample_product = Product(
        name="Kipfilet",
        product_id="4804565",
        brand="BONI",
        content="500g",
        description="100% kip",
        conservation_info="Chilled",
        usage_info="Cook thoroughly"
    )

    with patch("xtra.server.resolve_ingredient", new=AsyncMock(return_value=("kipfilet", sample_product))):
        result = await server_module.handle_call_tool("resolve_ingredient", {"ingredient": "kipfilet"})
        assert len(result) == 1
        assert "Product Resolved:" in result[0].text
        assert "Kipfilet" in result[0].text
        assert "4804565" in result[0].text

@pytest.mark.asyncio
async def test_handle_call_tool_missing_session_id():
    orig_client = server_module.client
    try:
        server_module.client = None
        result = await server_module.handle_call_tool("add_items_to_list", {"product_ids": ["123"]})
        assert len(result) == 1
        assert isinstance(result[0], types.TextContent)
        assert "Error: Colruyt client not properly initialized" in result[0].text
    finally:
        server_module.client = orig_client
