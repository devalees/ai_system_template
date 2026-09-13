"""Manifest for Lookups Module."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="lookups",
    version="1.0.0",
    title="Normalized Master Data & Lookups",
    description="Multi-tenant master data lookups for Countries, Cities, Currencies, Units of Measure, Tax Types, and Tags with ISO fixtures.",
    tier="base",
    depends_on=["identity_rbac"],
    ai_enabled=True,
    auto_install=True,
)
