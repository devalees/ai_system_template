"""Automated health and baseline route test suite."""

import pytest
from httpx import AsyncClient, ASGITransport
from core.app import create_app

app = create_app()


@pytest.mark.asyncio
async def test_root_endpoint():
    """Verify root platform information."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["platform"] == "Sovereign Headless Backend Platform"
        assert data["version"] == "1.0.0"
        assert data["status"] == "online"
        assert data["docs"] == "/docs"
        assert data["health"] == "/health"


@pytest.mark.asyncio
async def test_health_check_structure():
    """Verify health check response schema and diagnostic keys."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
        # 200 when DB/Redis are connected, 503 when running without external services
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "degraded"]
        assert "components" in data
        assert "database" in data["components"]
        assert "redis" in data["components"]
        assert "celery_broker" in data["components"]
        assert "version" in data
        assert "timestamp" in data
