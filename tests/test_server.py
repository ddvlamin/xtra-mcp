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
    assert "resolve_recipe" in tool_names
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
        query="visbouillon",
        name="Finesse bouillon vetarme vis",
        product_id="4170742",
        brand="KNORR",
        top_category_name="Conserven"
    )

    with patch("xtra.server.store_resolved_product", new=AsyncMock(return_value=sample_product)) as mock_store:
        result = await server_module.handle_call_tool(
            "store_resolved_product",
            {
                "ingredient": "visbouillon",
                "product_id": "4170742",
                "name": "Finesse bouillon vetarme vis",
                "brand": "KNORR",
                "top_category_name": "Conserven"
            }
        )
        assert len(result) == 1
        assert "Stored resolved product:" in result[0].text
        assert "visbouillon" in result[0].text
        assert "4170742" in result[0].text
        mock_store.assert_called_once_with(
            ingredient="visbouillon",
            product_id="4170742",
            name="Finesse bouillon vetarme vis",
            brand="KNORR",
            client=mock_client,
            top_category_name="Conserven"
        )

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
        with patch.dict("os.environ", {"CLPBFF_SESSION": ""}, clear=False):
            result = await server_module.handle_call_tool("add_items_to_list", {"product_ids": ["123"]})
            assert len(result) == 1
            assert isinstance(result[0], types.TextContent)
            assert "Error: Colruyt client not properly initialized" in result[0].text
    finally:
        server_module.client = orig_client

@pytest.mark.asyncio
async def test_server_call_resolve_ingredient_ambiguous_numbered_and_other():
    mock_client = MagicMock()
    mock_client.session_id = "dummy_session"
    mock_client.get_most_bought_products = AsyncMock(return_value=[])
    server_module.client = mock_client

    sample_products = [Product(name=f"Prod {i}", product_id=str(i)) for i in range(1, 8)]

    with patch("xtra.server.resolve_ingredient", new=AsyncMock(return_value=("test_ing", sample_products))):
        # Default offset = 0
        result = await server_module.handle_call_tool("resolve_ingredient", {"ingredient": "test_ing"})
        assert len(result) == 1
        text = result[0].text
        assert "1. Prod 1 (1)" in text
        assert "5. Prod 5 (5)" in text
        assert "6. Other" in text
        assert "6. Prod 6" not in text

        # Page 2 (offset = 5)
        result_pg2 = await server_module.handle_call_tool("resolve_ingredient", {"ingredient": "test_ing", "offset": 5})
        text_pg2 = result_pg2[0].text
        assert "1. Prod 6 (6)" in text_pg2
        assert "2. Prod 7 (7)" in text_pg2
        assert "Other" not in text_pg2

