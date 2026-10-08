import pytest
import os
import json
from unittest.mock import AsyncMock, MagicMock, patch
from xtra.models import Product, ExtractedIngredient
from xtra.session import (
    SessionManager,
    SessionIngredient,
    SessionItemStatus,
    start_resolution_session,
    resolve_session_ingredient_choice,
    paginate_session_ingredient,
    session_manager,
)
import xtra.server as server_module

@pytest.fixture(autouse=True)
def clean_session_manager():
    session_manager.sessions.clear()
    yield
    session_manager.sessions.clear()

@pytest.mark.asyncio
async def test_start_resolution_session_mixed():
    mock_client = MagicMock()
    mock_client.session_id = "test_session"

    prod1 = Product(name="Melk", product_id="101", brand="Campina", top_category_name="Zuivel")
    prod2_options = [
        Product(name=f"Kip {i}", product_id=f"20{i}", brand="BONI", top_category_name="Vlees")
        for i in range(1, 8)
    ]

    async def mock_resolve(query, client=None, db=None):
        if query == "melk":
            return "melk", prod1
        elif query == "kip":
            return "kip", prod2_options
        return query, []

    with patch("xtra.session.resolve_ingredient", side_effect=mock_resolve):
        result = await start_resolution_session(
            ingredients=["melk", "kip"],
            client=mock_client,
            limit=5
        )

        assert result["status"] == "in_progress"
        assert result["total_count"] == 2
        assert result["resolved_count"] == 1
        assert result["remaining_count"] == 1
        assert result["active_ingredient"]["name"] == "kip"
        assert len(result["active_ingredient"]["results"]) == 5
        assert result["active_ingredient"]["pagination"]["has_more"] is True
        assert "[2/2] Finding: kip" in result["presentation_markdown"]
        assert "1. Kip 1 [BONI] (201) - Vlees" in result["presentation_markdown"]
        assert "6. Next page (offset 5)" in result["presentation_markdown"]

@pytest.mark.asyncio
async def test_resolve_choice_and_complete_session(tmp_path):
    mock_client = MagicMock()
    mock_client.session_id = "test_session"

    recipe_file = tmp_path / "curry.md"
    recipe_file.write_text("# Curry\n\n## Ingredients\n- 500g chicken\n- 400ml coconut milk\n")

    chicken_options = [
        Product(name="Chicken Breast", product_id="c1", brand="Farm", top_category_name="Meat"),
        Product(name="Chicken Thigh", product_id="c2", brand="Farm", top_category_name="Meat"),
    ]
    coconut_options = [
        Product(name="Coconut Milk 400ml", product_id="cm1", brand="Aroy-D", top_category_name="Pantry"),
    ]

    async def mock_resolve(query, client=None, db=None):
        if "chicken" in query:
            return "chicken", chicken_options
        return "coconut milk", coconut_options

    with patch("xtra.session.extract_ingredients_with_llm", new=AsyncMock(return_value=[
        ExtractedIngredient(name="chicken", quantity=500, unit="g"),
        ExtractedIngredient(name="coconut milk", quantity=400, unit="ml"),
    ])), patch("xtra.session.resolve_ingredient", side_effect=mock_resolve), patch("xtra.session.store_resolved_product", new=AsyncMock(side_effect=lambda **kw: Product(product_id=kw["product_id"], name=kw["name"], brand=kw.get("brand"), top_category_name=kw.get("top_category_name")))):

        # Step 1: Start resolution
        start_res = await start_resolution_session(
            recipe_filename=str(recipe_file),
            client=mock_client
        )
        assert start_res["status"] == "in_progress"
        assert start_res["total_count"] == 2
        assert start_res["resolved_count"] == 0
        assert start_res["active_ingredient"]["name"] == "chicken"
        sid = start_res["session_id"]

        # Step 2: User picks option 1 (c1)
        step2 = await resolve_session_ingredient_choice(
            session_id=sid,
            selected_product_id="c1",
            client=mock_client
        )
        assert step2["status"] == "in_progress"
        assert step2["resolved_count"] == 1
        assert step2["remaining_count"] == 1
        assert step2["next_ingredient"]["name"] == "coconut milk"

        # Step 3: User picks option 1 (cm1) -> Completes session
        step3 = await resolve_session_ingredient_choice(
            session_id=sid,
            selected_product_id="cm1",
            client=mock_client
        )
        assert step3["status"] == "completed"
        assert step3["resolved_count"] == 2
        assert step3["remaining_count"] == 0
        assert "🎉 All ingredients resolved (2/2)" in step3["presentation_markdown"]

        # Verify recipe file was annotated!
        content = recipe_file.read_text()
        assert "## Resolved Products" in content
        assert "- chicken (500 g) [productId=c1]" in content
        assert "- coconut milk (400 ml) [productId=cm1]" in content

@pytest.mark.asyncio
async def test_paginate_session_ingredient():
    mock_client = MagicMock()
    mock_client.session_id = "test_session"

    options = [
        Product(name=f"Apple {i}", product_id=f"a_{i}", brand="Eco", top_category_name="Fruit")
        for i in range(1, 13)
    ]

    with patch("xtra.session.resolve_ingredient", new=AsyncMock(return_value=("apple", options))):
        res = await start_resolution_session(ingredients=["apple"], client=mock_client, limit=5)
        sid = res["session_id"]
        assert len(res["active_ingredient"]["results"]) == 5
        assert res["active_ingredient"]["results"][0]["product_id"] == "a_1"

        # Page 2 (offset 5)
        pg2 = await paginate_session_ingredient(session_id=sid, offset=5, limit=5)
        assert pg2["status"] == "in_progress"
        assert len(pg2["ingredient"]["results"]) == 5
        assert pg2["ingredient"]["results"][0]["product_id"] == "a_6"
        assert pg2["ingredient"]["pagination"]["has_more"] is True
        assert pg2["ingredient"]["pagination"]["next_offset"] == 10

        # Page 3 (offset 10)
        pg3 = await paginate_session_ingredient(session_id=sid, offset=10, limit=5)
        assert len(pg3["ingredient"]["results"]) == 2
        assert pg3["ingredient"]["results"][0]["product_id"] == "a_11"
        assert pg3["ingredient"]["pagination"]["has_more"] is False
        assert pg3["ingredient"]["pagination"]["next_offset"] is None

@pytest.mark.asyncio
async def test_server_call_session_tools():
    mock_client = MagicMock()
    mock_client.session_id = "test_session"
    server_module.client = mock_client

    with patch("xtra.server.start_resolution_session", new=AsyncMock(return_value={"status": "in_progress", "session_id": "s123", "presentation_markdown": "test progress"})):
        result = await server_module.handle_call_tool("start_recipe_resolution", {"ingredients": ["apple", "banana"]})
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["session_id"] == "s123"

    with patch("xtra.server.resolve_session_ingredient_choice", new=AsyncMock(return_value={"status": "in_progress", "session_id": "s123", "resolved_count": 1})):
        result2 = await server_module.handle_call_tool("resolve_ingredient_choice", {"session_id": "s123", "selected_product_id": "p1"})
        data2 = json.loads(result2[0].text)
        assert data2["resolved_count"] == 1

    with patch("xtra.server.paginate_session_ingredient", new=AsyncMock(return_value={"status": "in_progress", "session_id": "s123", "ingredient": {}})):
        result3 = await server_module.handle_call_tool("paginate_active_ingredient", {"session_id": "s123", "offset": 5})
        data3 = json.loads(result3[0].text)
        assert data3["status"] == "in_progress"
