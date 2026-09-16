"""Manifest for Metadata-Driven Dynamic UI Engine & View Registry Module."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="ui_schema",
    version="1.0.0",
    title="Dynamic UI Schema & View Engine",
    description="Declarative UI schema generator, view registry, resizable split-panel layouts, and drag-and-drop studio personalization.",
    tier="base",
    depends_on=["identity_rbac", "automated_actions", "chatter"],
    ai_enabled=True,
    auto_install=True,
)
