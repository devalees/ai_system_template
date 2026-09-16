"""Pydantic schemas for Addresses module."""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class AddressBase(BaseModel):
    """Base fields for address creation and serialization."""
    res_model: Optional[str] = Field(default=None, max_length=100, description="Target model name (e.g. 'Party', 'Company', 'Warehouse').")
    res_id: Optional[uuid.UUID] = Field(default=None, description="Target entity primary key UUID.")
    title: Optional[str] = Field(default="", max_length=100, description="Address label (e.g. 'Headquarters', 'Warehouse #3').")
    address_type: str = Field(
        default="billing",
        max_length=30,
        description="Address purpose: 'billing', 'shipping', 'branch', 'warehouse', 'contact', 'headquarters', 'other'.",
    )
    is_default: bool = Field(default=False, description="Whether this is the primary/default address for this address_type.")
    street1: str = Field(..., max_length=255, description="Primary street address line.")
    street2: Optional[str] = Field(default=None, max_length=255, description="Secondary address line (suite, building, floor).")
    postal_code: Optional[str] = Field(default=None, max_length=20, description="Postal code or ZIP.")
    state_province: Optional[str] = Field(default=None, max_length=100, description="State, province, or governorate.")
    city_id: Optional[uuid.UUID] = Field(default=None, description="Normalized foreign key to lookup_cities.")
    country_id: Optional[uuid.UUID] = Field(default=None, description="Normalized foreign key to lookup_countries.")
    geo_lat: Optional[float] = Field(default=None, description="Geographic latitude coordinate (-90 to 90).")
    geo_lng: Optional[float] = Field(default=None, description="Geographic longitude coordinate (-180 to 180).")


class AddressCreate(AddressBase):
    """Payload for creating a new address record."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "res_model": "Company",
                "res_id": "00000000-0000-0000-0000-000000000000",
                "title": "Cairo Headquarters",
                "address_type": "headquarters",
                "is_default": True,
                "street1": "90th Street, Fifth Settlement",
                "street2": "Building 45, Floor 3",
                "postal_code": "11835",
                "state_province": "Cairo",
                "geo_lat": 30.0131,
                "geo_lng": 31.4289,
            }
        }
    )


class AddressUpdate(BaseModel):
    """Payload for updating an existing address record."""
    title: Optional[str] = Field(default=None, max_length=100)
    address_type: Optional[str] = Field(default=None, max_length=30)
    is_default: Optional[bool] = Field(default=None)
    street1: Optional[str] = Field(default=None, max_length=255)
    street2: Optional[str] = Field(default=None, max_length=255)
    postal_code: Optional[str] = Field(default=None, max_length=20)
    state_province: Optional[str] = Field(default=None, max_length=100)
    city_id: Optional[uuid.UUID] = Field(default=None)
    country_id: Optional[uuid.UUID] = Field(default=None)
    geo_lat: Optional[float] = Field(default=None)
    geo_lng: Optional[float] = Field(default=None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "street2": "Building 45, Floor 4 (Expanded)",
                "is_default": True,
            }
        }
    )


class AddressRead(AddressBase):
    """Serialized address response."""
    id: uuid.UUID
    company_id: uuid.UUID
    version_id: int
    created_at: datetime
    updated_at: datetime
    formatted_address: Optional[str] = None
    city_name: Optional[str] = None
    country_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
