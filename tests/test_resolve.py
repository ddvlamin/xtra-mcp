import pytest
from unittest.mock import AsyncMock, MagicMock
from src.logic import resolve_ingredient
from src.models import Product

@pytest.mark.asyncio
async def test_resolve_ingredient_unique():
    client = MagicMock()
    client.search_products = AsyncMock(return_value=[
        Product(name="Kipfilet", technicalArticleNumber="123")
    ])
    most_bought = []
    
    result = await resolve_ingredient("3 kipfilets", client, most_bought)
    assert isinstance(result, Product)
    assert result.technicalArticleNumber == "123"

@pytest.mark.asyncio
async def test_resolve_ingredient_ambiguous_resolved_by_most_bought():
    client = MagicMock()
    client.search_products = AsyncMock(return_value=[
        Product(name="Kipfilet A", technicalArticleNumber="123"),
        Product(name="Kipfilet B", technicalArticleNumber="456")
    ])
    most_bought = [
        Product(name="Kipfilet B", technicalArticleNumber="456")
    ]
    
    result = await resolve_ingredient("3 kipfilets", client, most_bought)
    assert isinstance(result, Product)
    assert result.technicalArticleNumber == "456"

@pytest.mark.asyncio
async def test_resolve_ingredient_ambiguous_unresolved():
    client = MagicMock()
    client.search_products = AsyncMock(return_value=[
        Product(name="Kipfilet A", technicalArticleNumber="123"),
        Product(name="Kipfilet B", technicalArticleNumber="456")
    ])
    most_bought = []
    
    result = await resolve_ingredient("3 kipfilets", client, most_bought)
    assert isinstance(result, list)
    assert len(result) == 2
