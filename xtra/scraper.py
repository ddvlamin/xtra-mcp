import httpx
from bs4 import BeautifulSoup
from typing import Dict, Optional

RTI_BASE_URL = "https://rti.colruytgroup.com/nl/product-info"

async def scrape_product_info(product_id: str, gtin: Optional[str] = None) -> Dict[str, Optional[str]]:
    """Scrapes product details from the Colruyt RTI portal."""
    ids_to_try = [product_id]
    if gtin and gtin not in ids_to_try:
        ids_to_try.append(gtin)

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
    }

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        for identifier in ids_to_try:
            url = f"{RTI_BASE_URL}/{identifier}"
            try:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    info = _parse_rti_html(response.text)
                    if any(info.values()):
                        return info
            except Exception:
                continue

    return {
        "product_description": None,
        "conservation_info": None,
        "usage_info": None,
        "content": None
    }

def _parse_rti_html(html: str) -> Dict[str, Optional[str]]:
    soup = BeautifulSoup(html, "html.parser")
    res = {
        "product_description": None,
        "conservation_info": None,
        "usage_info": None,
        "content": None
    }

    for section in soup.find_all("div", class_="flex flex-col gap-4"):
        h2 = section.find("h2")
        if not h2:
            continue
        title = h2.get_text(strip=True).lower()

        if "inhoud" in title and not res["content"]:
            paragraphs = [p.get_text(strip=True) for p in section.find_all("p") if p.get_text(strip=True)]
            if paragraphs:
                res["content"] = " ".join(paragraphs)

        elif "bewaar" in title or "gebruik" in title:
            sub_sections = section.find_all("div", class_="flex flex-col gap-2")
            if sub_sections:
                for sub in sub_sections:
                    h3 = sub.find("h3")
                    sub_title = h3.get_text(strip=True).lower() if h3 else ""
                    paragraphs = [p.get_text(strip=True) for p in sub.find_all("p") if p.get_text(strip=True)]
                    text = " ".join(paragraphs)
                    if "bereiding" in sub_title or "gebruik" in sub_title:
                        res["usage_info"] = text
                    elif "bewaar" in sub_title:
                        res["conservation_info"] = text
                    else:
                        if not res["conservation_info"]:
                            res["conservation_info"] = text
            else:
                paragraphs = [p.get_text(strip=True) for p in section.find_all("p") if p.get_text(strip=True)]
                if paragraphs:
                    res["conservation_info"] = " ".join(paragraphs)

        elif "ingrediënten" in title and not res["product_description"]:
            paragraphs = [p.get_text(strip=True) for p in section.find_all("p") if p.get_text(strip=True)]
            if paragraphs:
                res["product_description"] = " ".join(paragraphs)

    return res
