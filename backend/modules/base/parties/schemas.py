"""Pydantic schemas for Universal Party & Contact Engine."""

import uuid
from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class PartyContactBase(BaseModel):
    """Base fields for an individual contact representative."""
    name: str = Field(..., max_length=100, description="Full name of the contact person.")
    job_title: Optional[str] = Field(default="", max_length=100, description="Job position or title (e.g. 'Procurement Director').")
    email: Optional[str] = Field(default=None, max_length=150, description="Direct email address.")
    phone: Optional[str] = Field(default=None, max_length=50, description="Office telephone number.")
    mobile: Optional[str] = Field(default=None, max_length=50, description="Direct mobile phone number.")
    is_primary: bool = Field(default=False, description="Designates the primary contact person for this party.")


class PartyContactCreate(PartyContactBase):
    """Payload for creating a new contact."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Sarah Jenkins",
                "job_title": "Head of Accounts Payable",
                "email": "sarah.jenkins@acme.com",
                "phone": "+1-555-0199",
                "is_primary": True,
            }
        }
    )


class PartyContactUpdate(BaseModel):
    """Payload for updating an existing contact."""
    name: Optional[str] = Field(default=None, max_length=100)
    job_title: Optional[str] = Field(default=None, max_length=100)
    email: Optional[str] = Field(default=None, max_length=150)
    phone: Optional[str] = Field(default=None, max_length=50)
    mobile: Optional[str] = Field(default=None, max_length=50)
    is_primary: Optional[bool] = Field(default=None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_title": "Chief Financial Officer",
                "is_primary": True,
            }
        }
    )


class PartyContactRead(PartyContactBase):
    """Serialized contact representation."""
    id: uuid.UUID
    company_id: uuid.UUID
    party_id: uuid.UUID
    version_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PartyBase(BaseModel):
    """Base fields for a unified partner record."""
    name: str = Field(..., max_length=150, description="Commercial name of the party.")
    legal_name: Optional[str] = Field(default=None, max_length=200, description="Registered statutory legal name.")
    is_company: bool = Field(default=True, description="True for corporate organizations, False for individual persons.")
    parent_id: Optional[uuid.UUID] = Field(default=None, description="Parent holding company UUID for corporate hierarchies.")
    is_customer: bool = Field(default=False, description="Designates client / customer commercial role.")
    is_vendor: bool = Field(default=False, description="Designates supplier / vendor commercial role.")
    is_employee: bool = Field(default=False, description="Designates internal employee status.")
    tax_id: Optional[str] = Field(default=None, max_length=50, description="VAT or Tax Identification Number.")
    commercial_reg_no: Optional[str] = Field(default=None, max_length=50, description="Commercial Registry (CR) number.")
    currency_id: Optional[uuid.UUID] = Field(default=None, description="Default billing currency ID.")
    credit_limit: Decimal = Field(default=Decimal("0.00"), ge=0, description="Maximum credit threshold allowed.")
    linked_company_id: Optional[uuid.UUID] = Field(default=None, description="Internal company ID for inter-company netting.")
    email: Optional[str] = Field(default=None, max_length=150, description="Primary organization email address.")
    phone: Optional[str] = Field(default=None, max_length=50, description="General telephone switchboard.")
    website: Optional[str] = Field(default=None, max_length=200, description="Official website URL.")


class PartyCreate(PartyBase):
    """Payload for creating a party with optional initial contacts."""
    contacts: List[PartyContactCreate] = Field(default=[], description="Initial contacts to attach upon creation.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Acme Global Industries",
                "legal_name": "Acme Global Industries LLC",
                "is_company": True,
                "is_customer": True,
                "is_vendor": True,
                "tax_id": "TAX-99887766",
                "commercial_reg_no": "CR-104928",
                "credit_limit": 50000.00,
                "email": "info@acmeglobal.com",
                "website": "https://www.acmeglobal.com",
                "contacts": [
                    {
                        "name": "Sarah Jenkins",
                        "job_title": "Procurement Lead",
                        "email": "sarah@acmeglobal.com",
                        "is_primary": True,
                    }
                ],
            }
        }
    )


class PartyUpdate(BaseModel):
    """Payload for updating party attributes."""
    name: Optional[str] = Field(default=None, max_length=150)
    legal_name: Optional[str] = Field(default=None, max_length=200)
    is_company: Optional[bool] = Field(default=None)
    parent_id: Optional[uuid.UUID] = Field(default=None)
    is_customer: Optional[bool] = Field(default=None)
    is_vendor: Optional[bool] = Field(default=None)
    is_employee: Optional[bool] = Field(default=None)
    tax_id: Optional[str] = Field(default=None, max_length=50)
    commercial_reg_no: Optional[str] = Field(default=None, max_length=50)
    currency_id: Optional[uuid.UUID] = Field(default=None)
    credit_limit: Optional[Decimal] = Field(default=None, ge=0)
    linked_company_id: Optional[uuid.UUID] = Field(default=None)
    email: Optional[str] = Field(default=None, max_length=150)
    phone: Optional[str] = Field(default=None, max_length=50)
    website: Optional[str] = Field(default=None, max_length=200)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "credit_limit": 75000.00,
                "is_customer": True,
            }
        }
    )


class PartyRead(PartyBase):
    """Serialized party record with relational details."""
    id: uuid.UUID
    company_id: uuid.UUID
    version_id: int
    parent_name: Optional[str] = None
    currency_code: Optional[str] = None
    linked_company_name: Optional[str] = None
    contacts: List[PartyContactRead] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PartyHierarchyNode(BaseModel):
    """Recursive hierarchy node for organizational holding structures."""
    id: uuid.UUID
    name: str
    is_company: bool
    is_customer: bool
    is_vendor: bool
    subsidiaries: List["PartyHierarchyNode"] = []

    model_config = ConfigDict(from_attributes=True)
