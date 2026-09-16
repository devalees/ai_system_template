"""Module manifest for Universal Work Items, Tasks & Dependencies."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="work_items",
    title="Universal Work Items, Tasks & Dependencies",
    description="Cross-entity work items, sub-task hierarchies, dependency DAGs, and Kanban stage transitions.",
    version="1.0.0",
    tier="base",
    depends_on=["identity_rbac", "lookups"],
    auto_install=True,
    ai_enabled=True,
)
