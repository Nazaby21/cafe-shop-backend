from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field
from app.schemas.category_schema import CategoryResponse


class CustomizationOptionBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    extra_price: Decimal = Field(ge=0)

class CustomizationOptionResponse(CustomizationOptionBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class CustomizationGroupBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    is_required: bool = False
    selection_type: str = Field(pattern="^(single|multiple)$")

class CustomizationGroupCreate(CustomizationGroupBase):
    options: list[CustomizationOptionBase]

class CustomizationGroupResponse(CustomizationGroupBase):
    id: int
    options: list[CustomizationOptionResponse]
    model_config = ConfigDict(from_attributes=True)


class CreateProductRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    price: Decimal = Field(gt=0, description="Unit price, must be positive")
    initial_stock: int = Field(default=0, ge=0)
    category_id: int = Field(gt=0)
    customization_groups: list[CustomizationGroupCreate] | None = None


class UpdateProductRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    price: Decimal = Field(gt=0)
    is_active: bool = True
    category_id: int = Field(gt=0)
    customization_groups: list[CustomizationGroupCreate] | None = None


class AdjustStockRequest(BaseModel):
    # Positive to restock, negative to remove/adjust down.
    change_quantity: int = Field(description="Positive to add stock, negative to remove stock")
    reason: str = Field(default="adjustment", pattern="^(restock|adjustment)$")
    reference: str | None = Field(default=None, max_length=255)


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    price: Decimal
    stock_quantity: int
    is_active: bool
    category_id: int
    category: CategoryResponse
    customization_groups: list[CustomizationGroupResponse] = []
