"""Module manifest for Contracts, Agreements & Subscriptions."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="contracts",
    title="Contracts, Agreements & Subscriptions",
    description="Commercial contracts, master service agreements, recurring subscriptions, renewal policies, and life-cycle auditing.",
    version="1.0.0",
    tier="base",
    depends_on=["identity_rbac", "lookups", "parties"],
    auto_install=True,
    ai_enabled=True,
)
