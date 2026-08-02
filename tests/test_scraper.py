import pytest
from unittest.mock import AsyncMock, patch
from xtra.colruyt import ColruytClient, _parse_rti_html

def test_parse_rti_html():
    sample_html = """
    <div class="flex flex-col gap-4">
        <h2>Inhoud</h2>
        <p>Netto inhoud: 500g</p>
    </div>
    <div class="flex flex-col gap-4">
        <h2>Bewaar- en gebruiksvoorschriften</h2>
        <div class="flex flex-col gap-2">
            <h3>Bereidings- en gebruiksinformatie</h3>
            <p>Bakken in de pan.</p>
        </div>
        <div class="flex flex-col gap-2">
            <h3>Bewaaradvies</h3>
            <p>Gekoeld bewaren op max 4C.</p>
        </div>
    </div>
    <div class="flex flex-col gap-4">
        <h2>Ingrediënten</h2>
        <p>100% kipfilet</p>
    </div>
    """
    parsed = _parse_rti_html(sample_html)
    assert parsed["content"] == "Netto inhoud: 500g"
    assert parsed["usage_info"] == "Bakken in de pan."
    assert parsed["conservation_info"] == "Gekoeld bewaren op max 4C."
    assert parsed["product_description"] == "100% kipfilet"

@pytest.mark.asyncio
async def test_get_product_info_success():
    sample_html = """
    <div class="flex flex-col gap-4">
        <h2>Inhoud</h2>
        <p>Netto inhoud: 200g</p>
    </div>
    """
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.text = sample_html

    client = ColruytClient(session_id="dummy", api_key="dummy", place_id="dummy")

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        info = await client.get_product_info("12345")
        assert info["content"] == "Netto inhoud: 200g"
