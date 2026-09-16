"""Enterprise Sales Order Management Validation Schemas."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict


class SaleOrderLineCreate(BaseModel):
    name: str = Field(..., max_length=255)
    quantity: Decimal = Field(default=Decimal("1.0000"), gt=0)
    uom_id: Optional[uuid.UUID] = None
    unit_price: Decimal = Field(..., ge=0)
    discount_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    tax_ids: List[str] = Field(default_factory=list)
    analytic_distribution: Dict[str, float] = Field(default_factory=dict)


class SaleOrderLineRead(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    name: str
    quantity: Decimal
    uom_id: Optional[uuid.UUID] = None
    unit_price: Decimal
    discount_percent: float
    tax_ids: List[str]
    price_subtotal: Decimal
    price_total: Decimal
    analytic_distribution: Dict[str, float]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SaleOrderCreate(BaseModel):
    party_id: uuid.UUID
    order_date: date
    currency_id: uuid.UUID
    payment_term_id: Optional[uuid.UUID] = None
    analytic_account_id: Optional[uuid.UUID] = None
    lines: List[SaleOrderLineCreate] = Field(..., min_length=1)


class SaleOrderRead(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    order_number: str
    party_id: uuid.UUID
    order_date: date
    currency_id: uuid.UUID
    payment_term_id: Optional[uuid.UUID] = None
    state: str
    invoice_status: str
    amount_untaxed: Decimal
    amount_tax: Decimal
    amount_total: Decimal
    analytic_account_id: Optional[uuid.UUID] = None
    invoice_id: Optional[uuid.UUID] = None
    lines: List[SaleOrderLineRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
