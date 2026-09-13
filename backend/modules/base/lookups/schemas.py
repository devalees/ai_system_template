"""Pydantic request and response schemas for Master Data Lookups."""

import uuid
from typing import Optional
from pydantic import BaseModel, Field


# 1. Country
class CountryCreate(BaseModel):
    name: str = Field(..., max_length=100)
    code: str = Field(..., min_length=2, max_length=3, description="ISO-3166-1 alpha-3 code (e.g. USA, SAU)")
    code_alpha2: Optional[str] = Field(None, max_length=2, description="ISO alpha-2 code (e.g. US, SA)")
    dialing_code: Optional[str] = Field(None, max_length=10)
    currency_code: Optional[str] = Field(None, max_length=3)


class CountryRead(CountryCreate):
    id: uuid.UUID
    company_id: uuid.UUID
    is_active: bool


# 2. City
class CityCreate(BaseModel):
    name: str = Field(..., max_length=100)
    country_id: uuid.UUID
    state_or_province: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)


class CityRead(CityCreate):
    id: uuid.UUID
    company_id: uuid.UUID
    is_active: bool


# 3. Currency
class CurrencyCreate(BaseModel):
    code: str = Field(..., min_length=3, max_length=3, description="ISO-4217 Currency Code (e.g. USD, EUR)")
    name: str = Field(..., max_length=100)
    symbol: str = Field(..., max_length=10)
    decimal_places: int = Field(2, ge=0, le=6)
    is_base: bool = False


class CurrencyRead(CurrencyCreate):
    id: uuid.UUID
    company_id: uuid.UUID
    is_active: bool


# 4. Unit Of Measure
class UnitOfMeasureCreate(BaseModel):
    name: str = Field(..., max_length=50)
    code: str = Field(..., max_length=20)
    category: str = Field("unit", max_length=50)
    rounding_precision: float = 0.01


class UnitOfMeasureRead(UnitOfMeasureCreate):
    id: uuid.UUID
    company_id: uuid.UUID
    is_active: bool


# 5. Tax Type
class TaxTypeCreate(BaseModel):
    name: str = Field(..., max_length=100)
    code: str = Field(..., max_length=50)
    rate: float = Field(..., ge=0.0, le=100.0)
    is_inclusive: bool = False


class TaxTypeRead(TaxTypeCreate):
    id: uuid.UUID
    company_id: uuid.UUID
    is_active: bool


# 6. Tag
class TagCreate(BaseModel):
    name: str = Field(..., max_length=50)
    color: str = Field("#3b82f6", max_length=20)
    model_target: Optional[str] = Field(None, max_length=100)


class TagRead(TagCreate):
    id: uuid.UUID
    company_id: uuid.UUID
    is_active: bool
