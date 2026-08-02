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
