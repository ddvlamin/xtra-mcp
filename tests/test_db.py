import pytest
from xtra.db import Database
from xtra.models import Product

@pytest.fixture
def memory_db():
    return Database(db_path=":memory:")

def test_db_init_and_store(memory_db):
    product = Product(
        query="kipfilet",
        product_id="4804565",
        name="Kippendijfilet",
        brand="BONI",
        description="100% kip",
        conservation_info="Chilled",
        usage_info="Cook thoroughly",
        content="500g",
        top_category_name="Bereidingen/Charcuterie/Vis/Veggie"
    )
    saved = memory_db.store_product(product)
    assert saved.query == "kipfilet"
    assert saved.product_id == "4804565"
    assert saved.top_category_name == "Bereidingen/Charcuterie/Vis/Veggie"

    retrieved = memory_db.get_product("kipfilet")
    assert retrieved is not None
    assert retrieved.name == "Kippendijfilet"
    assert retrieved.content == "500g"
    assert retrieved.top_category_name == "Bereidingen/Charcuterie/Vis/Veggie"

def test_db_multiple_queries_same_product_id(memory_db):
    # Multiple distinct queries can point to the same product_id
    p1 = Product(query="kipfilet", product_id="4804565", name="Kippendijfilet")
    p2 = Product(query="kipfilets", product_id="4804565", name="Kippendijfilet")
    p3 = Product(query="kip borst", product_id="4804565", name="Kippendijfilet")
    
    memory_db.store_product(p1)
    memory_db.store_product(p2)
    memory_db.store_product(p3)

    assert memory_db.get_product("kipfilet").product_id == "4804565"
    assert memory_db.get_product("kipfilets").product_id == "4804565"
    assert memory_db.get_product("kip borst").product_id == "4804565"

    all_products = memory_db.get_all_products()
    assert len(all_products) == 3

    # Updating an existing query updates its specific record
    p1_updated = Product(query="kipfilet", product_id="9999999", name="Nieuwe Kip")
    memory_db.store_product(p1_updated)
    assert memory_db.get_product("kipfilet").product_id == "9999999"
    assert memory_db.get_product("kipfilets").product_id == "4804565"

def test_db_store_product_validation(memory_db):
    # Test missing product_id
    p1 = Product(name="No ID", product_id="", query="test")
    with pytest.raises(ValueError) as exc1:
        memory_db.store_product(p1)
    assert "product_id" in str(exc1.value)

    # Test missing name
    p2 = Product(name="", product_id="123", query="test")
    with pytest.raises(ValueError) as exc2:
        memory_db.store_product(p2)
    assert "name" in str(exc2.value)

    # Test missing query
    p3 = Product(name="Valid Name", product_id="123", query="")
    with pytest.raises(ValueError) as exc3:
        memory_db.store_product(p3)
    assert "query" in str(exc3.value)

def test_db_fuzzy_matching_hit(memory_db):
    product = Product(
        query="rode currypasta",
        product_id="111222",
        name="Rode Curry Pasta 200g"
    )
    memory_db.store_product(product)

    match = memory_db.find_product("rode curry pasta", score_threshold=80)
    assert match is not None
    assert match.product_id == "111222"

def test_db_fuzzy_matching_case_insensitive(memory_db):
    product = Product(
        query="prei",
        product_id="29623",
        name="prei"
    )
    memory_db.store_product(product)

    match = memory_db.find_product("Prei", score_threshold=80)
    assert match is not None
    assert match.product_id == "29623"

def test_db_fuzzy_matching_miss_below_threshold(memory_db):
    product = Product(
        query="rode currypasta",
        product_id="111222",
        name="Rode Curry Pasta 200g"
    )
    memory_db.store_product(product)

    match = memory_db.find_product("basmatirijst", score_threshold=80)
    assert match is None

def test_db_delete_product_by_query(memory_db):
    product = Product(
        query="melk",
        product_id="999",
        name="Volle Melk 1L"
    )
    memory_db.store_product(product)
    assert memory_db.get_product("melk") is not None

    deleted = memory_db.delete_product(query="melk")
    assert deleted == 1
    assert memory_db.get_product("melk") is None

    # Deleting non-existent
    deleted_again = memory_db.delete_product(query="melk")
    assert deleted_again == 0

def test_db_delete_product_by_product_id(memory_db):
    product = Product(
        query="eieren",
        product_id="888",
        name="Scharreleieren 10st"
    )
    memory_db.store_product(product)

    deleted = memory_db.delete_product(product_id="888")
    assert deleted == 1
    assert memory_db.get_product("eieren") is None

def test_db_delete_product_validation(memory_db):
    with pytest.raises(ValueError) as exc:
        memory_db.delete_product()
    assert "Either query or product_id" in str(exc.value)

def test_run_migrations_from_legacy_schema():
    import sqlite3
    from xtra.migrations import run_migrations

    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    # Create legacy table with normalized_name and without top_category_name
    cursor.execute("""
        CREATE TABLE products (
            normalized_name TEXT PRIMARY KEY,
            product_id TEXT NOT NULL,
            product_name TEXT NOT NULL
        )
    """)
    conn.commit()

    run_migrations(conn)

    cursor.execute("PRAGMA table_info(products)")
    columns = [col[1] for col in cursor.fetchall()]
    assert "query" in columns
    assert "normalized_name" not in columns
    assert "top_category_name" in columns
