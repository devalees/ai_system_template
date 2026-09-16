"""Enterprise Accounting Module Settings."""

from pydantic import BaseModel, Field
from typing import Literal
from modules.base.settings.service import SettingsService


class AccountingSettings(BaseModel):
    """Configurable tenant-level financial and accounting policies."""

    tax_cash_basis: bool = Field(
        default=False,
        title="Tax Cash Basis",
        description="Calculate VAT and sales tax on payment collection rather than on invoice posting.",
        json_schema_extra={"category": "Tax & Compliance"}
    )
    anglo_saxon_accounting: bool = Field(
        default=False,
        title="Anglo-Saxon Accounting",
        description="Record Cost of Goods Sold (COGS) at product delivery rather than standard continental expensing.",
        json_schema_extra={"category": "Valuation & Ledgers"}
    )
    auto_post_depreciation: bool = Field(
        default=True,
        title="Automated Monthly Depreciation",
        description="Automatically generate and post monthly asset depreciation journal entries via background workers.",
        json_schema_extra={"category": "Asset Management"}
    )
    budget_enforcement_level: Literal["warn", "block", "none"] = Field(
        default="warn",
        title="Budget Overrun Policy",
        description="Behavior when transactions exceed planned budget lines: 'warn' shows alerts, 'block' prevents posting, 'none' permits posting.",
        json_schema_extra={"category": "Budgeting & Financial Control"}
    )
    budget_warning_threshold: float = Field(
        default=90.0,
        ge=50.0,
        le=100.0,
        title="Budget Warning Threshold (%)",
        description="Percentage of budget utilization that triggers warning alerts.",
        json_schema_extra={"category": "Budgeting & Financial Control"}
    )
    lock_posted_moves: bool = Field(
        default=True,
        title="Hard Lock on Posted Journal Moves",
        description="Strictly block editing or direct deletion of posted journal entries.",
        json_schema_extra={"category": "Audit & Compliance"}
    )


# Auto-register settings schema with SettingsService
SettingsService.register_module_settings("accounting", AccountingSettings)
