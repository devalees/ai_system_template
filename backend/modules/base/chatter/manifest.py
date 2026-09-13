"""Manifest for Chatter Module."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="chatter",
    version="1.0.0",
    title="Polymorphic Discussion & Real-time Collaboration",
    description="Entity chatter threads supporting comments, notifications, AI agent findings, and WebSocket broadcasts via Redis Pub/Sub.",
    tier="base",
    depends_on=["identity_rbac"],
    ai_enabled=True,
    auto_install=True,
)
