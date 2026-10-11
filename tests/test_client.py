import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from xtra.sdk.colruyt import ColruytClient, ColruytProduct

def test_client_init_missing_session_id():
    with patch.dict(os.environ, {"X_CG_APIKEY": "dummy_key", "COLRUYT_PLACE_ID": "1234"}, clear=True):
        with pytest.raises(ValueError) as excinfo:
            ColruytClient()
        assert "Colruyt session ID must be provided" in str(excinfo.value)

def test_client_init_missing_api_key():
    with patch.dict(os.environ, {"CLPBFF_SESSION": "dummy_session"}, clear=True):
        with pytest.raises(ValueError) as excinfo:
            ColruytClient()
        assert "Colruyt API key must be provided" in str(excinfo.value)

def test_client_init_missing_place_id():
    with patch.dict(os.environ, {"CLPBFF_SESSION": "dummy_session", "X_CG_APIKEY": "dummy_key"}, clear=True):
        with pytest.raises(ValueError) as excinfo:
            ColruytClient()
        assert "Colruyt place ID must be provided" in str(excinfo.value)

def test_client_init_success_with_args():
    with patch.dict(os.environ, {}, clear=True):
        client = ColruytClient(
            session_id="dummy_session",
            api_key="my_custom_key",
            place_id="1234"
        )
        assert client.session_id == "dummy_session"
        assert client.api_key == "my_custom_key"
        assert client.place_id == "1234"

def test_client_init_success_with_env():
    with patch.dict(os.environ, {
        "X_CG_APIKEY": "env_key",
        "COLRUYT_PLACE_ID": "5678"
    }, clear=True):
        client = ColruytClient(session_id="dummy_session")
        assert client.session_id == "dummy_session"
        assert client.api_key == "env_key"
        assert client.place_id == "5678"

def test_client_init_success_with_alternate_env_key():
    with patch.dict(os.environ, {
        "COLRUYT_API_KEY": "alt_env_key",
        "COLRUYT_PLACE_ID": "5678",
        "COLRUYT_COOKIE": "foo=bar; baz=qux",
        "REESE84": "token123"
    }, clear=True):
        client = ColruytClient(session_id="dummy_session")
        assert client.api_key == "alt_env_key"
        assert client.cookies["clpbff_session"] == "dummy_session"
        assert client.cookies["foo"] == "bar"
        assert client.cookies["baz"] == "qux"
        assert client.cookies["reese84"] == "token123"

def test_colruyt_product_to_product_transformation():
    cp = ColruytProduct(
        name="Kipfilet",
        technicalArticleNumber="4804565",
        brand="BONI",
        content="500g",
        topCategoryName="Bereidingen/Charcuterie/Vis/Veggie"
    )
    assert cp.topCategoryName == "Bereidingen/Charcuterie/Vis/Veggie"

    product = cp.to_product(query="kipfilet")
    assert product.product_id == "4804565"
    assert product.name == "Kipfilet"
    assert product.brand == "BONI"
    assert product.query == "kipfilet"
    assert product.top_category_name == "Bereidingen/Charcuterie/Vis/Veggie"

def test_colruyt_product_from_json_dict_with_top_category_name():
    payload = {
        "name": "volkorenbrood lang dagvers",
        "technicalArticleNumber": "3029844",
        "topCategoryName": "Brood/Ontbijt"
    }
    cp = ColruytProduct(**payload)
    assert cp.topCategoryName == "Brood/Ontbijt"
    assert cp.to_product().top_category_name == "Brood/Ontbijt"


@pytest.mark.asyncio
async def test_get_shopping_list():
    client = ColruytClient(session_id="dummy", api_key="dummy", place_id="1234")
    sample_response = {
        "data": {
            "items": [
                {
                    "id": "uuid-1",
                    "description": "Boni Melk 1L",
                    "productData": {"productId": "111", "quantity": 1, "unitCode": "P"},
                    "completedAt": None,
                }
            ]
        }
    }
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=sample_response)

    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_resp)) as mock_get:
        items = await client.get_shopping_list()
        assert len(items) == 1
        assert items[0].id == "uuid-1"
        assert items[0].description == "Boni Melk 1L"
        assert items[0].productData.productId == "111"
        assert mock_get.called


@pytest.mark.asyncio
async def test_get_shopping_list_get_list_items_format():
    client = ColruytClient(session_id="dummy", api_key="dummy", place_id="1234")
    sample_response = {
        "getListItems": {
            "data": [
                {
                    "id": "uuid-2",
                    "description": "BONI Hummus Pikant Basic",
                    "productData": {"productId": "4855056", "quantity": 1, "unitCode": "P"},
                    "completedAt": None,
                    "createdAt": 1791714327.0,
                    "updatedAt": "2026-10-11T10:25:27Z",
                }
            ]
        }
    }
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=sample_response)

    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_resp)):
        items = await client.get_shopping_list()
        assert len(items) == 1
        assert items[0].id == "uuid-2"
        assert items[0].description == "BONI Hummus Pikant Basic"
        assert items[0].productData.productId == "4855056"
        assert items[0].createdAt == 1791714327.0


@pytest.mark.asyncio
async def test_remove_item_from_list():
    client = ColruytClient(session_id="dummy", api_key="dummy", place_id="1234")
    mock_resp = MagicMock()
    mock_resp.status_code = 204
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.delete", AsyncMock(return_value=mock_resp)) as mock_delete:
        res = await client.remove_item_from_list("uuid-123")
        assert res is True
        assert mock_delete.called


@pytest.mark.asyncio
async def test_add_recipe(tmp_path):
    client = ColruytClient(session_id="dummy", api_key="dummy", place_id="1234")
    recipe_file = tmp_path / "test_recipe.md"
    recipe_file.write_text(
        "# Recipe\n\n## Ingredients\n- boter: 10g\n\n## Resolved Products\n- boter (10g) [productId=13805]\n- melk (1L) [productId=99999]\n",
        encoding="utf-8"
    )

    with patch.object(client, "add_items_to_list", AsyncMock(return_value=[])) as mock_add:
        await client.add_recipe(str(recipe_file))
        assert mock_add.called
        products_arg = mock_add.call_args[0][0]
        assert len(products_arg) == 2
        assert {p.product_id for p in products_arg} == {"13805", "99999"}

