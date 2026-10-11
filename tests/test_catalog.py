import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from xtra.catalog.db import Database
from xtra.sdk.models import Product, ExtractedIngredient
from xtra.catalog.extractor import (
    extract_ingredients_section,
    parse_recipe_ingredients,
    extract_resolved_products,
    format_resolved_products_list,
    append_or_update_recipe_section,
)
from xtra.catalog.annotate import annotate_recipe_content, annotate_recipe_file
from xtra.catalog.ingest import search_and_prompt_candidate


def test_database_operations():
    db = Database(":memory:")
    p = Product(query="boter", product_id="13805", name="Boni Roomboter 250g")
    stored = db.store_product(p)
    assert stored.product_id == "13805"
    assert stored.query == "boter"

    found = db.find_product("boter")
    assert found is not None
    assert found.product_id == "13805"

    all_prods = db.get_all_products()
    assert len(all_prods) == 1

    del_count = db.delete_product(query="boter")
    assert del_count == 1
    assert db.get_product("boter") is None


def test_extractor_parse_recipe_ingredients():
    md = """
# Recipe
## Ingredients
- gehakt: 75 g
- : 1 sjalotten
- boter: 10 g
- peper, zout: snuifje
## Instructions
1. Cook
"""
    ings = parse_recipe_ingredients(md)
    names = [i.name for i in ings]
    assert "gehakt" in names
    assert "sjalotten" in names
    assert "boter" in names
    assert "peper" in names
    assert "zout" in names


def test_extractor_extract_resolved_products():
    md = """
## Resolved Products
- gehakt (75 g) [productId=1305966]
- witte wijn [productId=1584236]
"""
    res = extract_resolved_products(md)
    assert len(res) == 2
    assert res[0]["ingredient"] == "gehakt"
    assert res[0]["productId"] == "1305966"
    assert res[1]["ingredient"] == "witte wijn"
    assert res[1]["productId"] == "1584236"


def test_extractor_append_or_update_recipe_section():
    base = "# Title\n\n## Ingredients\n- boter: 10g\n"
    updated = append_or_update_recipe_section(base, "Resolved Products", "- boter [productId=13805]")
    assert "## Resolved Products" in updated
    assert "- boter [productId=13805]" in updated

    # Replace existing
    re_updated = append_or_update_recipe_section(updated, "Resolved Products", "- boter [productId=99999]")
    assert "13805" not in re_updated
    assert "99999" in re_updated


def test_annotate_recipe_content_with_warnings():
    db = Database(":memory:")
    db.store_product(Product(query="boter", product_id="13805", name="Boter"))

    md = """
# Recept
## Ingredients
- boter: 20 g
- onbekend_item: 100 g
"""
    updated_md, resolved, warnings = annotate_recipe_content(md, db, recipe_name="test.md")

    assert len(resolved) == 1
    assert resolved[0][1] == "13805"
    assert len(warnings) == 1
    assert "onbekend_item" in warnings[0]
    assert "## Resolved Products" in updated_md
    assert "- boter (20 g) [productId=13805]" in updated_md


def test_annotate_recipe_file_in_place(tmp_path):
    db = Database(":memory:")
    db.store_product(Product(query="wortel", product_id="11111", name="Wortelen"))

    recipe_path = tmp_path / "wortelsoep.md"
    recipe_path.write_text("# Soep\n\n## Ingredients\n- wortel: 500 g\n", encoding="utf-8")

    res_cnt, warn_cnt = annotate_recipe_file(str(recipe_path), db)
    assert res_cnt == 1
    assert warn_cnt == 0

    new_content = recipe_path.read_text(encoding="utf-8")
    assert "## Resolved Products" in new_content
    assert "[productId=11111]" in new_content


@pytest.mark.asyncio
async def test_search_and_prompt_candidate_selection():
    db = Database(":memory:")
    mock_client = MagicMock()
    mock_candidate = Product(product_id="22222", name="Verse Prei", brand="BONI", content="1 stuk")
    mock_client.search_products = AsyncMock(return_value=[mock_candidate])

    ing = ExtractedIngredient(name="prei")

    with patch("builtins.input", side_effect=["1"]):
        stored = await search_and_prompt_candidate(ing, mock_client, db)
        assert stored is not None
        assert stored.product_id == "22222"
        assert db.find_product("prei").product_id == "22222"
