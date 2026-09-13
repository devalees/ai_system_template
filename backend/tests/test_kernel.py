"""Unit and integration tests for Micro-Kernel DAG, manifest parser, and event bus."""

import pytest
from httpx import AsyncClient, ASGITransport
from core.manifest import ModuleManifest
from core.kernel import Kernel
from core.event_bus import EventBus
from core.exceptions import (
    CircularDependencyError,
    MissingDependencyError,
    EntityNotFoundException,
    PermissionDeniedException,
)
from core.app import create_app


def test_manifest_validation():
    """Verify snake_case enforcement and manifest contracts."""
    # Valid manifest
    manifest = ModuleManifest(
        name="sales_orders",
        title="Sales Orders",
        tier="app",
        depends_on=["identity_rbac", "lookups"],
        ai_enabled=True,
    )
    assert manifest.name == "sales_orders"
    assert manifest.tier == "app"
    assert manifest.ai_enabled is True

    # Invalid name (uppercase / spaces)
    with pytest.raises(ValueError):
        ModuleManifest(name="Sales Orders", title="Sales")

    with pytest.raises(ValueError):
        ModuleManifest(name="sales-orders", title="Sales")


def test_topological_sort_linear():
    """Verify linear dependency chain order resolution."""
    k = Kernel()
    k.register_manifest(ModuleManifest(name="a", title="A"))
    k.register_manifest(ModuleManifest(name="b", title="B", depends_on=["a"]))
    k.register_manifest(ModuleManifest(name="c", title="C", depends_on=["b"]))

    order = k.resolve_dependencies()
    assert order == ["a", "b", "c"]


def test_topological_sort_diamond():
    """Verify diamond dependency DAG resolution."""
    k = Kernel()
    k.register_manifest(ModuleManifest(name="base", title="Base"))
    k.register_manifest(ModuleManifest(name="rbac", title="RBAC", depends_on=["base"]))
    k.register_manifest(ModuleManifest(name="lookups", title="Lookups", depends_on=["base"]))
    k.register_manifest(ModuleManifest(name="crm", title="CRM", depends_on=["rbac", "lookups"]))

    order = k.resolve_dependencies()
    assert order.index("base") < order.index("rbac")
    assert order.index("base") < order.index("lookups")
    assert order.index("rbac") < order.index("crm")
    assert order.index("lookups") < order.index("crm")


def test_missing_dependency():
    """Verify MissingDependencyError is raised when a required module is missing."""
    k = Kernel()
    k.register_manifest(ModuleManifest(name="app", title="App", depends_on=["non_existent"]))

    with pytest.raises(MissingDependencyError) as exc_info:
        k.resolve_dependencies()
    assert "non_existent" in str(exc_info.value)


def test_circular_dependency():
    """Verify CircularDependencyError is raised when a cycle exists."""
    k = Kernel()
    k.register_manifest(ModuleManifest(name="alpha", title="Alpha", depends_on=["beta"]))
    k.register_manifest(ModuleManifest(name="beta", title="Beta", depends_on=["alpha"]))

    with pytest.raises(CircularDependencyError) as exc_info:
        k.resolve_dependencies()
    assert "Circular dependency detected" in str(exc_info.value)


@pytest.mark.asyncio
async def test_event_bus_pubsub():
    """Verify in-process async event dispatch and handler invocation."""
    bus = EventBus()
    received_events = []

    @bus.on("entity.created")
    async def handle_created(msg):
        received_events.append(msg)

    @bus.on("entity.*")
    async def handle_wildcard(msg):
        received_events.append({"wildcard": True, **msg})

    await bus.emit("entity.created", {"id": "rec-123", "amount": 100}, broadcast_redis=False)

    assert len(received_events) == 2
    assert received_events[0]["event"] == "entity.created"
    assert received_events[0]["payload"]["id"] == "rec-123"
    assert received_events[1]["wildcard"] is True


@pytest.mark.asyncio
async def test_kernel_modules_api():
    """Verify /api/v1/kernel/modules diagnostic endpoint."""
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/kernel/modules")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert "total_modules" in data
        assert "load_order" in data
        assert "modules" in data
        assert "ai_enabled_count" in data


@pytest.mark.asyncio
async def test_error_envelope_format():
    """Verify standardized machine-actionable error envelope for domain exceptions."""
    app = create_app()

    # Route that raises domain exception
    @app.get("/test/not-found")
    async def raise_not_found():
        raise EntityNotFoundException(entity_name="Customer", identifier="cust-999")

    @app.get("/test/forbidden")
    async def raise_forbidden():
        raise PermissionDeniedException(action="export", resource="sales.invoice")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Not found test
        res_404 = await client.get("/test/not-found")
        assert res_404.status_code == 404
        env_404 = res_404.json()
        assert "error" in env_404
        assert env_404["error"]["code"] == "ENTITY_NOT_FOUND"
        assert "cust-999" in env_404["error"]["message"]
        assert "resolution_hint" in env_404["error"]
        assert env_404["error"]["details"]["entity"] == "Customer"

        # Forbidden test
        res_403 = await client.get("/test/forbidden")
        assert res_403.status_code == 403
        env_403 = res_403.json()
        assert env_403["error"]["code"] == "PERMISSION_DENIED"
        assert env_403["error"]["resolution_hint"] != ""
