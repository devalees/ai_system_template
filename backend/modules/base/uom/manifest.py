"""Module manifest for Unit of Measure & Conversion Matrix."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="uom",
    title="Unit of Measure & Conversion Matrix",
    description="Multi-category unit of measure conversion ratio matrix, reference unit normalization, and product-specific cross-category rules.",
    version="1.0.0",
    tier="base",
    depends_on=["identity_rbac"],
    auto_install=True,
    ai_enabled=True,
)
