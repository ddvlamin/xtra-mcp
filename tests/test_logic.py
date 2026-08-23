import pytest
from xtra.logic import extract_ingredients_section

def test_extract_ingredients_section():
    md = """
# Recipe
## 🛒 Ingrediënten
* **Eiwit:** 3 kipfilets
* **Groenten:** 1 rode paprika, 1 courgette
* **Smaakmakers:** 2 tl rode currypasta
## Instructions
1. Mix.
"""
    section = extract_ingredients_section(md)
    assert "* **Eiwit:** 3 kipfilets" in section
    assert "* **Groenten:** 1 rode paprika, 1 courgette" in section
    assert "Instructions" not in section

@pytest.mark.asyncio
async def test_store_resolved_product():
    from xtra.logic import store_resolved_product
    from xtra.db import Database
    db = Database(":memory:")
    stored = await store_resolved_product(
        ingredient="rode currypasta",
        product_id="111222",
        name="Rode Curry Pasta 200g",
        brand="BONI",
        db=db
    )
    assert stored.normalized_name == "rode currypasta"
    assert stored.product_id == "111222"
    assert stored.name == "Rode Curry Pasta 200g"

    found = db.find_product("rode currypasta")
    assert found is not None
    assert found.product_id == "111222"

def test_format_ingredient_label():
    from xtra.logic import format_ingredient_label
    from xtra.models import ExtractedIngredient

    assert format_ingredient_label(ExtractedIngredient(name="bloem", quantity=200, unit="g")) == "bloem (200 g)"
    assert format_ingredient_label(ExtractedIngredient(name="kipfilets", quantity=3, unit=None)) == "kipfilets (3)"
    assert format_ingredient_label(ExtractedIngredient(name="zout", quantity=None, unit=None)) == "zout"
    assert format_ingredient_label({"name": "melk", "quantity": 100, "unit": "ml"}) == "melk (100 ml)"
    assert format_ingredient_label("peper") == "peper"

def test_format_resolved_products_list():
    from xtra.logic import format_resolved_products_list
    from xtra.models import ExtractedIngredient, Product

    items = [
        (ExtractedIngredient(name="bloem", quantity=200, unit="g"), Product(name="Tarwebloem", product_id="12345")),
        (ExtractedIngredient(name="melk", quantity=100, unit="ml"), Product(name="Volle melk", product_id="67890")),
    ]
    md_list = format_resolved_products_list(items)
    assert md_list == "- bloem (200 g) [productId=12345]\n- melk (100 ml) [productId=67890]"

def test_append_or_update_recipe_section_new():
    from xtra.logic import append_or_update_recipe_section

    recipe_md = "# Recipe\n\n## Ingredients\n- 200 g bloem\n\n## Instructions\n1. Mix.\n"
    body = "- bloem (200 g) [productId=12345]"
    updated = append_or_update_recipe_section(recipe_md, "Resolved Products", body)

    assert "## Resolved Products\n- bloem (200 g) [productId=12345]\n" in updated
    assert updated.startswith("# Recipe")

def test_append_or_update_recipe_section_replace():
    from xtra.logic import append_or_update_recipe_section

    recipe_md = """# Recipe
## Ingredients
- 200 g bloem
## Resolved Products
- old item [productId=999]
## Instructions
1. Mix.
"""
    body = "- bloem (200 g) [productId=12345]"
    updated = append_or_update_recipe_section(recipe_md, "Resolved Products", body)

    assert "old item" not in updated
    assert "## Resolved Products\n- bloem (200 g) [productId=12345]\n" in updated
    assert "## Instructions\n1. Mix." in updated


