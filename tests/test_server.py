import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import xtra.server as server_module
from xtra.models import Product, ProductMapping
import xtra.server as server
import mcp.types as types
from xtra.client import ColruytClient


@pytest.mark.asyncio
async def test_server_list_tools():
    tools = await server_module.handle_list_tools()
    tool_names = [t.name for t in tools]

    # Verify new tools are present
    assert "resolve_ingredient" in tool_names
    assert "save_product_mapping" in tool_names
    assert "add_items_to_list" in tool_names
    assert "add_recipe_to_list" in tool_names

    # Verify old public search tools are removed
    assert "get_most_bought_products" not in tool_names
    assert "search_products" not in tool_names

@pytest.mark.asyncio
async def test_server_call_resolve_ingredient_tool():
    mock_client = MagicMock()
    mock_client.get_most_bought_products = AsyncMock(return_value=[])
    server_module.client = mock_client

    sample_product = Product(
        name="Kipfilet",
        technicalArticleNumber="4804565",
        brand="BONI",
        content="500g",
        description="100% kip",
        conservation_info="Chilled",
        usage_info="Cook thoroughly"
    )

    with patch("xtra.server.resolve_ingredient", new=AsyncMock(return_value=sample_product)):
        result = await server_module.handle_call_tool("resolve_ingredient", {"ingredient": "kipfilet"})
        assert len(result) == 1
        assert "Product Resolved:" in result[0].text
        assert "Kipfilet" in result[0].text
        assert "4804565" in result[0].text

@pytest.mark.asyncio
async def test_server_call_save_product_mapping_tool():
    mock_client = MagicMock()
    server_module.client = mock_client

    sample_mapping = ProductMapping(
        cleaned_ingredient="kipfilet",
        product_id="4804565",
        product_name="Kipfilet",
        product_brand="BONI",
        product_description="100% kip",
        conservation_info="Chilled",
        usage_info="Cook thoroughly",
        content="500g"
    )

    with patch("xtra.server.save_product_mapping_logic", new=AsyncMock(return_value=sample_mapping)):
        result = await server_module.handle_call_tool("save_product_mapping", {
            "cleaned_ingredient": "kipfilet",
            "product_id": "4804565",
            "product_name": "Kipfilet",
            "product_brand": "BONI"
        })
        assert len(result) == 1
        assert "Saved product mapping successfully:" in result[0].text
        assert "kipfilet" in result[0].text
        assert "4804565" in result[0].text

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
