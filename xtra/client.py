from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from xtra.models import Product

class SupermarketClient(ABC):
    """Abstract interface for supermarket API clients (e.g. Colruyt, Delhaize, Albert Heijn)."""

    @abstractmethod
    async def get_most_bought_products(self) -> List[Product]:
        """Fetch frequently purchased products."""
        pass

    @abstractmethod
    async def search_products(self, query: str) -> List[Product]:
        """Search for products matching the given query string."""
        pass

    @abstractmethod
    async def get_product_info(self, product_id: str, gtin: Optional[str] = None) -> Dict[str, Optional[str]]:
        """Fetch or scrape detailed product metadata (description, conservation, usage, content)."""
        pass

    @abstractmethod
    async def add_items_to_list(self, products: List[Product]) -> List[Any]:
        """Add products to the user's shopping list."""
        pass
