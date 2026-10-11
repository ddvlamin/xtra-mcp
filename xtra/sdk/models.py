from typing import List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


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
    top_category_name: Optional[str] = None
    created_at: Optional[str] = None


class ExtractedIngredient(BaseModel):
    """Structured ingredient parsed from recipe text."""
    name: str
    quantity: Optional[Union[float, int, str]] = None
    unit: Optional[str] = None


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
    topCategoryName: Optional[str] = None

    def to_product(self, query: Optional[str] = None) -> Product:
        """Converts Colruyt-specific API response object into unified internal Product domain model."""
        return Product(
            query=query,
            product_id=self.technicalArticleNumber,
            name=self.name,
            brand=self.brand,
            content=self.content,
            gtin=self.gtin,
            top_category_name=self.topCategoryName
        )


class ProductData(BaseModel):
    productId: str
    quantity: int = 1
    unitCode: str = "P"


class ListItem(BaseModel):
    id: str
    description: str
    productData: Optional[ProductData] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None
    completedAt: Optional[str] = None


class AddItemsRequest(BaseModel):
    items: List[ListItem]
