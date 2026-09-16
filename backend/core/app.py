"""FastAPI application factory, lifecycle management, and micro-kernel integration."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any, List
from datetime import datetime, timezone
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
import redis.asyncio as aioredis

from sqlalchemy.orm.exc import StaleDataError

from core.config import settings
from core.context import MultiTenancyContextMiddleware
from core.idempotency import IdempotencyMiddleware
from core.database import engine
from core.kernel import kernel
from core.event_bus import event_bus
from core.exceptions import (
    PlatformException,
    platform_exception_handler,
    validation_exception_handler,
    global_exception_handler,
    stale_data_exception_handler,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown events with async micro-kernel bootstrap."""
    # Run async migrations and bootstrap hooks
    await kernel.migrate()
    await kernel.bootstrap()
    yield
    # Teardown resources
    await event_bus.close()
    await engine.dispose()


def create_app() -> FastAPI:
    """Instantiate and configure the FastAPI application with synchronous module router mounting."""
    app = FastAPI(
        title="Sovereign Headless Backend Platform",
        description="High-performance async micro-kernel backend platform for sovereign enterprise apps.",
        version="1.0.0",
        lifespan=lifespan,
    )

    # 1. Register Idempotency Shield Middleware (inner: runs with active tenant context)
    app.add_middleware(IdempotencyMiddleware)

    # 2. Register Multi-Tenancy & Context Extraction Middleware (outer: sets ContextVar)
    app.add_middleware(MultiTenancyContextMiddleware)

    # 3. Enable CORS (outermost: handles pre-flight OPTIONS and CORS headers)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 4. Register Global Standardized Error Envelope Handlers
    app.add_exception_handler(PlatformException, platform_exception_handler)
    app.add_exception_handler(StaleDataError, stale_data_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    # 4. Micro-Kernel Synchronous Route Discovery & Mounting
    kernel.discover()
    kernel.resolve_dependencies()
    kernel.load(app=app)

    # 4.1. Mount Sovereign FastMCP AI Agent Bridge
    from core.mcp_bridge.routes import router as mcp_router
    app.include_router(mcp_router, prefix="/api/v1/mcp")

    # 4.2. Mount Sovereign Dynamic UI Engine & View Registry
    from modules.base.ui_schema.routes import router as ui_router
    app.include_router(ui_router, prefix="/api/v1/ui", tags=["Dynamic UI Schema & View Engine"])


    # 5. Micro-Kernel Registry Diagnostics Endpoint
    @app.get("/api/v1/kernel/modules", tags=["Kernel Diagnostics"])
    async def get_kernel_modules() -> Dict[str, Any]:
        """Return registered modules, execution load order, and AI-enabled capabilities."""
        return {
            "status": "online",
            "total_modules": len(kernel.manifests),
            "load_order": kernel.load_order,
            "modules": kernel.list_modules(),
            "ai_enabled_count": len(kernel.get_ai_enabled_modules()),
        }

    # 6. System Health Check Endpoint
    @app.get("/health", tags=["System Diagnostics"])
    async def health_check() -> JSONResponse:
        """Asynchronous system health check verifying database, redis, and celery connectivity."""
        components: Dict[str, str] = {}
        all_healthy = True

        # Database Ping
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            components["database"] = "connected"
        except Exception as exc:
            components["database"] = f"error: {str(exc)}"
            all_healthy = False

        # Redis Ping
        try:
            r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
            await r.ping()
            await r.aclose()
            components["redis"] = "connected"
        except Exception as exc:
            components["redis"] = f"error: {str(exc)}"
            all_healthy = False

        # Celery Broker Connectivity
        try:
            r_celery = aioredis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=2)
            await r_celery.ping()
            await r_celery.aclose()
            components["celery_broker"] = "connected"
        except Exception as exc:
            components["celery_broker"] = f"error: {str(exc)}"
            all_healthy = False

        # Kernel Boot Status
        components["kernel"] = "booted" if kernel._booted else "ready"

        response_payload = {
            "status": "healthy" if all_healthy else "degraded",
            "components": components,
            "version": "1.0.0",
            "environment": settings.ENVIRONMENT,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        http_status = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(status_code=http_status, content=response_payload)

    # 7. Root Information Endpoint
    @app.get("/", tags=["System Diagnostics"])
    async def root_endpoint() -> Dict[str, Any]:
        """Root API platform status and documentation links."""
        return {
            "platform": "Sovereign Headless Backend Platform",
            "version": "1.0.0",
            "status": "online",
            "docs": "/docs",
            "health": "/health",
            "kernel_modules": "/api/v1/kernel/modules",
        }

    return app
