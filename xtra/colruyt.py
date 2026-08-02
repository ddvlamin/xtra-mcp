import os
import httpx
import uuid
from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel, Field, ConfigDict
from bs4 import BeautifulSoup
from xtra.models import Product
from xtra.client import SupermarketClient

class Price(BaseModel):
    basicPrice: float
    measurementUnitPrice: Optional[float] = None
    measurementUnit: Optional[str] = None

class ColruytProduct(BaseModel):
    """Colruyt-specific API response payload DTO."""
    model_config = ConfigDict(populate_by_name=True)

    name: str
    technicalArticleNumber: str
    commercialArticleNumber: Optional[str] = None
    brand: Optional[str] = None
    content: Optional[str] = None
    thumbNail: Optional[str] = None
    price: Optional[Price] = None
    longName: Optional[str] = Field(None, alias="LongName")
    gtin: Optional[List[str]] = Field(None, alias="GTIN")

    def to_product(self, normalized_name: Optional[str] = None) -> Product:
        """Converts Colruyt-specific API response object into unified internal Product domain model."""
        return Product(
            normalized_name=normalized_name,
            product_id=self.technicalArticleNumber,
            name=self.name,
            brand=self.brand,
            content=self.content,
            gtin=self.gtin
        )

class ProductData(BaseModel):
    productId: str
    quantity: int = 1
    unitCode: str = "P"

class ListItem(BaseModel):
    id: str
    description: str
    productData: ProductData
    createdAt: str
    updatedAt: str
    completedAt: Optional[str] = None

class AddItemsRequest(BaseModel):
    items: List[ListItem]

class ColruytClient(SupermarketClient):
    BASE_URL = "https://apix.colruyt.be/gateway/emec.colruyt.bffsvc/cg"
    SEARCH_URL = "https://apip.colruyt.be/gateway/emec.colruyt.protected.bffsvc/cg/nl/api/product-search-prs"
    RTI_BASE_URL = "https://rti.colruytgroup.com/nl/product-info"

    def __init__(self, session_id: str, api_key: Optional[str] = None, place_id: Optional[str] = None):
        self.session_id = session_id
        
        # Determine API key from argument or environment variables
        self.api_key = api_key or os.environ.get("X_CG_APIKEY") or os.environ.get("COLRUYT_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Colruyt API key must be provided either via the api_key parameter "
                "or the X_CG_APIKEY / COLRUYT_API_KEY environment variables."
            )

        # Determine place ID from argument or environment variable
        self.place_id = place_id or os.environ.get("COLRUYT_PLACE_ID")
        if not self.place_id:
            raise ValueError(
                "Colruyt place ID must be provided either via the place_id parameter "
                "or the COLRUYT_PLACE_ID environment variable."
            )

        self.headers = {
            "x-cg-apikey": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
            "Origin": "https://www.colruyt.be",
            "Referer": "https://www.colruyt.be/"
        }
        self.cookies = {"clpbff_session": self.session_id}

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
            return [ColruytProduct(**p).to_product() for p in data.get("products", [])]

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
                json=request_body.dict(), 
                headers=self.headers, 
                cookies=self.cookies
            )
            response.raise_for_status()
            data = response.json()
            return [ListItem(**i) for i in data.get("data", {}).get("items", [])]

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
