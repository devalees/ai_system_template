"""Manifest for Module Settings Engine."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="settings",
    version="1.0.0",
    title="Module Settings Engine",
    description="Multi-tenant per-module dynamic JSONB configuration with Redis caching.",
    tier="base",
    depends_on=["identity_rbac"],
    ai_enabled=False,
    auto_install=True,
)
