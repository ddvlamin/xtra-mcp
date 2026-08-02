import pytest
from xtra.logic import extract_ingredients, clean_ingredient

def test_extract_ingredients():
    md = """
# Recipe
## 🛒 Ingrediënten
* **Eiwit:** 3 kipfilets
* **Groenten:** 1 rode paprika, 1 courgette
* **Smaakmakers:** 2 tl rode currypasta
"""
    ingredients = extract_ingredients(md)
    assert "3 kipfilets" in ingredients
    assert "1 rode paprika" in ingredients
    assert "1 courgette" in ingredients
    assert "2 tl rode currypasta" in ingredients

def test_clean_ingredient():
    assert clean_ingredient("3 kipfilets") == "kipfilets"
    assert clean_ingredient("½ l kokosmelk") == "kokosmelk"
    assert clean_ingredient("2 dikke koffielepels rode currypasta") == "rode currypasta"
    assert clean_ingredient("1 rode paprika") == "rode paprika"
    assert clean_ingredient("enkele sperzieboontjes") == "sperzieboontjes"
    assert clean_ingredient("1 kop basmatirijst") == "basmatirijst"

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

