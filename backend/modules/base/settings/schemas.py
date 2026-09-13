"""Pydantic schemas for Module Settings."""

import uuid
from typing import Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class ModuleSettingsUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "settings_data": {
                    "base_currency": "USD",
                    "fiscal_year_start": "01-01",
                    "auto_post_entries": True,
                    "tax_rounding": "round_globally"
                }
            }
        }
    )

    settings_data: Dict[str, Any] = Field(..., description="Configuration dictionary to patch/merge")


class ModuleSettingsRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "module_name": "inventory",
                "company_id": "a0000000-0000-0000-0000-000000000001",
                "settings_data": {
                    "reorder_point": 10,
                    "auto_notify": True,
                    "warehouse_code": "WH-MAIN"
                }
            }
        }
    )

    module_name: str
    company_id: uuid.UUID
    settings_data: Dict[str, Any]


class ModuleSettingsResponse(ModuleSettingsRead):
    pass
