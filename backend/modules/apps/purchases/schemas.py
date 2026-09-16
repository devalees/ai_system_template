"""Enterprise Purchases & Procurement Validation Schemas."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict


class PurchaseOrderLineCreate(BaseModel):
    product_id: Optional[uuid.UUID] = None
    name: Optional[str] = Field(None, max_length=255)
    quantity: Decimal = Field(default=Decimal("1.0000"), gt=0)
    uom_id: Optional[uuid.UUID] = None
    unit_price: Optional[Decimal] = Field(None, ge=0)
    tax_ids: List[str] = Field(default_factory=list)
    analytic_distribution: Dict[str, float] = Field(default_factory=dict)


class PurchaseOrderLineRead(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    product_id: Optional[uuid.UUID] = None
    name: str
    quantity: Decimal
    uom_id: Optional[uuid.UUID] = None
    unit_price: Decimal
    tax_ids: List[str]
    price_subtotal: Decimal
    price_total: Decimal
    analytic_distribution: Dict[str, float]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderCreate(BaseModel):
    party_id: uuid.UUID
    order_date: date
    currency_id: uuid.UUID
    payment_term_id: Optional[uuid.UUID] = None
    analytic_account_id: Optional[uuid.UUID] = None
    lines: List[PurchaseOrderLineCreate] = Field(..., min_length=1)


class PurchaseOrderRead(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    order_number: str
    party_id: uuid.UUID
    order_date: date
    currency_id: uuid.UUID
    payment_term_id: Optional[uuid.UUID] = None
    state: str
    bill_status: str
    amount_untaxed: Decimal
    amount_tax: Decimal
    amount_total: Decimal
    analytic_account_id: Optional[uuid.UUID] = None
    bill_id: Optional[uuid.UUID] = None
    lines: List[PurchaseOrderLineRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
