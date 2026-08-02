from pydantic import BaseModel
from typing import List, Optional

class Product(BaseModel):
    """Unified internal domain model representing a product."""
    normalized_name: Optional[str] = None
    product_id: str
    name: str
    brand: Optional[str] = None
    description: Optional[str] = None
    conservation_info: Optional[str] = None
    usage_info: Optional[str] = None
    content: Optional[str] = None
    gtin: Optional[List[str]] = None
    created_at: Optional[str] = None

