"""Module Manifest for Enterprise Purchases & Procurement."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="purchases",
    title="Purchases & Vendor Procurement",
    description="Requests for Quotation, Purchase Orders, 3-Way Matching, and Vendor Bill Generation",
    version="1.0.0",
    tier="app",
    depends_on=[
        "accounting",
        "approvals",
    ],
    ai_enabled=True,
    auto_install=True,
)
