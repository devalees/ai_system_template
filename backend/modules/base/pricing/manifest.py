"""Module manifest for Pricing Engine & Multi-Tier Price Lists."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="pricing",
    title="Pricing Engine & Multi-Tier Price Lists",
    description="Multi-currency price lists, volume tier breaks, promotional campaigns, and formula discount matrices.",
    version="1.0.0",
    tier="base",
    depends_on=["identity_rbac", "lookups"],
    auto_install=True,
    ai_enabled=True,
)
