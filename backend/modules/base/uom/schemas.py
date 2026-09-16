"""Pydantic schemas and DTOs for Unit of Measure & Conversion Matrix."""

import uuid
from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Category Schemas
# ---------------------------------------------------------------------------

class UOMCategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Category name (e.g. Weight, Volume, Length)")
    description: Optional[str] = Field(None, description="Detailed category description")


class UOMCategoryCreate(UOMCategoryBase):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Weight",
                "description": "Mass and weight measurements (Kilograms, Grams, Tons).",
            }
        }
    )


class UOMCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class UOMCategoryResponse(UOMCategoryBase):
    id: uuid.UUID
    company_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Unit Schemas
# ---------------------------------------------------------------------------

class UOMUnitBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Unit name (e.g. Kilogram)")
    code: str = Field(..., min_length=1, max_length=20, description="Unique unit code (e.g. kg)")
    symbol: Optional[str] = Field(None, max_length=20, description="Measurement symbol (e.g. kg)")
    uom_type: str = Field("reference", pattern="^(reference|bigger|smaller)$", description="Type relative to category reference")
    ratio: Decimal = Field(Decimal("1.0"), gt=0, description="Conversion ratio relative to reference unit")
    rounding_precision: Decimal = Field(Decimal("0.01"), gt=0, description="Rounding precision")


class UOMUnitCreate(UOMUnitBase):
    category_id: uuid.UUID = Field(..., description="Parent UOM Category ID")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "category_id": "00000000-0000-0000-0000-000000000000",
                "name": "Metric Ton",
                "code": "t",
                "symbol": "t",
                "uom_type": "bigger",
                "ratio": 1000.0,
                "rounding_precision": 0.001,
            }
        }
    )


class UOMUnitUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    symbol: Optional[str] = None
    uom_type: Optional[str] = Field(None, pattern="^(reference|bigger|smaller)$")
    ratio: Optional[Decimal] = Field(None, gt=0)
    rounding_precision: Optional[Decimal] = Field(None, gt=0)
    is_active: Optional[bool] = None


class UOMUnitResponse(UOMUnitBase):
    id: uuid.UUID
    company_id: uuid.UUID
    category_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Conversion Rule Schemas
# ---------------------------------------------------------------------------

class UOMConversionRuleCreate(BaseModel):
    from_uom_id: uuid.UUID = Field(..., description="Source unit ID")
    to_uom_id: uuid.UUID = Field(..., description="Target unit ID")
    ratio: Decimal = Field(..., gt=0, description="Conversion multiplier: 1 from_uom = ratio * to_uom")
    res_model: Optional[str] = Field(None, max_length=100, description="Optional entity model (e.g. product)")
    res_id: Optional[uuid.UUID] = Field(None, description="Optional entity record ID")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "from_uom_id": "00000000-0000-0000-0000-000000000001",
                "to_uom_id": "00000000-0000-0000-0000-000000000002",
                "ratio": 0.92,
                "res_model": "product",
            }
        }
    )


class UOMConversionRuleResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    from_uom_id: uuid.UUID
    to_uom_id: uuid.UUID
    ratio: Decimal
    res_model: Optional[str] = None
    res_id: Optional[uuid.UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Conversion Evaluation Schemas
# ---------------------------------------------------------------------------

class UOMConvertRequest(BaseModel):
    quantity: Decimal = Field(..., gt=0, description="Quantity to convert")
    from_uom_id: Optional[uuid.UUID] = Field(None, description="Source unit ID (or use code)")
    from_uom_code: Optional[str] = Field(None, description="Source unit code (e.g. 'kg')")
    to_uom_id: Optional[uuid.UUID] = Field(None, description="Target unit ID (or use code)")
    to_uom_code: Optional[str] = Field(None, description="Target unit code (e.g. 'g')")
    res_model: Optional[str] = Field(None, description="Optional item model for item-specific rules")
    res_id: Optional[uuid.UUID] = Field(None, description="Optional item record ID")

    @model_validator(mode="after")
    def check_uoms_specified(self) -> "UOMConvertRequest":
        if not self.from_uom_id and not self.from_uom_code:
            raise ValueError("Must specify either from_uom_id or from_uom_code.")
        if not self.to_uom_id and not self.to_uom_code:
            raise ValueError("Must specify either to_uom_id or to_uom_code.")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "quantity": 2.5,
                "from_uom_code": "t",
                "to_uom_code": "kg",
            }
        }
    )


class UOMConvertResponse(BaseModel):
    original_quantity: Decimal
    from_uom_code: str
    converted_quantity: Decimal
    to_uom_code: str
    conversion_factor: Decimal
    method: str  # intra_category | explicit_rule

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "original_quantity": 2.5,
                "from_uom_code": "t",
                "converted_quantity": 2500.0,
                "to_uom_code": "kg",
                "conversion_factor": 1000.0,
                "method": "intra_category",
            }
        }
    )
