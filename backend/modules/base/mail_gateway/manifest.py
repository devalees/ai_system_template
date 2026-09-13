"""Manifest for Mail Gateway Module."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="mail_gateway",
    version="1.0.0",
    title="Mail Gateway & Async Email Pipeline",
    description="Outbound SMTP email pipeline with Jinja2 templating, Celery async queued dispatch, and bounce/delivery tracking.",
    tier="base",
    depends_on=["identity_rbac"],
    ai_enabled=True,
    auto_install=True,
)
