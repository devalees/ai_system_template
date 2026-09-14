"""Pydantic request and response schemas for Master Data Lookups."""

import uuid
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


# 1. Country
class CountryCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "United States of America",
                "code": "USA",
                "code_alpha2": "US",
                "dialing_code": "+1",
                "currency_code": "USD",
            }
        }
    )

    name: str = Field(..., max_length=100)
    code: str = Field(..., min_length=2, max_length=3, description="ISO-3166-1 alpha-3 code (e.g. USA, SAU)")
    code_alpha2: Optional[str] = Field(None, max_length=2, description="ISO alpha-2 code (e.g. US, SA)")
    dialing_code: Optional[str] = Field(None, max_length=10)
    currency_code: Optional[str] = Field(None, max_length=3)


class CountryRead(CountryCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    is_active: bool


# 2. City
class CityCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "New York",
                "country_id": "c0000000-0000-0000-0000-000000000001",
                "state_or_province": "NY",
                "postal_code": "10001",
            }
        }
    )

    name: str = Field(..., max_length=100)
    country_id: uuid.UUID
    state_or_province: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)


class CityRead(CityCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    is_active: bool


# 3. Currency
class CurrencyCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "USD",
                "name": "US Dollar",
                "symbol": "$",
                "decimal_places": 2,
                "is_base": True,
            }
        }
    )

    code: str = Field(..., min_length=3, max_length=3, description="ISO-4217 Currency Code (e.g. USD, EUR)")
    name: str = Field(..., max_length=100)
    symbol: str = Field(..., max_length=10)
    decimal_places: int = Field(2, ge=0, le=6)
    is_base: bool = False


class CurrencyRead(CurrencyCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    is_active: bool


# 4. Unit Of Measure
class UnitOfMeasureCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Kilograms",
                "code": "KG",
                "category": "weight",
                "rounding_precision": 0.001,
            }
        }
    )

    name: str = Field(..., max_length=50)
    code: str = Field(..., max_length=20)
    category: str = Field("unit", max_length=50)
    rounding_precision: float = 0.01


class UnitOfMeasureRead(UnitOfMeasureCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    is_active: bool


# 5. Tax Type
class TaxTypeCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Standard VAT 15%",
                "code": "VAT_15",
                "rate": 15.0,
                "is_inclusive": False,
            }
        }
    )

    name: str = Field(..., max_length=100)
    code: str = Field(..., max_length=50)
    rate: float = Field(..., ge=0.0, le=100.0)
    is_inclusive: bool = False


class TaxTypeRead(TaxTypeCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    is_active: bool


# 6. Tag
class TagCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "High Priority",
                "color": "#ef4444",
                "model_target": "lead",
            }
        }
    )

    name: str = Field(..., max_length=50)
    color: str = Field("#3b82f6", max_length=20)
    model_target: Optional[str] = Field(None, max_length=100)


class TagRead(TagCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    is_active: bool


# 7. Category
class CategoryCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Legal Contracts",
                "code": "DOC_LEGAL",
                "res_model": "document",
                "parent_id": None,
                "description": "Corporate contracts, agreements, and NDAs",
                "color": "#3b82f6",
                "icon": "folder",
                "sequence": 10,
            }
        }
    )

    name: str = Field(..., min_length=1, max_length=100, description="Human-readable category name")
    code: str = Field(..., min_length=1, max_length=50, description="Machine code or slug unique within tenant and res_model")
    res_model: str = Field("general", max_length=100, description="Domain entity or module scope (e.g. document, mail_template, product)")
    parent_id: Optional[uuid.UUID] = Field(None, description="Optional parent category UUID for sub-classification")
    description: Optional[str] = Field(None, max_length=255, description="Optional category description")
    color: str = Field("#3b82f6", max_length=20, description="Hex color badge for UI")
    icon: Optional[str] = Field(None, max_length=50, description="Icon identifier for UI navigation")
    sequence: int = Field(10, ge=0, description="Sorting sequence order in UI")


class CategoryUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Employment Agreements",
                "parent_id": "c0000000-0000-0000-0000-000000000001",
                "sequence": 20,
            }
        }
    )

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    res_model: Optional[str] = Field(None, max_length=100)
    parent_id: Optional[uuid.UUID] = Field(None, description="Set parent UUID for sub-classification, or null for root")
    description: Optional[str] = Field(None, max_length=255)
    color: Optional[str] = Field(None, max_length=20)
    icon: Optional[str] = Field(None, max_length=50)
    sequence: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    code: str
    res_model: str
    parent_id: Optional[uuid.UUID] = None
    parent_name: Optional[str] = None
    description: Optional[str] = None
    color: str
    icon: Optional[str] = None
    sequence: int
    is_active: bool
    full_path: Optional[str] = None
    children_count: int = 0


class CategoryTreeRead(CategoryRead):
    children: List["CategoryTreeRead"] = []
