import pytest
from src.logic import extract_ingredients, clean_ingredient

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
