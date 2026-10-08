import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import xtra.server as server_module
from xtra.models import Product
import mcp.types as types

@pytest.mark.asyncio
async def test_server_list_tools():
    tools = await server_module.handle_list_tools()
    tool_names = [t.name for t in tools]

    # Verify active exposed tools
    assert "start_recipe_resolution" in tool_names
    assert "resolve_ingredient_choice" in tool_names
    assert "paginate_active_ingredient" in tool_names
    assert "add_items_to_list" in tool_names
    assert "add_recipe_to_list" in tool_names

    # Verify removed redundant tools
    assert "store_resolved_product" not in tool_names
    assert "resolve_ingredient" not in tool_names
    assert "resolve_recipe" not in tool_names
    assert "annotate_recipe_with_productids" not in tool_names

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
async def test_server_call_add_recipe_to_list(tmp_path):
    mock_client = MagicMock()
    mock_client.session_id = "dummy_session"
    mock_client.add_items_to_list = AsyncMock(return_value=[{"id": "p1"}])
    server_module.client = mock_client

    recipe_file = tmp_path / "test_recipe.md"
    recipe_file.write_text("# Recipe\n## Ingredients\n- 100g bloem\n")

    sample_product = Product(name="Bloem", product_id="p1")

    with patch("xtra.server.start_resolution_session", new=AsyncMock(return_value={
        "status": "completed",
        "session_id": "s999",
        "presentation_markdown": "Done"
    })), patch("xtra.server.session_manager.get_session") as mock_get_sess:
        sess = MagicMock()
        sess.session_id = "s999"
        sess.is_completed = True
        sess.resolved_count = 1
        sess.total_count = 1
        item = MagicMock()
        item.resolved_product = sample_product
        sess.ingredients = [item]
        mock_get_sess.return_value = sess

        result = await server_module.handle_call_tool("add_recipe_to_list", {"recipe_filename": str(recipe_file)})
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["added_count"] == 1

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
    assert "resolve_ingredient_choice" in messages[0].content.text
    assert "paginate_active_ingredient" in messages[0].content.text
