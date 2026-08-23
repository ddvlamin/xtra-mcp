import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import xtra.server as server_module
from xtra.models import Product

@pytest.mark.asyncio
async def test_server_list_tools_includes_annotate_recipe():
    tools = await server_module.handle_list_tools()
    tool_names = [t.name for t in tools]
    assert "annotate_recipe_with_productids" in tool_names

@pytest.mark.asyncio
async def test_annotate_recipe_success(tmp_path):
    mock_client = MagicMock()
    mock_client.session_id = "dummy_session"
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

    with patch("xtra.logic.extract_ingredients_with_llm", new=AsyncMock(return_value=[{"name": "bloem", "quantity": 200, "unit": "g"}])), \
         patch("xtra.logic.resolve_ingredient", new=AsyncMock(return_value=("bloem", sample_product))):

        result = await server_module.handle_call_tool(
            "annotate_recipe_with_productids",
            {"recipe_filename": str(recipe_file.resolve())}
        )

        assert len(result) == 1
        assert "Successfully annotated recipe" in result[0].text
        assert "## Resolved Products" in result[0].text
        assert "- bloem (200 g) [productId=12345]" in result[0].text

        # Verify file content on disk
        updated_content = recipe_file.read_text()
        assert "## Resolved Products" in updated_content
        assert "- bloem (200 g) [productId=12345]" in updated_content
        assert "## Instructions" in updated_content

@pytest.mark.asyncio
async def test_annotate_recipe_replaces_existing_section(tmp_path):
    mock_client = MagicMock()
    mock_client.session_id = "dummy_session"
    server_module.client = mock_client

    sample_product = Product(name="Tarwebloem", product_id="12345")

    recipe_file = tmp_path / "recipe.md"
    recipe_file.write_text("""# Pannenkoeken
## Ingredients
- 200 g bloem
## Resolved Products
- old item [productId=999]
## Instructions
1. Bakken.
""")

    with patch("xtra.logic.extract_ingredients_with_llm", new=AsyncMock(return_value=[{"name": "bloem", "quantity": 200, "unit": "g"}])), \
         patch("xtra.logic.resolve_ingredient", new=AsyncMock(return_value=("bloem", sample_product))):

        result = await server_module.handle_call_tool(
            "annotate_recipe_with_productids",
            {"recipe_filename": str(recipe_file.resolve())}
        )

        assert len(result) == 1
        assert "Successfully annotated recipe" in result[0].text

        updated_content = recipe_file.read_text()
        assert "old item" not in updated_content
        assert "- bloem (200 g) [productId=12345]" in updated_content

@pytest.mark.asyncio
async def test_annotate_recipe_does_not_write_when_ambiguous(tmp_path):
    mock_client = MagicMock()
    mock_client.session_id = "dummy_session"
    server_module.client = mock_client

    sample_product = Product(name="Tarwebloem", product_id="12345")
    ambig_options = [
        Product(name="Volle melk", product_id="111", brand="Campina"),
        Product(name="Halfvolle melk", product_id="222", brand="BONI"),
    ]

    recipe_file = tmp_path / "recipe.md"
    initial_content = """# Pannenkoeken
## Ingredients
- 200 g bloem
- 100 ml melk
## Instructions
1. Bakken.
"""
    recipe_file.write_text(initial_content)

    async def mock_resolve(ing, client, **kwargs):
        if ing == "bloem":
            return "bloem", sample_product
        else:
            return "melk", ambig_options

    with patch("xtra.logic.extract_ingredients_with_llm", new=AsyncMock(return_value=[
        {"name": "bloem", "quantity": 200, "unit": "g"},
        {"name": "melk", "quantity": 100, "unit": "ml"}
    ])), patch("xtra.logic.resolve_ingredient", side_effect=mock_resolve):

        result = await server_module.handle_call_tool(
            "annotate_recipe_with_productids",
            {"recipe_filename": str(recipe_file.resolve())}
        )

        assert len(result) == 1
        assert "Cannot annotate recipe: not all ingredients are resolved" in result[0].text
        assert "Please choose an option for ambiguous ingredient" in result[0].text
        assert "1. Volle melk [Campina] (111)" in result[0].text

        # Verify file on disk is UNTOUCHED
        assert recipe_file.read_text() == initial_content

@pytest.mark.asyncio
async def test_annotate_recipe_file_not_found():
    mock_client = MagicMock()
    mock_client.session_id = "dummy_session"
    server_module.client = mock_client

    result = await server_module.handle_call_tool(
        "annotate_recipe_with_productids",
        {"recipe_filename": "/nonexistent/path/recipe.md"}
    )
    assert len(result) == 1
    assert "Error: Recipe file '/nonexistent/path/recipe.md' not found." in result[0].text
