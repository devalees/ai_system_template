"""Module manifest for Resource Scheduling & Capacity Allocation."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="resources",
    title="Resource Scheduling & Capacity Allocation",
    description="Universal enterprise resources (human, equipment, vehicle, space), capacity calendars, collision detection, and scheduled allocations.",
    version="1.0.0",
    tier="base",
    depends_on=["identity_rbac", "calendar"],
    auto_install=True,
    ai_enabled=True,
)
