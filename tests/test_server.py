import json
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
        data = json.loads(result[0].text)
        assert data["status"] == "stored"
        assert data["query"] == "visbouillon"
        assert data["product"]["product_id"] == "4170742"
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
        data = json.loads(result[0].text)
        assert data["status"] == "resolved"
        assert data["query"] == "kipfilet"
        assert data["product"]["name"] == "Kipfilet"
        assert data["product"]["product_id"] == "4804565"

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

@pytest.mark.asyncio
async def test_server_call_resolve_ingredient_ambiguous_numbered_and_other():
    mock_client = MagicMock()
    mock_client.session_id = "dummy_session"
    mock_client.get_most_bought_products = AsyncMock(return_value=[])
    server_module.client = mock_client

    sample_products = [
        Product(name=f"Prod {i}", product_id=str(i), top_category_name="Zuivel" if i == 1 else None)
        for i in range(1, 8)
    ]

    with patch("xtra.server.resolve_ingredient", new=AsyncMock(return_value=("test_ing", sample_products))):
        # Default offset = 0, limit = 5
        result = await server_module.handle_call_tool("resolve_ingredient", {"ingredient": "test_ing"})
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "ambiguous"
        assert len(data["results"]) == 5
        assert data["results"][0]["product_id"] == "1"
        assert data["results"][4]["product_id"] == "5"
        assert "presentation_markdown" in data
        assert "1. Prod 1 (1) - Zuivel" in data["presentation_markdown"]
        assert "5. Prod 5 (5)" in data["presentation_markdown"]
        assert "6. Next page" in data["presentation_markdown"]

        # Page 2 (offset = 5)
        result_pg2 = await server_module.handle_call_tool("resolve_ingredient", {"ingredient": "test_ing", "offset": 5})
        data_pg2 = json.loads(result_pg2[0].text)
        assert data_pg2["status"] == "ambiguous"
        assert len(data_pg2["results"]) == 2
        assert data_pg2["results"][0]["product_id"] == "6"
        assert data_pg2["results"][1]["product_id"] == "7"
        assert data_pg2["pagination"]["has_more"] is False
        assert data_pg2["pagination"]["next_offset"] is None
        assert "1. Prod 6 (6)" in data_pg2["presentation_markdown"]
        assert "2. Prod 7 (7)" in data_pg2["presentation_markdown"]
        assert "Next page" not in data_pg2["presentation_markdown"]

@pytest.mark.asyncio
async def test_server_product_assistant_mode_prompt():
    prompts = await server_module.handle_list_prompts()
    prompt_names = [p.name for p in prompts]
    assert "product_assistant_mode" in prompt_names

    prompt_res = await server_module.handle_get_prompt("product_assistant_mode")
    assert prompt_res is not None
    messages = prompt_res.messages
    assert len(messages) >= 1
    assert "presentation_markdown" in messages[0].content.text
    assert "store_resolved_product" in messages[0].content.text
    assert "next_offset" in messages[0].content.text

