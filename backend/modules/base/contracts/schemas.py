"""Pydantic schemas and DTOs for Contracts, Agreements & Subscriptions."""

import uuid
from decimal import Decimal
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Contract Line Schemas
# ---------------------------------------------------------------------------

class ContractLineBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Service or deliverable description")
    quantity: Decimal = Field(Decimal("1.0000"), gt=0, description="Delivered volume or subscription count")
    unit_price: Decimal = Field(Decimal("0.0000"), ge=0, description="Agreed rate per unit")


class ContractLineCreate(ContractLineBase):
    pass


class ContractLineResponse(ContractLineBase):
    id: uuid.UUID
    contract_id: uuid.UUID
    subtotal: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Contract Schemas
# ---------------------------------------------------------------------------

class ContractBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Contract or agreement title")
    party_id: uuid.UUID = Field(..., description="Target party (Customer, Vendor, or Employee) UUID")
    contract_type: str = Field(
        "customer",
        pattern="^(customer|vendor|employment|lease|subscription)$",
        description="Contract classification",
    )
    start_date: date = Field(..., description="Agreement effective start date")
    end_date: Optional[date] = Field(None, description="Expiration or termination date")
    billing_frequency: str = Field(
        "monthly",
        pattern="^(one_off|monthly|quarterly|semi_annual|annual)$",
        description="Payment or invoice cycle",
    )
    amount: Decimal = Field(Decimal("0.00"), ge=0, description="Total contract monetary commitment")
    currency_id: Optional[uuid.UUID] = Field(None, description="Contract anchor currency UUID")
    auto_renew: bool = Field(False, description="Whether contract automatically extends on expiry")
    notice_days: int = Field(30, ge=0, description="Required days of notice prior to termination")
    terms_and_conditions: Optional[str] = Field(None, description="Legal clauses or scope of work")
    notes: Optional[str] = Field(None, description="Internal commercial notes")


class ContractCreate(ContractBase):
    sequence_number: Optional[str] = Field(None, max_length=50, description="Custom reference or agreement number")
    lines: List[ContractLineCreate] = Field(default_factory=list, description="Deliverable lines")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sequence_number": "MSA-2026-004",
                "title": "Cloud Infrastructure Master Services Agreement",
                "party_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
                "contract_type": "customer",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "billing_frequency": "monthly",
                "amount": "120000.00",
                "auto_renew": True,
                "notice_days": 60,
                "lines": [
                    {
                        "name": "Dedicated Managed Kubernetes Cluster",
                        "quantity": "1.0000",
                        "unit_price": "10000.0000",
                    }
                ],
            }
        }
    )


class ContractUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    contract_type: Optional[str] = Field(None, pattern="^(customer|vendor|employment|lease|subscription)$")
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    billing_frequency: Optional[str] = Field(None, pattern="^(one_off|monthly|quarterly|semi_annual|annual)$")
    amount: Optional[Decimal] = Field(None, ge=0)
    currency_id: Optional[uuid.UUID] = None
    auto_renew: Optional[bool] = None
    notice_days: Optional[int] = Field(None, ge=0)
    terms_and_conditions: Optional[str] = None
    notes: Optional[str] = None


class ContractResponse(ContractBase):
    id: uuid.UUID
    company_id: uuid.UUID
    sequence_number: str
    state: str
    party_name: Optional[str] = None
    lines: List[ContractLineResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContractRenewRequest(BaseModel):
    new_end_date: date = Field(..., description="Extended agreement end date")


class ContractTerminateRequest(BaseModel):
    reason: Optional[str] = Field(None, description="Commercial or regulatory reason for early termination")
