from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from xtra.sdk.models import Product, ListItem


class SupermarketClient(ABC):
    """Abstract base class representing generic supermarket actions."""

    @abstractmethod
    async def get_most_bought_products(self, place_id: Optional[str] = None) -> List[Product]:
        """Fetch the user's most frequently bought products."""
        pass

    @abstractmethod
    async def search_products(self, query: str, place_id: Optional[str] = None) -> List[Product]:
        """Search products using an arbitrary query term."""
        pass

    @abstractmethod
    async def get_product_info(self, product_id: str, gtin: Optional[str] = None) -> Dict[str, Optional[str]]:
        """Fetch extended details for a product (ingredients, storage, usage, content)."""
        pass

    @abstractmethod
    async def add_items_to_list(self, products: List[Product]) -> List[ListItem]:
        """Add products to the user's shopping list."""
        pass

    @abstractmethod
    async def get_shopping_list(self, place_id: Optional[str] = None, limit: int = 255, offset: int = 0) -> List[ListItem]:
        """Retrieve all active items on the shopping list."""
        pass

    @abstractmethod
    async def remove_item_from_list(self, item_id: str) -> bool:
        """Remove a single item from the shopping list by its list item ID."""
        pass

    @abstractmethod
    async def add_recipe(self, recipe_path: str) -> List[ListItem]:
        """Parse an annotated recipe markdown file and add its resolved products to the shopping list."""
        pass
