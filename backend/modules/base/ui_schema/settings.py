"""Enterprise UI Schema, Branding, and Theme Settings."""

from pydantic import BaseModel, Field
from typing import Literal
from modules.base.settings.service import SettingsService


class UIThemeSettings(BaseModel):
    """Configurable company-level visual styling, layout presets, and branding defaults."""

    default_visual_theme: Literal["sovereign-dark", "enterprise-light", "high-density-erp", "nordic-minimal"] = Field(
        default="sovereign-dark",
        title="Default Visual Theme",
        description="Global design aesthetic: sovereign-dark (glassmorphism), enterprise-light (clean minimal), high-density-erp (accounting), nordic-minimal (soft dark).",
        json_schema_extra={"category": "Visual Appearance"},
    )
    default_shell_archetype: Literal["collapsible_sidebar", "top_navbar", "master_detail"] = Field(
        default="collapsible_sidebar",
        title="Application Shell Layout",
        description="Outer navigation framework: collapsible icon sidebar, classic top mega-menu, or split master-detail.",
        json_schema_extra={"category": "Navigation & Shell"},
    )
    default_density: Literal["comfortable", "compact"] = Field(
        default="comfortable",
        title="Data Density Mode",
        description="Table row padding and form element spacing.",
        json_schema_extra={"category": "Display Density"},
    )
    primary_brand_color: str = Field(
        default="#0ea5e9",
        title="Primary Brand Accent Color",
        description="Hex color code for primary action buttons, focus rings, and glowing badges.",
        json_schema_extra={"category": "Branding"},
    )
    font_family: str = Field(
        default="Inter, system-ui, sans-serif",
        title="Application Typography",
        description="Default CSS font family applied across the user interface.",
        json_schema_extra={"category": "Branding"},
    )
    allow_user_theme_override: bool = Field(
        default=True,
        title="Allow User Personal Overrides",
        description="Permit individual users to toggle between dark/light themes and compact mode independently.",
        json_schema_extra={"category": "User Preferences"},
    )


# Auto-register settings schema with central SettingsService
SettingsService.register_module_settings("ui_schema", UIThemeSettings)
