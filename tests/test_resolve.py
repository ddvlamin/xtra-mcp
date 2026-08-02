import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from xtra.logic import resolve_ingredient, save_product_mapping_logic
from xtra.models import Product, ProductMapping
from xtra.db import Database

@pytest.fixture
def memory_db():
    return Database(db_path=":memory:")

@pytest.mark.asyncio
async def test_resolve_ingredient_from_db(memory_db):
    memory_db.save_mapping(ProductMapping(
        cleaned_ingredient="kipfilets",
        product_id="999",
        product_name="Saved Kipfilet"
    ))

    client = MagicMock()
    most_bought = []

    result = await resolve_ingredient("3 kipfilets", client, most_bought, db=memory_db)
    assert isinstance(result, Product)
    assert result.technicalArticleNumber == "999"
    assert result.name == "Saved Kipfilet"
    client.search_products.assert_not_called()

@pytest.mark.asyncio
async def test_resolve_ingredient_unique(memory_db):
    client = MagicMock()
    client.search_products = AsyncMock(return_value=[
        Product(name="Kipfilet", technicalArticleNumber="123")
    ])
    most_bought = []

    with patch("xtra.logic.scrape_product_info", new=AsyncMock(return_value={
        "product_description": "Scraped ingredients",
        "conservation_info": None,
        "usage_info": None,
        "content": "500g"
    })):
        result = await resolve_ingredient("3 kipfilets", client, most_bought, db=memory_db)
        assert isinstance(result, Product)
        assert result.technicalArticleNumber == "123"
        assert result.description == "Scraped ingredients"
        
        # Verify saved in DB
        saved_db = memory_db.get_mapping("kipfilets")
        assert saved_db is not None
        assert saved_db.product_id == "123"

@pytest.mark.asyncio
async def test_resolve_ingredient_ambiguous_resolved_by_most_bought(memory_db):
    client = MagicMock()
    client.search_products = AsyncMock(return_value=[
        Product(name="Kipfilet A", technicalArticleNumber="123"),
        Product(name="Kipfilet B", technicalArticleNumber="456")
    ])
    most_bought = [
        Product(name="Kipfilet B", technicalArticleNumber="456")
    ]

    with patch("xtra.logic.scrape_product_info", new=AsyncMock(return_value={
        "product_description": "Scraped B",
        "conservation_info": None,
        "usage_info": None,
        "content": None
    })):
        result = await resolve_ingredient("3 kipfilets", client, most_bought, db=memory_db)
        assert isinstance(result, Product)
        assert result.technicalArticleNumber == "456"

@pytest.mark.asyncio
async def test_resolve_ingredient_ambiguous_unresolved(memory_db):
    client = MagicMock()
    client.search_products = AsyncMock(return_value=[
        Product(name="Kipfilet A", technicalArticleNumber="123"),
        Product(name="Kipfilet B", technicalArticleNumber="456")
    ])
    most_bought = []

    result = await resolve_ingredient("3 kipfilets", client, most_bought, db=memory_db)
    assert isinstance(result, list)
    assert len(result) == 2

@pytest.mark.asyncio
async def test_save_product_mapping_logic(memory_db):
    with patch("xtra.logic.scrape_product_info", new=AsyncMock(return_value={
        "product_description": "Scraped Desc",
        "conservation_info": "Gekoeld",
        "usage_info": "Koken",
        "content": "1kg"
    })):
        mapping = await save_product_mapping_logic(
            cleaned_ingredient=" 2 kg Basmati Rijst ",
            product_id="777",
            product_name="Basmati Rice 1kg",
            product_brand="BONI",
            db=memory_db
        )
        assert mapping.cleaned_ingredient == "Basmati Rijst"
        assert mapping.product_id == "777"
        assert mapping.conservation_info == "Gekoeld"
