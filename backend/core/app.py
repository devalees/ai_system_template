"""FastAPI application factory and system diagnostics."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any
from datetime import datetime, timezone
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
import redis.asyncio as aioredis

from core.config import settings
from core.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown events."""
    yield
    # Safely close database connection pool
    await engine.dispose()


def create_app() -> FastAPI:
    """Instantiate and configure the FastAPI application."""
    app = FastAPI(
        title="Sovereign Headless Backend Platform",
        description="High-performance async micro-kernel backend platform for sovereign enterprise apps.",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Enable CORS for frontend and external integrations
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["System Diagnostics"])
    async def health_check() -> JSONResponse:
        """Asynchronous system health check verifying database, redis, and celery connectivity."""
        components: Dict[str, str] = {}
        all_healthy = True

        # 1. PostgreSQL Database Ping
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            components["database"] = "connected"
        except Exception as exc:
            components["database"] = f"error: {str(exc)}"
            all_healthy = False

        # 2. Redis Cache Ping
        try:
            r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
            await r.ping()
            await r.aclose()
            components["redis"] = "connected"
        except Exception as exc:
            components["redis"] = f"error: {str(exc)}"
            all_healthy = False

        # 3. Celery Broker Connectivity
        try:
            r_celery = aioredis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=2)
            await r_celery.ping()
            await r_celery.aclose()
            components["celery_broker"] = "connected"
        except Exception as exc:
            components["celery_broker"] = f"error: {str(exc)}"
            all_healthy = False

        response_payload = {
            "status": "healthy" if all_healthy else "degraded",
            "components": components,
            "version": "1.0.0",
            "environment": settings.ENVIRONMENT,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        http_status = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(status_code=http_status, content=response_payload)

    @app.get("/", tags=["System Diagnostics"])
    async def root_endpoint() -> Dict[str, Any]:
        """Root API platform status and documentation links."""
        return {
            "platform": "Sovereign Headless Backend Platform",
            "version": "1.0.0",
            "status": "online",
            "docs": "/docs",
            "health": "/health",
        }

    return app
