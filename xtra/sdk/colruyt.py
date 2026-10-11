import os
import re
import httpx
import uuid
from datetime import datetime
from typing import List, Optional, Dict
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(override=True)

from xtra.sdk.models import (
    Product,
    ListItem,
    ColruytProduct,
    Price,
    ProductData,
    AddItemsRequest,
)
from xtra.sdk.client import SupermarketClient


class ColruytClient(SupermarketClient):
    BASE_URL = "https://apix.colruyt.be/gateway/emec.colruyt.bffsvc/cg"
    SEARCH_URL = "https://apip.colruyt.be/gateway/emec.colruyt.protected.bffsvc/cg/nl/api/product-search-prs"
    RTI_BASE_URL = "https://rti.colruytgroup.com/nl/product-info"

    def __init__(
        self,
        session_id: Optional[str] = None,
        api_key: Optional[str] = None,
        place_id: Optional[str] = None
    ):
        self.session_id = session_id or os.environ.get("CLPBFF_SESSION")
        if not self.session_id:
            raise ValueError(
                "Colruyt session ID must be provided either via the session_id parameter "
                "or the CLPBFF_SESSION environment variable."
            )

        self.api_key = api_key or os.environ.get("X_CG_APIKEY") or os.environ.get("COLRUYT_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Colruyt API key must be provided either via the api_key parameter "
                "or the X_CG_APIKEY / COLRUYT_API_KEY environment variables."
            )

        self.place_id = place_id or os.environ.get("COLRUYT_PLACE_ID")
        if not self.place_id:
            raise ValueError(
                "Colruyt place ID must be provided either via the place_id parameter "
                "or the COLRUYT_PLACE_ID environment variable."
            )

        self.headers = {
            "x-cg-apikey": self.api_key,
            "Accept": "*/*",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
            "Origin": "https://www.colruyt.be",
            "Referer": "https://www.colruyt.be/"
        }
        self.cookies = {"clpbff_session": self.session_id}
        if os.environ.get("COLRUYT_COOKIE"):
            for c in os.environ.get("COLRUYT_COOKIE", "").split(";"):
                if "=" in c:
                    k, v = c.strip().split("=", 1)
                    self.cookies[k] = v
        if os.environ.get("REESE84"):
            self.cookies["reese84"] = os.environ.get("REESE84")

    async def get_most_bought_products(self, place_id: Optional[str] = None) -> List[Product]:
        url = f"{self.BASE_URL}/most-bought-products"
        params = {
            "lang": "nl",
            "placeId": place_id or self.place_id,
            "prs": "true"
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=self.headers, cookies=self.cookies)
            response.raise_for_status()
            data = response.json()
            return [ColruytProduct(**p).to_product() for p in data]

    async def search_products(self, query: str, place_id: Optional[str] = None) -> List[Product]:
        params = {
            "searchTerm": query,
            "placeId": place_id or self.place_id,
            "size": 25,
            "sort": "relevancy desc",
            "isAvailable": "true",
            "skip": 0
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(self.SEARCH_URL, params=params, headers=self.headers, cookies=self.cookies)
            response.raise_for_status()
            data = response.json()
            return [ColruytProduct(**p).to_product(query=query) for p in data.get("products", [])]

    async def get_product_info(self, product_id: str, gtin: Optional[str] = None) -> Dict[str, Optional[str]]:
        """Scrapes product details from the Colruyt RTI portal."""
        ids_to_try = [product_id]
        if gtin and gtin not in ids_to_try:
            ids_to_try.append(gtin)

        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
        }

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            for identifier in ids_to_try:
                url = f"{self.RTI_BASE_URL}/{identifier}"
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

    async def add_items_to_list(self, products: List[Product]) -> List[ListItem]:
        url = f"{self.BASE_URL}/add-items-to-list"
        now = datetime.utcnow().isoformat() + "Z"

        items = []
        for p in products:
            item = ListItem(
                id=str(uuid.uuid4()),
                description=p.name,
                productData=ProductData(productId=p.product_id),
                createdAt=now,
                updatedAt=now
            )
            items.append(item)

        request_body = AddItemsRequest(items=items)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=request_body.model_dump(),
                headers=self.headers,
                cookies=self.cookies
            )
            response.raise_for_status()
            data = response.json()
            raw_items = data.get("data", {}).get("items") or data.get("items", [])
            return [ListItem(**i) for i in raw_items]

    async def get_shopping_list(
        self,
        place_id: Optional[str] = None,
        limit: int = 255,
        offset: int = 0
    ) -> List[ListItem]:
        """Fetch the current active shopping list."""
        url = f"{self.BASE_URL}/latest-shopping-list"
        params = {
            "limit": limit,
            "offset": offset,
            "sort": "createdAt desc",
            "placeId": place_id or self.place_id,
            "lang": "nl",
            "prs": "true"
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=self.headers, cookies=self.cookies)
            response.raise_for_status()
            data = response.json()
            raw_items = data.get("data", {}).get("items") or data.get("items", [])
            return [ListItem(**i) for i in raw_items]

    async def remove_item_from_list(self, item_id: str) -> bool:
        """Remove a shopping list item by its list item ID (UUID)."""
        url = f"{self.BASE_URL}/remove-item-from-list/{item_id}"
        async with httpx.AsyncClient() as client:
            response = await client.delete(url, headers=self.headers, cookies=self.cookies)
            response.raise_for_status()
            return response.status_code in (200, 204)

    async def add_recipe(self, recipe_path: str) -> List[ListItem]:
        """Parse an annotated recipe markdown file and add its resolved products to the shopping list."""
        if not os.path.isfile(recipe_path):
            raise FileNotFoundError(f"Recipe file not found: {recipe_path}")

        with open(recipe_path, "r", encoding="utf-8") as f:
            content = f.read()

        product_ids = _extract_resolved_product_ids(content)
        if not product_ids:
            raise ValueError(f"No resolved products found with [productId=...] in recipe {recipe_path}")

        products = [Product(name=f"Product {pid}", product_id=pid) for pid in product_ids]
        return await self.add_items_to_list(products)


def _extract_resolved_product_ids(content: str) -> List[str]:
    """Extract all product IDs formatted as [productId=...] in the text."""
    pattern = r"\[productId=([a-zA-Z0-9_-]+)\]"
    return re.findall(pattern, content)


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
