import pytest
from unittest.mock import AsyncMock, MagicMock
from xtra.logic import resolve_ingredient
from xtra.models import Product
from xtra.db import Database

@pytest.fixture
def memory_db():
    return Database(db_path=":memory:")

@pytest.mark.asyncio
async def test_resolve_ingredient_from_db(memory_db):
    memory_db.store_product(Product(
        normalized_name="kipfilets",
        product_id="999",
        name="Saved Kipfilet"
    ))

    client = MagicMock()
    most_bought = []

    result = await resolve_ingredient("3 kipfilets", client, most_bought, db=memory_db)
    assert isinstance(result, Product)
    assert result.product_id == "999"
    assert result.name == "Saved Kipfilet"
    client.search_products.assert_not_called()

@pytest.mark.asyncio
async def test_resolve_ingredient_unique(memory_db):
    client = MagicMock()
    client.search_products = AsyncMock(return_value=[
        Product(name="Kipfilet", product_id="123")
    ])
    client.get_product_info = AsyncMock(return_value={
        "product_description": "Scraped ingredients",
        "conservation_info": None,
        "usage_info": None,
        "content": "500g"
    })
    most_bought = []

    result = await resolve_ingredient("3 kipfilets", client, most_bought, db=memory_db)
    assert isinstance(result, Product)
    assert result.product_id == "123"
    assert result.description == "Scraped ingredients"
    
    # Verify saved in DB
    saved_db = memory_db.get_product("kipfilets")
    assert saved_db is not None
    assert saved_db.product_id == "123"

@pytest.mark.asyncio
async def test_resolve_ingredient_ambiguous_resolved_by_most_bought(memory_db):
    client = MagicMock()
    client.search_products = AsyncMock(return_value=[
        Product(name="Kipfilet A", product_id="123"),
        Product(name="Kipfilet B", product_id="456")
    ])
    client.get_product_info = AsyncMock(return_value={
        "product_description": "Scraped B",
        "conservation_info": None,
        "usage_info": None,
        "content": None
    })
    most_bought = [
        Product(name="Kipfilet B", product_id="456")
    ]

    result = await resolve_ingredient("3 kipfilets", client, most_bought, db=memory_db)
    assert isinstance(result, Product)
    assert result.product_id == "456"

@pytest.mark.asyncio
async def test_resolve_ingredient_ambiguous_unresolved(memory_db):
    client = MagicMock()
    client.search_products = AsyncMock(return_value=[
        Product(name="Kipfilet A", product_id="123"),
        Product(name="Kipfilet B", product_id="456")
    ])
    most_bought = []

    result = await resolve_ingredient("3 kipfilets", client, most_bought, db=memory_db)
    assert isinstance(result, list)
    assert len(result) == 2

@pytest.mark.asyncio
async def test_store_product_direct(memory_db):
    stored = memory_db.store_product(
        Product(
            name="Basmati Rice 1kg",
            product_id="777",
            brand="BONI",
            normalized_name="Basmati Rijst",
            conservation_info="Gekoeld"
        )
    )
    assert stored.normalized_name == "Basmati Rijst"
    assert stored.product_id == "777"
    assert stored.conservation_info == "Gekoeld"
