"""Pydantic schemas for Module Settings."""

import uuid
from typing import Dict, Any
from pydantic import BaseModel, Field


class ModuleSettingsUpdate(BaseModel):
    settings_data: Dict[str, Any] = Field(..., description="Configuration dictionary to patch/merge")


class ModuleSettingsRead(BaseModel):
    module_name: str
    company_id: uuid.UUID
    settings_data: Dict[str, Any]
