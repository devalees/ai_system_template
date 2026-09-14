"""Module manifest for Universal Headless Reporting & Document Engine."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="reporting",
    title="Universal Headless Reporting & Document Engine",
    description="Headless report generation, dynamic ORM aggregation, customizable document templates, and multi-format exports (JSON, CSV, XLSX, PDF)",
    version="1.0.0",
    tier="base",
    depends_on=["identity_rbac", "documents"],
    ai_enabled=True,
    auto_install=True,
    custom_permissions=[
        {"resource": "report", "action": "export", "name": "Export Report Files (PDF, Excel, CSV)"},
    ],
)
