"""Module manifest for Payment Terms, Methods & Transactions."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="payments",
    title="Payment Terms, Methods & Transactions",
    description="Payment methods, installment terms calculation, cash flow schedules, and multi-currency transactions.",
    version="1.0.0",
    tier="base",
    depends_on=["identity_rbac", "lookups", "fx_engine"],
    auto_install=True,
    ai_enabled=True,
)
