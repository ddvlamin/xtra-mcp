import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from xtra.extractor import (
    IngredientExtractor,
    LLMIngredientExtractor,
    BaseIngredientExtractor,
    ExtractionError
)
from xtra.models import ExtractedIngredient

def test_extractor_initialization():
    extractor = LLMIngredientExtractor(host="http://custom-host:11434", model="custom-model")
    assert extractor.host == "http://custom-host:11434"
    assert extractor.model == "custom-model"
    assert not extractor.is_openai_compat
    assert extractor.endpoint == "http://custom-host:11434/api/chat"

def test_extractor_openai_compat_endpoint():
    extractor = LLMIngredientExtractor(host="http://api.openai.com/v1", model="gpt-4o-mini")
    assert extractor.is_openai_compat
    assert extractor.endpoint == "http://api.openai.com/v1/chat/completions"

@pytest.mark.asyncio
async def test_extractor_empty_input():
    extractor = IngredientExtractor()
    result = await extractor.extract("")
    assert result == []
    result_whitespace = await extractor.extract("   \n\t  ")
    assert result_whitespace == []

@pytest.mark.asyncio
async def test_extractor_success_ollama():
    sample_response = {
        "message": {
            "content": '[{"name": "bloem", "quantity": 250, "unit": "g"}, {"name": "ei", "quantity": 2, "unit": null}]'
        }
    }
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=sample_response)

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_resp)

    extractor = LLMIngredientExtractor(http_client=mock_client)
    result = await extractor.extract("- 250g bloem\n- 2 eieren")

    assert len(result) == 2
    assert isinstance(result[0], ExtractedIngredient)
    assert result[0].name == "bloem"
    assert result[0].quantity == 250
    assert result[0].unit == "g"
    assert result[1].name == "ei"
    assert result[1].quantity == 2
    assert result[1].unit is None

@pytest.mark.asyncio
async def test_extractor_success_openai_compat():
    sample_response = {
        "choices": [
            {
                "message": {
                    "content": '[{"name": "kipfilet", "quantity": 300, "unit": "g"}]'
                }
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=sample_response)

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_resp)

    extractor = LLMIngredientExtractor(host="http://localhost:11434/v1", http_client=mock_client)
    result = await extractor.extract("- 300 g kipfilet")

    assert len(result) == 1
    assert result[0].name == "kipfilet"
    assert result[0].quantity == 300
    assert result[0].unit == "g"

@pytest.mark.asyncio
async def test_extractor_malformed_json_raises_extraction_error():
    sample_response = {
        "message": {
            "content": 'Not a json response'
        }
    }
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=sample_response)

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_resp)

    extractor = LLMIngredientExtractor(http_client=mock_client)
    with pytest.raises(ExtractionError, match="did not return a valid JSON array"):
        await extractor.extract("- 1 bloem")

@pytest.mark.asyncio
async def test_extractor_connection_error_raises_extraction_error():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

    extractor = LLMIngredientExtractor(http_client=mock_client)
    with pytest.raises(ExtractionError, match="Failed to query LLM"):
        await extractor.extract("- 1 bloem")
