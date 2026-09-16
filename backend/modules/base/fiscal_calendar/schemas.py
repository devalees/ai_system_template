"""Pydantic request and response schemas for Fiscal Calendar module."""

import uuid
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class FiscalPeriodBase(BaseModel):
    """Base fields for a fiscal accounting period."""
    name: str = Field(..., max_length=100, description="Descriptive name of the period (e.g. 'January 2026').")
    code: str = Field(..., max_length=50, description="Unique period code (e.g. '2026-01').")
    date_from: date = Field(..., description="Start date of the fiscal period.")
    date_to: date = Field(..., description="End date of the fiscal period.")
    period_type: str = Field(default="month", max_length=20, description="Period division type: 'month', 'quarter', 'opening', 'closing'.")
    state: str = Field(default="open", max_length=20, description="Operational lock state: 'open', 'closing', 'locked'.")


class FiscalPeriodCreate(FiscalPeriodBase):
    """Payload for creating a custom fiscal period directly."""
    fiscal_year_id: uuid.UUID = Field(..., description="ID of the parent fiscal year.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "fiscal_year_id": "00000000-0000-0000-0000-000000000000",
                "name": "January 2026",
                "code": "2026-01",
                "date_from": "2026-01-01",
                "date_to": "2026-01-31",
                "period_type": "month",
                "state": "open",
            }
        }
    )


class FiscalPeriodUpdate(BaseModel):
    """Payload for updating period attributes or state."""
    name: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=20, description="'open', 'closing', or 'locked'")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "January 2026 (Audited)",
                "state": "locked",
            }
        }
    )


class FiscalPeriodRead(FiscalPeriodBase):
    """Serialized representation of a fiscal period."""
    id: uuid.UUID
    company_id: uuid.UUID
    fiscal_year_id: uuid.UUID
    version_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FiscalYearBase(BaseModel):
    """Base fields for a fiscal year."""
    name: str = Field(..., max_length=100, description="Descriptive name of the fiscal year (e.g. 'Fiscal Year 2026').")
    code: str = Field(..., max_length=50, description="Unique code of the fiscal year (e.g. 'FY2026').")
    date_from: date = Field(..., description="Start date of the fiscal year.")
    date_to: date = Field(..., description="End date of the fiscal year.")


class FiscalYearCreate(FiscalYearBase):
    """Payload for creating a fiscal year with optional period auto-generation."""
    auto_generate_periods: bool = Field(default=True, description="Automatically generate monthly or quarterly periods.")
    period_type: str = Field(default="month", max_length=20, description="Period subdivision: 'month' or 'quarter'.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Fiscal Year 2026",
                "code": "FY2026",
                "date_from": "2026-01-01",
                "date_to": "2026-12-31",
                "auto_generate_periods": True,
                "period_type": "month",
            }
        }
    )


class FiscalYearUpdate(BaseModel):
    """Payload for updating fiscal year attributes."""
    name: Optional[str] = Field(default=None, max_length=100)
    is_closed: Optional[bool] = Field(default=None, description="Whether the fiscal year is officially closed.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Fiscal Year 2026 (Closed)",
                "is_closed": True,
            }
        }
    )


class FiscalYearRead(FiscalYearBase):
    """Serialized representation of a fiscal year with child periods."""
    id: uuid.UUID
    company_id: uuid.UUID
    is_closed: bool
    version_id: int
    created_at: datetime
    updated_at: datetime
    periods: List[FiscalPeriodRead] = []

    model_config = ConfigDict(from_attributes=True)


class DateValidationRequest(BaseModel):
    """Request validating whether a target date is open for posting transactions."""
    target_date: date = Field(..., description="The transaction posting date to validate.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "target_date": "2026-03-15",
            }
        }
    )


class DateValidationResponse(BaseModel):
    """Result of validating a transaction posting date against the fiscal calendar."""
    is_open: bool
    target_date: date
    period_id: Optional[uuid.UUID] = None
    period_code: Optional[str] = None
    period_state: Optional[str] = None
    year_code: Optional[str] = None
    message: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "is_open": True,
                "target_date": "2026-03-15",
                "period_id": "00000000-0000-0000-0000-000000000000",
                "period_code": "2026-03",
                "period_state": "open",
                "year_code": "FY2026",
                "message": "Period '2026-03' is open for transactions.",
            }
        }
    )
