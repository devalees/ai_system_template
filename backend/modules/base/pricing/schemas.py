"""Pydantic schemas and DTOs for Pricing Engine & Multi-Tier Price Lists."""

import uuid
from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Price List Schemas
# ---------------------------------------------------------------------------

class PriceListBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Price list display title")
    code: str = Field(..., min_length=1, max_length=50, description="Unique reference code")
    description: Optional[str] = Field(None, description="Operational notes or scope")
    currency_id: Optional[uuid.UUID] = Field(None, description="Anchor currency ID")


class PriceListCreate(PriceListBase):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Wholesale USD Tier 1",
                "code": "PL_WHOLESALE_USD",
                "description": "Bulk purchase price list for wholesale distributors.",
            }
        }
    )


class PriceListUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    currency_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None


# ---------------------------------------------------------------------------
# Price List Item Schemas
# ---------------------------------------------------------------------------

class PriceListItemBase(BaseModel):
    applied_on: str = Field("all", pattern="^(all|category|product)$", description="Scope: all, category, or product")
    res_model: Optional[str] = Field(None, max_length=100, description="Target entity model (e.g. 'products')")
    res_id: Optional[uuid.UUID] = Field(None, description="Target entity ID (product ID or category ID)")
    min_quantity: Decimal = Field(Decimal("1.0"), ge=0, description="Minimum order quantity threshold")
    pricing_mode: str = Field(
        "percentage_discount",
        pattern="^(fixed|percentage_discount|formula)$",
        description="Calculation method: fixed, percentage_discount, or formula",
    )
    fixed_price: Optional[Decimal] = Field(None, ge=0, description="Fixed unit price if mode is 'fixed'")
    discount_percentage: Optional[Decimal] = Field(None, description="Discount % (e.g. 15.0 for 15% off)")
    formula_markup_percentage: Optional[Decimal] = Field(None, description="Markup % applied before surcharge")
    formula_surcharge: Optional[Decimal] = Field(None, description="Fixed surcharge amount added after markup")
    valid_from: Optional[datetime] = Field(None, description="Promotional start datetime")
    valid_to: Optional[datetime] = Field(None, description="Promotional end datetime")
    sequence: int = Field(10, description="Evaluation precedence order (lower executes first)")


class PriceListItemCreate(PriceListItemBase):
    price_list_id: Optional[uuid.UUID] = Field(None, description="Parent price list ID if not in path")

    @model_validator(mode="after")
    def validate_pricing_mode_attributes(self) -> "PriceListItemCreate":
        if self.pricing_mode == "fixed" and self.fixed_price is None:
            raise ValueError("fixed_price must be specified when pricing_mode is 'fixed'")
        if self.pricing_mode == "percentage_discount" and self.discount_percentage is None:
            raise ValueError("discount_percentage must be specified when pricing_mode is 'percentage_discount'")
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("valid_to must be greater than or equal to valid_from")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "applied_on": "all",
                "min_quantity": 100.0,
                "pricing_mode": "percentage_discount",
                "discount_percentage": 15.0,
                "sequence": 10,
            }
        }
    )


class PriceListItemUpdate(BaseModel):
    applied_on: Optional[str] = Field(None, pattern="^(all|category|product)$")
    res_model: Optional[str] = None
    res_id: Optional[uuid.UUID] = None
    min_quantity: Optional[Decimal] = Field(None, ge=0)
    pricing_mode: Optional[str] = Field(None, pattern="^(fixed|percentage_discount|formula)$")
    fixed_price: Optional[Decimal] = Field(None, ge=0)
    discount_percentage: Optional[Decimal] = None
    formula_markup_percentage: Optional[Decimal] = None
    formula_surcharge: Optional[Decimal] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    sequence: Optional[int] = None


class PriceListItemResponse(PriceListItemBase):
    id: uuid.UUID
    company_id: uuid.UUID
    price_list_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PriceListResponse(PriceListBase):
    id: uuid.UUID
    company_id: uuid.UUID
    is_active: bool
    items: List[PriceListItemResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Price Evaluation Schemas
# ---------------------------------------------------------------------------

class PriceEvaluateRequest(BaseModel):
    price_list_id: uuid.UUID = Field(..., description="Target price list ID")
    base_price: Decimal = Field(..., gt=0, description="Standard catalog base price")
    quantity: Decimal = Field(Decimal("1.0"), gt=0, description="Purchase quantity")
    res_model: Optional[str] = Field(None, description="Item model name (e.g. 'products')")
    res_id: Optional[uuid.UUID] = Field(None, description="Item ID")
    category_id: Optional[uuid.UUID] = Field(None, description="Item Category ID")
    evaluation_date: Optional[datetime] = Field(None, description="Date for promotional validity (default: now)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "price_list_id": "00000000-0000-0000-0000-000000000001",
                "base_price": 200.0,
                "quantity": 150.0,
            }
        }
    )


class PriceEvaluateResponse(BaseModel):
    price_list_id: uuid.UUID
    base_price: Decimal
    quantity: Decimal
    unit_price: Decimal
    total_amount: Decimal
    discount_amount: Decimal
    discount_percentage: Optional[Decimal] = None
    applied_rule_id: Optional[uuid.UUID] = None
    applied_mode: str  # fixed | percentage_discount | formula | none

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "price_list_id": "00000000-0000-0000-0000-000000000001",
                "base_price": 200.0,
                "quantity": 150.0,
                "unit_price": 170.0,
                "total_amount": 25500.0,
                "discount_amount": 30.0,
                "discount_percentage": 15.0,
                "applied_mode": "percentage_discount",
            }
        }
    )
