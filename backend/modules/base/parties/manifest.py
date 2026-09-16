"""Module manifest for Universal Party & Contact Engine."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="parties",
    title="Universal Party & Contact Engine",
    description="Unified Partner model (Customer/Vendor dual roles), corporate hierarchies, child contacts, and inter-company entity linkage.",
    version="1.0.0",
    tier="base",
    depends_on=["identity_rbac", "lookups", "addresses"],
    auto_install=True,
    ai_enabled=True,
)
