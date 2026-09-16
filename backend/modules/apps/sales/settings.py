"""Enterprise Sales Module Settings."""

from pydantic import BaseModel, Field
from typing import Literal
from modules.base.settings.service import SettingsService


class SalesSettings(BaseModel):
    """Configurable tenant-level sales policies."""

    default_invoicing_policy: Literal["ordered", "delivered"] = Field(
        default="ordered",
        title="Default Invoicing Policy",
        description="Whether customer invoices are generated based on ordered quantities or delivered quantities.",
        json_schema_extra={"category": "Invoicing & Billing"}
    )
    quotation_validity_days: int = Field(
        default=30,
        ge=1,
        le=365,
        title="Quotation Validity Duration (Days)",
        description="Number of days after which customer quotations expire automatically.",
        json_schema_extra={"category": "Sales Orders"}
    )
    auto_invoice_on_confirmation: bool = Field(
        default=False,
        title="Auto-Draft Invoice on Order Confirmation",
        description="Automatically spawn a draft customer invoice in Accounting when a sales order is confirmed.",
        json_schema_extra={"category": "Invoicing & Billing"}
    )
    enable_discounts: bool = Field(
        default=True,
        title="Allow Line-Level Discounts",
        description="Permit sales representatives to apply discretionary percentage discounts on order lines.",
        json_schema_extra={"category": "Pricing & Discounts"}
    )


# Auto-register settings schema with SettingsService
SettingsService.register_module_settings("sales", SalesSettings)
