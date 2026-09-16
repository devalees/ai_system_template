"""Manifest for Sequences Module."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="sequences",
    version="1.0.0",
    title="Universal Sequence & Legal Auto-Numbering Engine",
    description="Multi-tenant, concurrency-safe, gapless auto-numbering engine with dynamic prefix/suffix formatting and reset periods.",
    tier="base",
    depends_on=["identity_rbac"],
    ai_enabled=True,
    auto_install=True,
)
