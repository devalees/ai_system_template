"""Manifest for Universal Import/Export Module."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="import_export",
    version="1.0.0",
    title="Universal Streaming Import & Export",
    description="High-performance streaming engine for CSV, Excel (openpyxl), and JSON bulk datasets with Celery asynchronous execution, dynamic field mapping, and validation.",
    tier="base",
    depends_on=["identity_rbac"],
    ai_enabled=True,
    auto_install=True,
)
