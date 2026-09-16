"""Module manifest for Money, Multi-Currency & Historical FX Engine."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="fx_engine",
    title="Money, Multi-Currency & Historical FX Engine",
    description="Multi-currency conversion, daily historical exchange rates, precision rounding, and triangulation math.",
    version="1.0.0",
    tier="base",
    depends_on=["identity_rbac", "lookups"],
    auto_install=True,
    ai_enabled=True,
)
