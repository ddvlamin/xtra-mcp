import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import xtra.mcp.server as server_module
from xtra.catalog.db import Database
from xtra.sdk.models import Product, ListItem, ProductData
import mcp.types as types


@pytest.mark.asyncio
async def test_server_list_tools():
    tools = await server_module.handle_list_tools()
    tool_names = [t.name for t in tools]

    # Verify new focused tools
    assert "lookup_products_in_database" in tool_names
    assert "add_items_to_list" in tool_names
    assert "get_shopping_list" in tool_names
    assert "remove_items_from_list" in tool_names

    # Verify old session tools are removed
    assert "start_recipe_resolution" not in tool_names
    assert "resolve_ingredient_choice" not in tool_names
    assert "paginate_active_ingredient" not in tool_names
    assert "add_recipe_to_list" not in tool_names


@pytest.mark.asyncio
async def test_lookup_products_in_database():
    test_db = Database(":memory:")
    test_db.store_product(Product(query="boter", product_id="13805", name="Boni Roomboter", brand="BONI"))
    server_module.db = test_db

    result = await server_module.lookup_products_in_database_tool(["boter", "onbekend_ding"])
    assert result["status"] == "success"
    assert result["matched_count"] == 1
    assert result["unresolved_count"] == 1
    assert result["matches"][0]["product_id"] == "13805"
    assert "onbekend_ding" in result["unresolved"][0]["warning"]


@pytest.mark.asyncio
async def test_add_items_to_list():
    mock_client = MagicMock()
    mock_client.session_id = "test_sess"
    mock_client.add_items_to_list = AsyncMock(return_value=[
        ListItem(id="i1", description="Boter", productData=ProductData(productId="13805"))
    ])
    server_module.client = mock_client

    result = await server_module.add_items_to_list_tool(["13805"])
    assert result["status"] == "success"
    assert result["added_count"] == 1
    assert result["product_ids"] == ["13805"]
    assert result["total_list_count"] == 1
    assert mock_client.add_items_to_list.called


@pytest.mark.asyncio
async def test_get_shopping_list():
    mock_client = MagicMock()
    mock_client.session_id = "test_sess"
    mock_client.get_shopping_list = AsyncMock(return_value=[
        ListItem(id="uuid-1", description="Melk", productData=ProductData(productId="999"), createdAt="2026-10-08T12:00:00Z")
    ])
    server_module.client = mock_client

    result = await server_module.get_shopping_list_tool()
    assert result["status"] == "success"
    assert result["count"] == 1
    assert result["items"][0]["item_id"] == "uuid-1"
    assert result["items"][0]["product_id"] == "999"


@pytest.mark.asyncio
async def test_remove_items_from_list():
    mock_client = MagicMock()
    mock_client.session_id = "test_sess"
    mock_client.remove_item_from_list = AsyncMock(return_value=True)
    server_module.client = mock_client

    result = await server_module.remove_items_from_list_tool(["uuid-1", "uuid-2"])
    assert result["status"] == "success"
    assert result["removed_count"] == 2
    assert result["removed_item_ids"] == ["uuid-1", "uuid-2"]
    assert mock_client.remove_item_from_list.call_count == 2


@pytest.mark.asyncio
async def test_handle_call_tool_missing_session_id():
    orig_client = server_module.client
    try:
        server_module.client = None
        with patch.dict("os.environ", {"CLPBFF_SESSION": ""}, clear=False):
            result = await server_module.handle_call_tool("add_items_to_list", {"product_ids": ["123"]})
            assert len(result) == 1
            assert isinstance(result[0], types.TextContent)
            data = json.loads(result[0].text)
            assert data["status"] == "error"
            assert "Colruyt client not properly initialized" in data["error"]
    finally:
        server_module.client = orig_client
