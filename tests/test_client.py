import os
import pytest
from unittest.mock import patch
from xtra.colruyt import ColruytClient, ColruytProduct

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
