"""Module manifest for Company Calendar & Recurring Events."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="calendar",
    title="Company Calendar & Events",
    description="Enterprise calendar management, recurring events (RFC 5545 RRULE), attendee RSVPs, and iCalendar synchronization.",
    version="1.0.0",
    tier="base",
    depends_on=["identity_rbac", "parties"],
    auto_install=True,
    ai_enabled=True,
    custom_permissions=[
        {"resource": "calendar", "action": "create", "name": "Create Calendar Events"},
        {"resource": "calendar", "action": "read", "name": "View Calendar Events"},
        {"resource": "calendar", "action": "update", "name": "Edit Calendar Events"},
        {"resource": "calendar", "action": "delete", "name": "Delete Calendar Events"},
    ],
)
