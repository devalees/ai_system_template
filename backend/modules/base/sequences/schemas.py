"""Pydantic schemas for the Universal Sequence Engine."""

import uuid
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class SequenceBase(BaseModel):
    """Base attributes for a Sequence."""
    name: str = Field(..., max_length=100, description="Human-readable title of the sequence series", examples=["Customer Invoices 2026"])
    code: str = Field(..., max_length=50, description="Unique programmatic sequence code", examples=["account.invoice"])
    prefix: str = Field(default="", max_length=100, description="Prefix template supporting date tokens %(year)s, %(month)s, %(day)s", examples=["INV/%(year)s/"])
    suffix: str = Field(default="", max_length=100, description="Optional suffix template", examples=["-SA"])
    padding: int = Field(default=5, ge=1, le=12, description="Zero-padding length for generated sequential number", examples=[5])
    step: int = Field(default=1, ge=1, le=100, description="Increment step for each allocation", examples=[1])
    reset_period: str = Field(default="never", description="Automatic reset frequency: 'never' | 'yearly' | 'monthly' | 'daily'", examples=["yearly"])
    is_active: bool = Field(default=True, description="Whether this sequence is active and allocatable")


class SequenceCreate(SequenceBase):
    """Schema for creating a new sequence."""
    current_number: int = Field(default=0, ge=0, description="Initial base counter (next number will be current + step)", examples=[0])

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Customer Invoices 2026",
                "code": "account.invoice",
                "prefix": "INV/%(year)s/%(month)s/",
                "suffix": "",
                "padding": 5,
                "current_number": 0,
                "step": 1,
                "reset_period": "yearly",
                "is_active": True,
            }
        }
    )


class SequenceUpdate(BaseModel):
    """Schema for updating an existing sequence."""
    name: Optional[str] = Field(None, max_length=100, description="Human-readable title")
    prefix: Optional[str] = Field(None, max_length=100, description="Prefix template")
    suffix: Optional[str] = Field(None, max_length=100, description="Suffix template")
    padding: Optional[int] = Field(None, ge=1, le=12, description="Zero-padding length")
    current_number: Optional[int] = Field(None, ge=0, description="Override counter (use with caution)")
    step: Optional[int] = Field(None, ge=1, le=100, description="Increment step")
    reset_period: Optional[str] = Field(None, description="Reset frequency: 'never' | 'yearly' | 'monthly' | 'daily'")
    is_active: Optional[bool] = Field(None, description="Active status")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Customer Invoices 2026 (Updated)",
                "prefix": "INV/%(year)s/",
                "padding": 6,
            }
        }
    )


class SequenceRead(SequenceBase):
    """Schema for reading sequence details."""
    id: uuid.UUID = Field(..., description="Unique sequence record UUID")
    company_id: uuid.UUID = Field(..., description="Tenant company UUID")
    current_number: int = Field(..., description="Current highest allocated number")
    last_reset_date: Optional[datetime] = Field(None, description="Timestamp when the sequence counter was last reset")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class NextNumberRequest(BaseModel):
    """Optional parameters when requesting or previewing the next sequence number."""
    context_date: Optional[datetime] = Field(None, description="Context date for evaluating %(year)s, %(month)s, %(day)s tokens (defaults to current time)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "context_date": "2026-09-16T10:00:00Z"
            }
        }
    )


class NextNumberResponse(BaseModel):
    """Response returned upon allocating or previewing a sequence number."""
    sequence_number: str = Field(..., description="The fully formatted legal sequence string", examples=["INV/2026/09/00001"])
    code: str = Field(..., description="Sequence code", examples=["account.invoice"])
    number: int = Field(..., description="The raw integer allocated", examples=[1])
    is_preview: bool = Field(default=False, description="True if previewed without mutating the database counter")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sequence_number": "INV/2026/09/00001",
                "code": "account.invoice",
                "number": 1,
                "is_preview": False,
            }
        }
    )
