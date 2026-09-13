"""Manifest for Notification Engine Module."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="notification_engine",
    version="1.0.0",
    title="Multi-Channel Notification Engine",
    description="Multi-channel notification dispatcher supporting In-App WebSocket alerts, WebPush (VAPID), Mobile push formatting, and user preference matrices.",
    tier="base",
    depends_on=["identity_rbac"],
    ai_enabled=True,
    auto_install=True,
)
