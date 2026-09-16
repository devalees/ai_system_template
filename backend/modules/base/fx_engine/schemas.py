"""Pydantic schemas for Money, Multi-Currency & Historical FX Engine."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ExchangeRateBase(BaseModel):
    """Base fields for exchange rate definitions."""
    from_currency_id: uuid.UUID = Field(..., description="Source currency ID (lookup_currencies).")
    to_currency_id: uuid.UUID = Field(..., description="Target currency ID (lookup_currencies).")
    rate: Decimal = Field(..., gt=0, max_digits=18, decimal_places=6, description="Conversion multiplier (1 Source = Rate Target).")
    effective_date: date = Field(..., description="Date on which this rate took effect.")
    source: str = Field(default="manual", max_length=50, description="Rate provider: 'manual', 'central_bank', 'ecb', 'cbe'.")


class ExchangeRateCreate(ExchangeRateBase):
    """Payload for creating a new exchange rate entry."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "from_currency_id": "00000000-0000-0000-0000-000000000000",
                "to_currency_id": "00000000-0000-0000-0000-000000000001",
                "rate": 48.500000,
                "effective_date": "2026-03-15",
                "source": "central_bank",
            }
        }
    )


class ExchangeRateUpdate(BaseModel):
    """Payload for modifying an existing exchange rate."""
    rate: Optional[Decimal] = Field(default=None, gt=0, max_digits=18, decimal_places=6)
    source: Optional[str] = Field(default=None, max_length=50)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "rate": 49.100000,
                "source": "cbe",
            }
        }
    )


class ExchangeRateRead(ExchangeRateBase):
    """Serialized exchange rate details with relational currency codes."""
    id: uuid.UUID
    company_id: uuid.UUID
    inverse_rate: Optional[Decimal] = None
    from_currency_code: Optional[str] = None
    to_currency_code: Optional[str] = None
    version_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CurrencyConvertRequest(BaseModel):
    """Request payload for converting monetary amounts across currencies."""
    amount: Decimal = Field(..., description="Monetary quantity to convert.")
    from_currency_id: uuid.UUID = Field(..., description="Source currency ID.")
    to_currency_id: uuid.UUID = Field(..., description="Target currency ID.")
    effective_date: Optional[date] = Field(default=None, description="Valuation date (defaults to today).")
    round_precision: Optional[int] = Field(default=None, ge=0, le=6, description="Decimal places to round to (defaults to target currency decimal_places).")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "amount": 100.00,
                "from_currency_id": "00000000-0000-0000-0000-000000000000",
                "to_currency_id": "00000000-0000-0000-0000-000000000001",
                "effective_date": "2026-03-15",
            }
        }
    )


class CurrencyConvertResponse(BaseModel):
    """Structured response detailing the conversion calculation and exchange rate utilized."""
    amount: Decimal
    converted_amount: Decimal
    from_currency_code: str
    to_currency_code: str
    rate_used: Decimal
    effective_date: date
    triangulation_used: bool = False

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "amount": 100.00,
                "converted_amount": 4850.00,
                "from_currency_code": "USD",
                "to_currency_code": "EGP",
                "rate_used": 48.500000,
                "effective_date": "2026-03-15",
                "triangulation_used": False,
            }
        }
    )
