"""Pydantic schemas and DTOs for Tax Engine & Fiscal Positions."""

import uuid
from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Tax Definition Schemas
# ---------------------------------------------------------------------------

class TaxBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Tax display title")
    code: str = Field(..., min_length=1, max_length=50, description="Unique reference code")
    tax_scope: str = Field("sales", pattern="^(sales|purchase|none)$", description="Scope: sales, purchase, or none")
    calculation_type: str = Field(
        "percent",
        pattern="^(percent|fixed|division)$",
        description="Calculation mode: percent, fixed, or division",
    )
    amount: Decimal = Field(Decimal("0.0000"), description="Tax rate percentage (e.g. 15.0) or fixed amount")
    is_inclusive: bool = Field(False, description="True if unit price includes this tax (B2C/gross)")
    include_base_amount: bool = Field(False, description="True if tax amount compounds into base for subsequent taxes")
    sequence: int = Field(10, description="Evaluation sequence for compounding rules")
    description: Optional[str] = Field(None, description="Regulatory reference or notes")


class TaxCreate(TaxBase):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Value Added Tax (15%)",
                "code": "VAT_15",
                "tax_scope": "sales",
                "calculation_type": "percent",
                "amount": "15.0000",
                "is_inclusive": False,
                "include_base_amount": False,
                "sequence": 10,
                "description": "Standard 15% domestic sales VAT",
            }
        }
    )


class TaxUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    tax_scope: Optional[str] = Field(None, pattern="^(sales|purchase|none)$")
    calculation_type: Optional[str] = Field(None, pattern="^(percent|fixed|division)$")
    amount: Optional[Decimal] = None
    is_inclusive: Optional[bool] = None
    include_base_amount: Optional[bool] = None
    sequence: Optional[int] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None


class TaxResponse(TaxBase):
    id: uuid.UUID
    company_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Fiscal Position Rule Schemas
# ---------------------------------------------------------------------------

class FiscalPositionRuleBase(BaseModel):
    source_tax_id: uuid.UUID = Field(..., description="Default line tax to be mapped")
    dest_tax_id: Optional[uuid.UUID] = Field(
        None, description="Replacement tax (or None to make the line tax-exempt)"
    )


class FiscalPositionRuleCreate(FiscalPositionRuleBase):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source_tax_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
                "dest_tax_id": "b2c3d4e5-f6a7-8b9c-0d1e-2f3a4b5c6d7e",
            }
        }
    )


class FiscalPositionRuleResponse(FiscalPositionRuleBase):
    id: uuid.UUID
    position_id: uuid.UUID
    created_at: datetime
    source_tax_name: Optional[str] = None
    dest_tax_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Fiscal Position Schemas
# ---------------------------------------------------------------------------

class FiscalPositionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Fiscal position title")
    code: str = Field(..., min_length=1, max_length=50, description="Unique reference code")
    description: Optional[str] = Field(None, description="Operational notes")
    auto_apply: bool = Field(False, description="Whether to automatically match customer country")
    country_id: Optional[uuid.UUID] = Field(None, description="Country target for auto-matching")
    vat_required: bool = Field(False, description="Whether customer tax_id is mandatory to qualify")
    note: Optional[str] = Field(None, description="Mandatory legal disclaimer printed on invoice")


class FiscalPositionCreate(FiscalPositionBase):
    rules: List[FiscalPositionRuleBase] = Field(default_factory=list, description="Initial tax mapping rules")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Export Customer (Outside Jurisdiction)",
                "code": "FP_EXPORT",
                "description": "Zero-rated tax position for international exports",
                "auto_apply": False,
                "vat_required": False,
                "note": "Exempt from domestic VAT under Article 32 of Tax Law.",
                "rules": [],
            }
        }
    )


class FiscalPositionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    auto_apply: Optional[bool] = None
    country_id: Optional[uuid.UUID] = None
    vat_required: Optional[bool] = None
    note: Optional[str] = None


class FiscalPositionResponse(FiscalPositionBase):
    id: uuid.UUID
    company_id: uuid.UUID
    is_active: bool
    rules: List[FiscalPositionRuleResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Tax Calculation Engine Schemas
# ---------------------------------------------------------------------------

class TaxLineInput(BaseModel):
    line_id: Optional[str] = Field(None, description="Arbitrary client line identifier")
    price_unit: Decimal = Field(..., ge=0, description="Unit sales or purchase price")
    quantity: Decimal = Field(Decimal("1.0"), gt=0, description="Quantity")
    discount_percentage: Decimal = Field(Decimal("0.0"), ge=0, le=100, description="Line discount %")
    tax_ids: List[uuid.UUID] = Field(default_factory=list, description="Applicable tax IDs on line")


class TaxComputeRequest(BaseModel):
    lines: List[TaxLineInput] = Field(..., min_length=1, description="Order/Invoice lines to evaluate")
    fiscal_position_id: Optional[uuid.UUID] = Field(None, description="Optional fiscal position mapping")
    currency_rounding: Decimal = Field(Decimal("0.01"), gt=0, description="Smallest currency fraction")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "lines": [
                    {
                        "line_id": "line-1",
                        "price_unit": "100.00",
                        "quantity": "2.0",
                        "discount_percentage": "10.0",
                        "tax_ids": ["a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d"],
                    }
                ],
                "currency_rounding": "0.01",
            }
        }
    )


class TaxLineBreakdownItem(BaseModel):
    tax_id: uuid.UUID
    tax_name: str
    rate: Decimal
    base_amount: Decimal
    tax_amount: Decimal
    is_inclusive: bool


class TaxLineResult(BaseModel):
    line_id: Optional[str] = None
    price_unit: Decimal
    quantity: Decimal
    discount_percentage: Decimal
    effective_unit_price: Decimal
    net_subtotal: Decimal
    total_tax: Decimal
    total_amount: Decimal
    tax_breakdown: List[TaxLineBreakdownItem] = Field(default_factory=list)


class TaxSummaryItem(BaseModel):
    tax_id: uuid.UUID
    tax_name: str
    rate: Decimal
    total_base: Decimal
    total_tax: Decimal


class TaxComputeResponse(BaseModel):
    subtotal: Decimal = Field(..., description="Total net taxable subtotal across all lines")
    total_tax: Decimal = Field(..., description="Total tax amount across all lines")
    total_amount: Decimal = Field(..., description="Gross total (subtotal + total_tax)")
    fiscal_position_applied: Optional[str] = Field(None, description="Title of fiscal position applied, if any")
    lines: List[TaxLineResult]
    tax_summary: List[TaxSummaryItem]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "subtotal": "180.00",
                "total_tax": "27.00",
                "total_amount": "207.00",
                "fiscal_position_applied": None,
                "lines": [],
                "tax_summary": [],
            }
        }
    )
