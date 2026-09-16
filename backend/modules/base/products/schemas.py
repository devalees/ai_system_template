"""Pydantic schemas for Universal Product & Item Master Data."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class ProductBase(BaseModel):
    """Base schema attributes for Product definition."""

    code: str = Field(
        ...,
        max_length=64,
        description="Internal SKU, item reference, or barcode (e.g. PROD-00001)",
    )
    name: str = Field(
        ...,
        max_length=255,
        description="Display name of the product or service",
    )
    description: Optional[str] = Field(
        None,
        description="Detailed specification or notes",
    )
    product_type: str = Field(
        "storable",
        pattern="^(storable|consumable|service)$",
        description="Product classification: 'storable', 'consumable', 'service'",
    )
    uom_id: uuid.UUID = Field(
        ...,
        description="Default sales/inventory unit of measure UUID",
    )
    purchase_uom_id: Optional[uuid.UUID] = Field(
        None,
        description="Default procurement unit of measure UUID",
    )
    sale_price: Decimal = Field(
        Decimal("0.0000"),
        ge=0,
        description="Standard sales price",
    )
    cost_price: Decimal = Field(
        Decimal("0.0000"),
        ge=0,
        description="Standard cost / purchase price",
    )
    sale_tax_ids: List[str] = Field(
        default_factory=list,
        description="Default sales tax UUID strings",
    )
    purchase_tax_ids: List[str] = Field(
        default_factory=list,
        description="Default purchase tax UUID strings",
    )
    income_account_id: Optional[uuid.UUID] = Field(
        None,
        description="Default revenue GL account UUID",
    )
    expense_account_id: Optional[uuid.UUID] = Field(
        None,
        description="Default expense/COGS GL account UUID",
    )
    category_id: Optional[uuid.UUID] = Field(
        None,
        description="Hierarchical category UUID",
    )
    is_saleable: bool = Field(
        True,
        description="Whether this product can be added to customer quotations/sales orders",
    )
    is_purchasable: bool = Field(
        True,
        description="Whether this product can be added to vendor RFQs/purchase orders",
    )
    is_active: bool = Field(
        True,
        description="Operational visibility toggle",
    )
    custom_fields: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extensible custom attributes JSONB",
    )


class ProductCreate(ProductBase):
    """Payload schema for creating a new product."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "PROD-1001",
                "name": "Industrial Widget Pro",
                "description": "High-durability mechanical component",
                "product_type": "storable",
                "uom_id": "00000000-0000-0000-0000-000000000001",
                "sale_price": 120.00,
                "cost_price": 75.00,
                "sale_tax_ids": [],
                "purchase_tax_ids": [],
                "is_saleable": True,
                "is_purchasable": True,
                "is_active": True,
            }
        }
    )


class ProductUpdate(BaseModel):
    """Payload schema for updating an existing product (PATCH)."""

    code: Optional[str] = Field(None, max_length=64)
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    product_type: Optional[str] = Field(None, pattern="^(storable|consumable|service)$")
    uom_id: Optional[uuid.UUID] = None
    purchase_uom_id: Optional[uuid.UUID] = None
    sale_price: Optional[Decimal] = Field(None, ge=0)
    cost_price: Optional[Decimal] = Field(None, ge=0)
    sale_tax_ids: Optional[List[str]] = None
    purchase_tax_ids: Optional[List[str]] = None
    income_account_id: Optional[uuid.UUID] = None
    expense_account_id: Optional[uuid.UUID] = None
    category_id: Optional[uuid.UUID] = None
    is_saleable: Optional[bool] = None
    is_purchasable: Optional[bool] = None
    is_active: Optional[bool] = None
    custom_fields: Optional[Dict[str, Any]] = None


class ProductRead(ProductBase):
    """Read schema representing a persisted product record."""

    id: uuid.UUID
    company_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    version_id: int

    model_config = ConfigDict(from_attributes=True)


class ProductDetailRead(ProductRead):
    """Enriched product detail with resolved category and UoM metadata."""

    category_name: Optional[str] = None
    uom_name: Optional[str] = None
    uom_symbol: Optional[str] = None
    purchase_uom_name: Optional[str] = None
    purchase_uom_symbol: Optional[str] = None
