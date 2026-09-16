"""Module manifest for Composite Addresses & Geographic Locations."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="addresses",
    title="Composite Addresses & Geographic Locations",
    description="Polymorphic address management, geographic coordinate tracking, and normalized postal structures.",
    version="1.0.0",
    tier="base",
    depends_on=["identity_rbac", "lookups"],
    auto_install=True,
    ai_enabled=True,
)
