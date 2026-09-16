"""Enterprise Purchases Module Settings."""

from pydantic import BaseModel, Field
from typing import Literal
from modules.base.settings.service import SettingsService


class PurchaseSettings(BaseModel):
    """Configurable tenant-level procurement policies."""

    po_approval_threshold: float = Field(
        default=5000.0,
        ge=0.0,
        title="Purchase Order Approval Threshold",
        description="Purchase orders with total amounts exceeding this threshold require managerial approval before confirmation.",
        json_schema_extra={"category": "Approval Governance"}
    )
    three_way_matching_policy: Literal["enforce", "warn", "none"] = Field(
        default="warn",
        title="3-Way Matching Policy",
        description="Enforcement policy comparing Purchase Order price and quantity against Vendor Bills and Goods Receipts.",
        json_schema_extra={"category": "Vendor Billing & Control"}
    )
    lock_confirmed_orders: bool = Field(
        default=True,
        title="Lock Confirmed Purchase Orders",
        description="Automatically freeze confirmed Purchase Orders against direct line edits.",
        json_schema_extra={"category": "Audit & Compliance"}
    )


# Auto-register settings schema with SettingsService
SettingsService.register_module_settings("purchases", PurchaseSettings)
