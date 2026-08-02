from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional

class Price(BaseModel):
    basicPrice: float
    measurementUnitPrice: Optional[float] = None
    measurementUnit: Optional[str] = None

class Product(BaseModel):
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
    description: Optional[str] = None
    conservation_info: Optional[str] = None
    usage_info: Optional[str] = None

class ProductMapping(BaseModel):
    cleaned_ingredient: str
    product_id: str
    product_name: str
    product_brand: Optional[str] = None
    product_description: Optional[str] = None
    conservation_info: Optional[str] = None
    usage_info: Optional[str] = None
    content: Optional[str] = None
    created_at: Optional[str] = None

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

class SearchResponse(BaseModel):
    products: List[Product]
    totalCount: int

