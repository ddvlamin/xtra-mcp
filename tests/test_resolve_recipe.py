import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import xtra.server as server_module
from xtra.models import Product
from xtra.logic import extract_ingredients_section, extract_ingredients_with_llm

def test_extract_ingredients_section():
    md = """---
tags: [dinner]
---
# Simple Recipe
## Ingredients
- 200 g bloem
- 100 ml melk
## Instructions
1. Mix.
"""
    sec = extract_ingredients_section(md)
    assert "- 200 g bloem" in sec
    assert "- 100 ml melk" in sec
    assert "Instructions" not in sec

from xtra.extractor import ExtractionError
from xtra.models import ExtractedIngredient

@pytest.mark.asyncio
async def test_extract_ingredients_with_llm_success():
    sample_response = {
        "message": {
            "content": '[{"name": "bloem", "quantity": 200, "unit": "g"}, {"name": "melk", "quantity": 100, "unit": "ml"}, {"name": "zout", "quantity": null, "unit": null}]'
        }
    }

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=sample_response)

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        result = await extract_ingredients_with_llm("- 200 g bloem\n- 100 ml melk\n- zout")
        assert len(result) == 3
        assert result[0] == ExtractedIngredient(name="bloem", quantity=200, unit="g")
        assert result[1] == ExtractedIngredient(name="melk", quantity=100, unit="ml")
        assert result[2] == ExtractedIngredient(name="zout", quantity=None, unit=None)

@pytest.mark.asyncio
async def test_extract_ingredients_with_llm_raises_on_error():
    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=Exception("Connection refused"))):
        with pytest.raises(ExtractionError, match="Failed to query LLM"):
            await extract_ingredients_with_llm("* 200 g bloem\n* 100 ml melk")

@pytest.mark.asyncio
async def test_server_call_resolve_recipe_tool():
    import json
    mock_client = MagicMock()
    mock_client.session_id = "dummy_session"
    mock_client.get_most_bought_products = AsyncMock(return_value=[])
    server_module.client = mock_client

    sample_product = Product(
        name="Tarwebloem",
        product_id="12345",
        brand="BONI"
    )

    recipe_md = """# Pannenkoeken
## Ingredients
- 200 g bloem
## Instructions
1. Bakken.
"""

    with patch("xtra.logic.extract_ingredients_with_llm", new=AsyncMock(return_value=[ExtractedIngredient(name="bloem", quantity=200, unit="g")])), \
         patch("xtra.logic.resolve_ingredient", new=AsyncMock(return_value=("bloem", sample_product))):
        
        result = await server_module.handle_call_tool(
            "resolve_recipe",
            {"recipe_content": recipe_md}
        )
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "complete"
        assert data["total_count"] == 1
        assert data["resolved_count"] == 1
        assert data["resolved"][0]["product"]["product_id"] == "12345"

@pytest.mark.asyncio
async def test_server_call_resolve_recipe_with_filepath(tmp_path):
    import json
    mock_client = MagicMock()
    mock_client.session_id = "dummy_session"
    mock_client.get_most_bought_products = AsyncMock(return_value=[])
    server_module.client = mock_client

    sample_product = Product(
        name="Tarwebloem",
        product_id="12345",
        brand="BONI"
    )

    recipe_file = tmp_path / "recipe.md"
    recipe_file.write_text("""# Pannenkoeken
## Ingredients
- 200 g bloem
## Instructions
1. Bakken.
""")

    with patch("xtra.logic.extract_ingredients_with_llm", new=AsyncMock(return_value=[ExtractedIngredient(name="bloem", quantity=200, unit="g")])), \
         patch("xtra.logic.resolve_ingredient", new=AsyncMock(return_value=("bloem", sample_product))):
        
        result = await server_module.handle_call_tool(
            "resolve_recipe",
            {"recipe_filename": str(recipe_file.resolve())}
        )
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "complete"
        assert data["total_count"] == 1
        assert data["resolved_count"] == 1
        assert data["resolved"][0]["product"]["product_id"] == "12345"

@pytest.mark.asyncio
async def test_server_call_resolve_recipe_ambiguous_one_at_a_time():
    import json
    mock_client = MagicMock()
    mock_client.session_id = "dummy_session"
    server_module.client = mock_client

    sample_product = Product(name="Tarwebloem", product_id="12345")
    ambig_options = [
        Product(name="Volle melk", product_id="111", brand="Campina"),
        Product(name="Halfvolle melk", product_id="222", brand="BONI"),
    ]
    ambig_options_2 = [
        Product(name="Witte suiker", product_id="333"),
        Product(name="Bruine suiker", product_id="444"),
    ]

    recipe_md = """# Pannenkoeken
## Ingredients
- 200 g bloem
- 100 ml melk
- 50 g suiker
"""

    async def mock_resolve(ing, client, **kwargs):
        if ing == "bloem":
            return "bloem", sample_product
        elif ing == "melk":
            return "melk", ambig_options
        else:
            return "suiker", ambig_options_2

    with patch("xtra.logic.extract_ingredients_with_llm", new=AsyncMock(return_value=[
        ExtractedIngredient(name="bloem", quantity=200, unit="g"),
        ExtractedIngredient(name="melk", quantity=100, unit="ml"),
        ExtractedIngredient(name="suiker", quantity=50, unit="g")
    ])), patch("xtra.logic.resolve_ingredient", side_effect=mock_resolve):
        
        result = await server_module.handle_call_tool(
            "resolve_recipe",
            {"recipe_content": recipe_md}
        )
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "incomplete"
        assert data["total_count"] == 3
        assert data["resolved_count"] == 1
        assert data["ambiguous_count"] == 2
        assert data["ambiguous"][0]["ingredient"]["name"] == "melk"
        assert len(data["ambiguous"][0]["options"]) == 2
        assert data["ambiguous"][0]["options"][0]["product_id"] == "111"

@pytest.mark.asyncio
async def test_server_call_resolve_recipe_file_not_found():
    import json
    mock_client = MagicMock()
    mock_client.session_id = "dummy_session"
    server_module.client = mock_client

    result = await server_module.handle_call_tool(
        "resolve_recipe",
        {"recipe_filename": "/nonexistent/path/recipe.md"}
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data["status"] == "error"
    assert "not found" in data["error"]

