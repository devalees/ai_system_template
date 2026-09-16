"""Module manifest for Fiscal Calendar & Period Locking Engine."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="fiscal_calendar",
    title="Fiscal Calendar & Period Locking Engine",
    description="Multi-period financial calendar, period locking guards, and backdating transaction prevention.",
    version="1.0.0",
    tier="base",
    depends_on=["identity_rbac"],
    auto_install=True,
    ai_enabled=True,
    custom_permissions=[
        {"resource": "period", "action": "lock", "name": "Lock Fiscal Period"},
        {"resource": "period", "action": "reopen", "name": "Reopen Fiscal Period"},
        {"resource": "year", "action": "close", "name": "Close Fiscal Year"},
    ],
)
