"""Manifest for Automated Actions & Event-Driven TCA Subsystem."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="automated_actions",
    version="1.0.0",
    title="Event-Driven Automated Actions & TCA Engine",
    description="Multi-tenant Trigger-Condition-Action (TCA) automation engine with in-memory AST evaluation, lifecycle hooks, and pluggable action handlers.",
    tier="base",
    depends_on=["identity_rbac", "settings", "chatter", "mail_gateway", "notification_engine"],
    ai_enabled=True,
    auto_install=True,
)
