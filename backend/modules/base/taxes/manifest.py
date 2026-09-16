"""Module manifest for Tax Engine & Fiscal Positions."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="taxes",
    title="Tax Engine & Fiscal Positions",
    description="Multi-jurisdiction enterprise tax calculation engine, fiscal positions, compound/inclusive taxes, and tax mapping rules.",
    version="1.0.0",
    tier="base",
    depends_on=["identity_rbac", "lookups"],
    auto_install=True,
    ai_enabled=True,
)
