"""Manifest for Unified Atomic Backup Module."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="backup",
    version="1.0.0",
    title="Unified Atomic Backup & Archive Engine",
    description="Atomic archive generator packaging PostgreSQL DDL/data dumps, filestore attachments, and JSON metadata into compressed .tar.gz bundles with cryptographic integrity verification.",
    tier="base",
    depends_on=["identity_rbac", "documents"],
    ai_enabled=True,
    auto_install=True,
)
