"""Enterprise Product Catalog Module Settings."""

from pydantic import BaseModel, Field
from typing import Literal
from modules.base.settings.service import SettingsService


class ProductSettings(BaseModel):
    """Configurable tenant-level product and catalog policies."""

    default_product_type: Literal["storable", "consumable", "service"] = Field(
        default="storable",
        title="Default Product Classification",
        description="Initial product type assigned when creating a new catalog item.",
        json_schema_extra={"category": "Catalog Defaults"},
    )
    enforce_unique_barcodes: bool = Field(
        default=True,
        title="Enforce Unique Barcodes / SKUs",
        description="Prevent duplicate item reference codes and barcodes across active products.",
        json_schema_extra={"category": "Product Identification"},
    )
    allow_negative_stock: bool = Field(
        default=False,
        title="Allow Negative Stock Operations",
        description="Allow sales deliveries and consumption when inventory balance drops below zero.",
        json_schema_extra={"category": "Inventory Policies"},
    )
    require_product_category: bool = Field(
        default=False,
        title="Require Category Assignment",
        description="Enforce that every product must be assigned to a hierarchical category before activation.",
        json_schema_extra={"category": "Catalog Governance"},
    )


# Auto-register settings schema with SettingsService
SettingsService.register_module_settings("products", ProductSettings)
