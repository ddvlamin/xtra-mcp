import httpx
import uuid
from datetime import datetime
from typing import List, Optional
from src.models import Product, ListItem, AddItemsRequest, ProductData

class ColruytClient:
    BASE_URL = "https://apix.colruyt.be/gateway/emec.colruyt.bffsvc/cg"
    # Updated search URL from recent documentation
    SEARCH_URL = "https://apip.colruyt.be/gateway/emec.colruyt.protected.bffsvc/cg/nl/api/product-search-prs"
    DEFAULT_API_KEY = "a8ylmv13-b285-4788-9e14-0f79b7ed2411"
    DEFAULT_PLACE_ID = "2643"

    def __init__(self, session_id: str, api_key: Optional[str] = None):
        self.session_id = session_id
        self.api_key = api_key or self.DEFAULT_API_KEY
        self.headers = {
            "x-cg-apikey": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
            "Origin": "https://www.colruyt.be",
            "Referer": "https://www.colruyt.be/"
        }
        self.cookies = {"clpbff_session": self.session_id}

    async def get_most_bought_products(self, place_id: str = DEFAULT_PLACE_ID) -> List[Product]:
        url = f"{self.BASE_URL}/most-bought-products"
        params = {
            "lang": "nl",
            "placeId": place_id,
            "prs": "true"
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=self.headers, cookies=self.cookies)
            response.raise_for_status()
            data = response.json()
            return [Product(**p) for p in data]

    async def search_products(self, query: str, place_id: str = DEFAULT_PLACE_ID) -> List[Product]:
        params = {
            "searchTerm": query,
            "placeId": place_id,
            "size": 25,
            "sort": "relevancy desc",
            "isAvailable": "true",
            "skip": 0
        }
        async with httpx.AsyncClient() as client:
            # Search now also includes cookies
            response = await client.get(self.SEARCH_URL, params=params, headers=self.headers, cookies=self.cookies)
            response.raise_for_status()
            data = response.json()
            return [Product(**p) for p in data.get("products", [])]

    async def add_items_to_list(self, products: List[Product]) -> List[ListItem]:
        url = f"{self.BASE_URL}/add-items-to-list"
        now = datetime.utcnow().isoformat() + "Z"
        
        items = []
        for p in products:
            item = ListItem(
                id=str(uuid.uuid4()),
                description=p.name,
                productData=ProductData(productId=p.technicalArticleNumber),
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
