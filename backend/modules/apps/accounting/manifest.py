"""Module Manifest for Enterprise Accounting & General Ledger."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="accounting",
    title="Financial Accounting & General Ledger",
    description="Enterprise Double-Entry Accounting, Invoicing, Asset Depreciation, Budgets & Analytic Cost Centers",
    version="1.0.0",
    tier="app",
    depends_on=[
        "identity_rbac",
        "settings",
        "lookups",
        "sequences",
        "fiscal_calendar",
        "fx_engine",
        "parties",
        "taxes",
        "payments",
        "workflows",
        "reporting",
    ],
    ai_enabled=True,
    auto_install=True,
)
