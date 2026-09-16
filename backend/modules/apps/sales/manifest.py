"""Module Manifest for Enterprise Sales Order Management."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="sales",
    title="Sales & Customer Order Management",
    description="Quotations, Sales Orders, Pricing Rules, Customer Invoicing Bridge",
    version="1.0.0",
    tier="app",
    depends_on=[
        "accounting",
        "pricing",
        "addresses",
    ],
    ai_enabled=True,
    auto_install=True,
)
