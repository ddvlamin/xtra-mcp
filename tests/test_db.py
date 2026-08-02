import pytest
from xtra.db import Database
from xtra.models import ProductMapping

@pytest.fixture
def memory_db():
    return Database(db_path=":memory:")

def test_db_init_and_save(memory_db):
    mapping = ProductMapping(
        cleaned_ingredient="kipfilet",
        product_id="4804565",
        product_name="Kippendijfilet",
        product_brand="BONI",
        product_description="100% kip",
        conservation_info="Chilled",
        usage_info="Cook thoroughly",
        content="500g"
    )
    saved = memory_db.save_mapping(mapping)
    assert saved.cleaned_ingredient == "kipfilet"
    assert saved.product_id == "4804565"

    retrieved = memory_db.get_mapping("kipfilet")
    assert retrieved is not None
    assert retrieved.product_name == "Kippendijfilet"
    assert retrieved.content == "500g"

def test_db_fuzzy_matching_hit(memory_db):
    mapping = ProductMapping(
        cleaned_ingredient="rode currypasta",
        product_id="111222",
        product_name="Rode Curry Pasta 200g"
    )
    memory_db.save_mapping(mapping)

    # Query with slight variation
    match = memory_db.find_fuzzy_mapping("rode curry pasta", score_threshold=80)
    assert match is not None
    assert match.product_id == "111222"

def test_db_fuzzy_matching_miss_below_threshold(memory_db):
    mapping = ProductMapping(
        cleaned_ingredient="rode currypasta",
        product_id="111222",
        product_name="Rode Curry Pasta 200g"
    )
    memory_db.save_mapping(mapping)

    # Unrelated query
    match = memory_db.find_fuzzy_mapping("basmatirijst", score_threshold=80)
    assert match is None
