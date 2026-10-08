import pytest
from xtra.models import Product, ExtractedIngredient
from xtra.formatting import (
    format_ingredient_label,
    format_resolved_products_list,
    append_or_update_recipe_section,
    format_ambiguous_options_markdown,
    format_session_progress_presentation,
)
from xtra.session import RecipeSession, SessionIngredient, SessionItemStatus

def test_format_ingredient_label():
    assert format_ingredient_label(ExtractedIngredient(name="bloem", quantity=200, unit="g")) == "bloem (200 g)"
    assert format_ingredient_label(ExtractedIngredient(name="kipfilets", quantity=3, unit=None)) == "kipfilets (3)"
    assert format_ingredient_label(ExtractedIngredient(name="zout", quantity=None, unit=None)) == "zout"
    assert format_ingredient_label({"name": "melk", "quantity": 100, "unit": "ml"}) == "melk (100 ml)"
    assert format_ingredient_label("peper") == "peper"

def test_format_resolved_products_list():
    items = [
        (ExtractedIngredient(name="bloem", quantity=200, unit="g"), Product(name="Tarwebloem", product_id="12345")),
        (ExtractedIngredient(name="melk", quantity=100, unit="ml"), Product(name="Volle melk", product_id="67890")),
    ]
    md_list = format_resolved_products_list(items)
    assert md_list == "- bloem (200 g) [productId=12345]\n- melk (100 ml) [productId=67890]"

def test_append_or_update_recipe_section():
    recipe_md = "# Recipe\n\n## Ingredients\n- 200 g bloem\n\n## Instructions\n1. Mix.\n"
    body = "- bloem (200 g) [productId=12345]"
    updated = append_or_update_recipe_section(recipe_md, "Resolved Products", body)
    assert "## Resolved Products\n- bloem (200 g) [productId=12345]\n" in updated

    # Replace existing
    replaced = append_or_update_recipe_section(updated, "Resolved Products", "- bloem (200 g) [productId=99999]")
    assert "12345" not in replaced
    assert "99999" in replaced

def test_format_ambiguous_options_markdown():
    options = [
        Product(name="Kipfilet", product_id="111", brand="BONI", top_category_name="Vlees"),
        Product(name="Kippendij", product_id="222", brand=None, top_category_name=None),
    ]
    md = format_ambiguous_options_markdown("kip", "kip", options, has_more=True, next_offset=2)
    assert "Ambiguous ingredient 'kip' (query: 'kip'). Options:" in md
    assert "1. Kipfilet [BONI] (111) - Vlees" in md
    assert "2. Kippendij (222)" in md
    assert "3. Next page (offset 2) (see more options)" in md


def test_format_session_progress_presentation():
    ing1 = SessionIngredient(name="bloem", query="bloem", status=SessionItemStatus.RESOLVED, resolved_product=Product(name="Bloem", product_id="b1"))
    ing2 = SessionIngredient(name="suiker", query="suiker", status=SessionItemStatus.AWAITING_SELECTION, candidate_products=[Product(name="Witte suiker", product_id="s1", brand="Tiense", top_category_name="Bakken")])
    session = RecipeSession(session_id="s1", ingredients=[ing1, ing2])

    md = format_session_progress_presentation(session, ing2, limit=5)
    assert "[2/2] Finding: suiker" in md
    assert "1. Witte suiker [Tiense] (s1) - Bakken" in md
