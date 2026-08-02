import pytest
from xtra.db import Database
from xtra.models import Product

@pytest.fixture
def memory_db():
    return Database(db_path=":memory:")

def test_db_init_and_store(memory_db):
    product = Product(
        normalized_name="kipfilet",
        product_id="4804565",
        name="Kippendijfilet",
        brand="BONI",
        description="100% kip",
        conservation_info="Chilled",
        usage_info="Cook thoroughly",
        content="500g"
    )
    saved = memory_db.store_product(product)
    assert saved.normalized_name == "kipfilet"
    assert saved.product_id == "4804565"

    retrieved = memory_db.get_product("kipfilet")
    assert retrieved is not None
    assert retrieved.name == "Kippendijfilet"
    assert retrieved.content == "500g"

def test_db_store_product_validation(memory_db):
    # Test missing product_id
    p1 = Product(name="No ID", product_id="", normalized_name="test")
    with pytest.raises(ValueError) as exc1:
        memory_db.store_product(p1)
    assert "product_id" in str(exc1.value)

    # Test missing name
    p2 = Product(name="", product_id="123", normalized_name="test")
    with pytest.raises(ValueError) as exc2:
        memory_db.store_product(p2)
    assert "name" in str(exc2.value)

    # Test missing normalized_name
    p3 = Product(name="Valid Name", product_id="123", normalized_name="")
    with pytest.raises(ValueError) as exc3:
        memory_db.store_product(p3)
    assert "normalized_name" in str(exc3.value)

def test_db_fuzzy_matching_hit(memory_db):
    product = Product(
        normalized_name="rode currypasta",
        product_id="111222",
        name="Rode Curry Pasta 200g"
    )
    memory_db.store_product(product)

    match = memory_db.find_product("rode curry pasta", score_threshold=80)
    assert match is not None
    assert match.product_id == "111222"

def test_db_fuzzy_matching_miss_below_threshold(memory_db):
    product = Product(
        normalized_name="rode currypasta",
        product_id="111222",
        name="Rode Curry Pasta 200g"
    )
    memory_db.store_product(product)

    match = memory_db.find_product("basmatirijst", score_threshold=80)
    assert match is None
