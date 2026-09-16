"""Module manifest for Product & Item Master Data."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="products",
    title="Product & Catalog Master Data",
    description="Universal product catalog, SKUs, inventory types, default pricing, UoMs, and tax linkages.",
    version="1.0.0",
    tier="base",
    depends_on=["identity_rbac", "lookups", "uom", "taxes"],
    auto_install=True,
    ai_enabled=True,
)
