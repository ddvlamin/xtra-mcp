from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Union

class Product(BaseModel):
    """Unified internal domain model representing a product."""
    model_config = ConfigDict(populate_by_name=True)

    query: Optional[str] = None
    product_id: str
    name: str
    brand: Optional[str] = None
    description: Optional[str] = None
    conservation_info: Optional[str] = None
    usage_info: Optional[str] = None
    content: Optional[str] = None
    gtin: Optional[List[str]] = None
    top_category_name: Optional[str] = Field(None, alias="topCategoryName")
    created_at: Optional[str] = None

    @property
    def topCategoryName(self) -> Optional[str]:
        return self.top_category_name

class ExtractedIngredient(BaseModel):
    """Structured ingredient parsed from recipe text."""
    name: str
    quantity: Optional[Union[float, int, str]] = None
    unit: Optional[str] = None

