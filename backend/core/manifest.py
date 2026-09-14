"""Module Manifest Contract Specification for Sovereign Micro-Kernel."""

from typing import List, Optional, Dict, Any, Literal
from pathlib import Path
from pydantic import BaseModel, Field, field_validator


class ModuleManifest(BaseModel):
    """Declarative specification defining a pluggable module's properties and dependencies."""

    name: str = Field(..., description="Unique snake_case identifier for the module")
    version: str = Field(default="1.0.0", description="Semantic version string")
    title: str = Field(..., description="Human-readable title")
    description: Optional[str] = Field(default="", description="High-level summary of module capabilities")
    tier: Literal["base", "app"] = Field(
        default="base",
        description="Structural tier: 'base' utility or 'app' business vertical",
    )
    depends_on: List[str] = Field(
        default_factory=list,
        description="List of required module names that must load prior to this module",
    )
    ai_enabled: bool = Field(
        default=False,
        description="Whether this module exposes FastMCP tools and semantic categories to AI agents",
    )
    settings_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional Pydantic schema or dict describing configurable module settings",
    )
    auto_install: bool = Field(
        default=True,
        description="Whether to load and initialize this module automatically on kernel boot",
    )
    custom_permissions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Optional list of custom non-CRUD capability dicts, e.g. [{'action': 'approve', 'resource': 'invoice', 'name': 'Approve Invoice'}]",
    )
    module_dir: Optional[Path] = Field(
        default=None,
        description="Filesystem directory where the module package resides",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Enforce strict snake_case module naming."""
        if not v.islower() or not v.replace("_", "").isalnum():
            raise ValueError(f"Module name '{v}' must be lowercase alphanumeric with underscores (snake_case).")
        return v
