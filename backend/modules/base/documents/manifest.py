"""Manifest for Documents Module."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="documents",
    version="1.0.0",
    title="Document & Blob Storage Engine",
    description="Content-addressable attachment manager saving blobs to filestore by SHA-256 with inherited permission checks.",
    tier="base",
    depends_on=["identity_rbac"],
    ai_enabled=True,
    auto_install=True,
)
