"""Manifest for Audit Logging Module."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="audit",
    version="1.0.0",
    title="Immutable Audit Trail & Diffs",
    description="Captures polymorphic mutations across all models with actor tracking and JSON state diffs.",
    tier="base",
    depends_on=["identity_rbac"],
    ai_enabled=True,
    auto_install=True,
)
