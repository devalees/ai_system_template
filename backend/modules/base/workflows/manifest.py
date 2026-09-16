"""Manifest for Workflows & State Machine Engine module."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="workflows",
    title="Workflow State Machine & Record Freeze",
    version="1.0.0",
    description="Declarative workflow state machine engine with AST condition guards, RBAC gating, and automatic record freezing.",
    author="Sovereign Core Team",
    category="Base",
    tier="base",
    depends_on=["identity_rbac", "automated_actions"],
    auto_install=True,
    ai_enabled=True,
    custom_permissions=[
        {"resource": "workflow", "action": "manage", "name": "Manage Workflow Definitions"},
        {"resource": "workflow", "action": "transition", "name": "Execute Workflow Transitions"},
        {"resource": "workflow", "action": "override_freeze", "name": "Override Frozen Records"},
    ],
)
