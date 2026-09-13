"""Manifest contract for Identity & Contextual RBAC module."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="identity_rbac",
    version="1.0.0",
    title="Identity & Contextual RBAC",
    description="Foundational authentication, first-class AI agent identity, and 3-tier ownership RBAC.",
    tier="base",
    depends_on=[],
    ai_enabled=False,
    auto_install=True,
)
