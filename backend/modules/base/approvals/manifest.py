"""Module manifest for Multi-Level Governance & Approval Engine."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="approvals",
    title="Multi-Level Governance & Approval Engine",
    description="Tiered multi-level approval workflows, AST condition gating, approver inbox, and audit trail actions.",
    version="1.0.0",
    tier="base",
    depends_on=["identity_rbac", "automated_actions", "workflows"],
    auto_install=True,
    ai_enabled=True,
    custom_permissions=[
        {"resource": "approval", "action": "manage_rules", "name": "Manage Approval Rules"},
        {"resource": "approval", "action": "act", "name": "Approve or Reject Requests"},
        {"resource": "approval", "action": "view_all", "name": "View All Company Approval Requests"},
    ],
)
