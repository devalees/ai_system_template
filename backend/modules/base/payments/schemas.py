"""Pydantic schemas and DTOs for Payment Terms, Methods & Transactions."""

import uuid
from decimal import Decimal
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Payment Method Schemas
# ---------------------------------------------------------------------------

class PaymentMethodBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Display name")
    code: str = Field(..., min_length=1, max_length=50, description="Unique reference code")
    method_type: str = Field("manual", pattern="^(manual|electronic|bank|cash)$", description="Type of instrument")
    description: Optional[str] = Field(None, description="Operational notes")


class PaymentMethodCreate(PaymentMethodBase):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Wire Bank Transfer",
                "code": "BANK_WIRE",
                "method_type": "bank",
                "description": "Direct bank wire deposit",
            }
        }
    )


class PaymentMethodUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    method_type: Optional[str] = Field(None, pattern="^(manual|electronic|bank|cash)$")
    is_active: Optional[bool] = None
    description: Optional[str] = None


class PaymentMethodResponse(PaymentMethodBase):
    id: uuid.UUID
    company_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Payment Terms Line Schemas
# ---------------------------------------------------------------------------

class PaymentTermsLineBase(BaseModel):
    sequence: int = Field(10, description="Order of installment allocation")
    value_type: str = Field("balance", pattern="^(percent|fixed|balance)$", description="percent, fixed, or balance")
    value: Decimal = Field(Decimal("0.0000"), ge=0, description="Percentage (e.g. 30.0) or fixed amount")
    days: int = Field(0, ge=0, description="Days offset")
    option: str = Field(
        "days_after_invoice",
        pattern="^(days_after_invoice|end_of_month|days_after_end_of_month)$",
        description="Calculation mode for due date",
    )


class PaymentTermsLineCreate(PaymentTermsLineBase):
    pass


class PaymentTermsLineResponse(PaymentTermsLineBase):
    id: uuid.UUID
    terms_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Payment Terms Schemas
# ---------------------------------------------------------------------------

class PaymentTermsBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Terms name")
    code: str = Field(..., min_length=1, max_length=50, description="Unique reference code")
    description: Optional[str] = Field(None, description="Commercial summary")


class PaymentTermsCreate(PaymentTermsBase):
    lines: List[PaymentTermsLineCreate] = Field(default_factory=list, description="Installment breakdown rules")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "30% Advance, Balance in 30 Days",
                "code": "30_ADV_30_NET",
                "description": "30% immediate advance, remaining balance within 30 days.",
                "lines": [
                    {"sequence": 10, "value_type": "percent", "value": "30.0000", "days": 0, "option": "days_after_invoice"},
                    {"sequence": 20, "value_type": "balance", "value": "0.0000", "days": 30, "option": "days_after_invoice"},
                ],
            }
        }
    )


class PaymentTermsUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class PaymentTermsResponse(PaymentTermsBase):
    id: uuid.UUID
    company_id: uuid.UUID
    is_active: bool
    lines: List[PaymentTermsLineResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Payment Transaction Schemas
# ---------------------------------------------------------------------------

class PaymentTransactionBase(BaseModel):
    payment_number: str = Field(..., min_length=1, max_length=50, description="Unique transaction number")
    res_model: Optional[str] = Field(None, max_length=100, description="Target entity model (e.g. invoices)")
    res_id: Optional[uuid.UUID] = Field(None, description="Target entity UUID")
    party_id: Optional[uuid.UUID] = Field(None, description="Customer or vendor party UUID")
    payment_method_id: uuid.UUID = Field(..., description="Payment method instrument UUID")
    transaction_type: str = Field("inbound", pattern="^(inbound|outbound)$", description="inbound or outbound")
    amount: Decimal = Field(..., gt=0, description="Transaction monetary amount")
    currency_id: Optional[uuid.UUID] = Field(None, description="Currency UUID")
    payment_date: Optional[datetime] = Field(None, description="Transaction datetime")
    reference: Optional[str] = Field(None, description="External transaction or gateway reference")
    notes: Optional[str] = Field(None, description="Internal remarks")


class PaymentTransactionCreate(PaymentTransactionBase):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "payment_number": "PAY-2026-0001",
                "res_model": "invoices",
                "payment_method_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
                "transaction_type": "inbound",
                "amount": "1500.00",
                "reference": "WIRE-TXN-98421",
                "notes": "Payment for invoice INV-2026-0089",
            }
        }
    )


class PaymentTransactionUpdate(BaseModel):
    reference: Optional[str] = None
    notes: Optional[str] = None


class PaymentTransactionResponse(PaymentTransactionBase):
    id: uuid.UUID
    company_id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime
    payment_method_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Due Date Schedule Calculation Schemas
# ---------------------------------------------------------------------------

class ComputePaymentScheduleRequest(BaseModel):
    total_amount: Decimal = Field(..., gt=0, description="Document gross amount to allocate")
    terms_id: uuid.UUID = Field(..., description="Payment terms UUID")
    invoice_date: Optional[date] = Field(None, description="Base invoice date (defaults to today)")
    currency_rounding: Decimal = Field(Decimal("0.01"), gt=0, description="Rounding increment")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_amount": "1000.00",
                "terms_id": "b2c3d4e5-f6a7-8b9c-0d1e-2f3a4b5c6d7e",
                "invoice_date": "2026-09-16",
                "currency_rounding": "0.01",
            }
        }
    )


class PaymentInstallment(BaseModel):
    installment_number: int
    due_date: date
    amount: Decimal
    percentage: Decimal


class ComputePaymentScheduleResponse(BaseModel):
    terms_id: uuid.UUID
    terms_name: str
    total_amount: Decimal
    installments: List[PaymentInstallment]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "terms_id": "b2c3d4e5-f6a7-8b9c-0d1e-2f3a4b5c6d7e",
                "terms_name": "30% Advance, Balance 30 Days",
                "total_amount": "1000.00",
                "installments": [
                    {"installment_number": 1, "due_date": "2026-09-16", "amount": "300.00", "percentage": "30.00"},
                    {"installment_number": 2, "due_date": "2026-10-16", "amount": "700.00", "percentage": "70.00"},
                ],
            }
        }
    )
