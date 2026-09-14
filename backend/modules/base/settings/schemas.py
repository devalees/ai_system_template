"""Pydantic schemas for Module Settings with rich self-describing metadata."""

import uuid
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class SettingOption(BaseModel):
    """Select option specification for choice-based settings."""
    value: Any = Field(..., description="Machine-readable option value")
    label: str = Field(..., description="Human-readable option display label")


class SettingFieldMeta(BaseModel):
    """Self-describing metadata for a single configurable module setting."""
    key: str = Field(..., description="Setting attribute key name")
    label: str = Field(..., description="User-friendly display title")
    description: str = Field(..., description="Comprehensive explanation of the setting's business logic and impact")
    type: str = Field(..., description="Data type: 'boolean', 'integer', 'float', 'string', 'select', 'secret'")
    default: Any = Field(None, description="System default fallback value")
    options: Optional[List[SettingOption]] = Field(None, description="Allowed choices if type is 'select'")
    category: Optional[str] = Field("General", description="Settings grouping category for UI sectioning")


class ModuleSettingsUpdate(BaseModel):
    """Payload for updating or merging key-value configuration settings for a module."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "settings_data": {
                    "allow_registration": True,
                    "password_min_length": 10,
                    "session_expiry_hours": 48
                }
            }
        }
    )

    settings_data: Dict[str, Any] = Field(..., description="Configuration dictionary to patch/merge")


class ModuleSettingsRead(BaseModel):
    """Persisted module configuration record."""
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "module_name": "identity_rbac",
                "company_id": "a0000000-0000-0000-0000-000000000001",
                "settings_data": {
                    "allow_registration": True,
                    "enforce_2fa": False,
                    "password_min_length": 8,
                    "session_expiry_hours": 24
                },
                "fields": []
            }
        }
    )

    module_name: str
    company_id: uuid.UUID
    settings_data: Dict[str, Any]
    fields: Optional[List[SettingFieldMeta]] = None


class ModuleSettingsResponse(BaseModel):
    """Comprehensive module settings response containing active values and self-describing field schema."""
    module_name: str = Field(..., description="Namespace of the module")
    company_id: uuid.UUID = Field(..., description="Active tenant company UUID")
    settings_data: Dict[str, Any] = Field(..., description="Current effective configuration values (merged with defaults)")
    fields: List[SettingFieldMeta] = Field(default_factory=list, description="Self-describing field metadata and options for UI and agent reflection")

