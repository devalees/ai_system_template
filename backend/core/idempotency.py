"""Idempotency Shield Middleware ensuring zero-duplicate side effects for mutating API requests."""

import json
import logging
from datetime import datetime, timezone
from typing import Set, Optional
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from fastapi import status
import redis.asyncio as aioredis

from core.config import settings
from core.context import get_active_company_id

logger = logging.getLogger("sovereign.idempotency")

MUTATING_METHODS: Set[str] = {"POST", "PUT", "PATCH", "DELETE"}
DEFAULT_IDEMPOTENCY_TTL: int = 86400  # 24 hours
IN_PROGRESS_LOCK_TTL: int = 60  # 60 seconds distributed in-flight lock


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Middleware intercepting Idempotency-Key headers on mutating HTTP requests.
    
    Guarantees:
    1. Distributed locking preventing concurrent parallel duplicate execution (409 IDEMPOTENCY_IN_PROGRESS).
    2. Caching of successful responses for 24 hours in Redis (X-Idempotency-Status: HIT).
    3. Automatic key release on 5xx server failures so clients can retry safely.
    4. Multi-tenant isolation by namespacing keys per company_id.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in MUTATING_METHODS:
            return await call_next(request)

        idempotency_key = (
            request.headers.get("idempotency-key")
            or request.headers.get("x-idempotency-key")
        )

        if not idempotency_key or not idempotency_key.strip():
            return await call_next(request)

        idempotency_key = idempotency_key.strip()
        company_id = str(
            get_active_company_id()
            or request.headers.get("x-company-id")
            or "global"
        )
        redis_key = f"sovereign:idempotency:{company_id}:{idempotency_key}"

        r: Optional[aioredis.Redis] = None
        try:
            r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            cached_data = await r.get(redis_key)
            if cached_data:
                payload = json.loads(cached_data)
                req_status = payload.get("status")

                if req_status == "in_progress":
                    await r.aclose()
                    return JSONResponse(
                        status_code=status.HTTP_409_CONFLICT,
                        content={
                            "error": {
                                "code": "IDEMPOTENCY_IN_PROGRESS",
                                "message": f"A request with Idempotency-Key '{idempotency_key}' is currently being processed.",
                                "resolution_hint": "Please wait for the initial request to complete before checking results.",
                                "details": {"idempotency_key": idempotency_key},
                            },
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                        headers={
                            "X-Idempotency-Status": "IN_PROGRESS",
                            "X-Idempotency-Key": idempotency_key,
                        },
                    )

                if req_status == "completed":
                    await r.aclose()
                    cached_headers = payload.get("headers", {})
                    cached_headers["X-Idempotency-Status"] = "HIT"
                    cached_headers["X-Idempotency-Key"] = idempotency_key
                    return Response(
                        content=payload.get("body", ""),
                        status_code=payload.get("status_code", 200),
                        media_type=payload.get("media_type", "application/json"),
                        headers=cached_headers,
                    )

            # Atomically acquire in-progress distributed lock
            in_progress_payload = json.dumps({
                "status": "in_progress",
                "started_at": datetime.now(timezone.utc).isoformat(),
            })
            acquired = await r.set(redis_key, in_progress_payload, nx=True, ex=IN_PROGRESS_LOCK_TTL)
            if not acquired:
                await r.aclose()
                return JSONResponse(
                    status_code=status.HTTP_409_CONFLICT,
                    content={
                        "error": {
                            "code": "IDEMPOTENCY_IN_PROGRESS",
                            "message": f"A request with Idempotency-Key '{idempotency_key}' is currently being processed.",
                            "resolution_hint": "Please wait for the initial request to complete.",
                            "details": {"idempotency_key": idempotency_key},
                        },
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    headers={
                        "X-Idempotency-Status": "IN_PROGRESS",
                        "X-Idempotency-Key": idempotency_key,
                    },
                )

        except Exception as exc:
            logger.warning(f"Idempotency Redis check bypassed due to error: {exc}")
            if r:
                try:
                    await r.aclose()
                except Exception:
                    pass
                r = None

        # Execute downstream request pipeline
        response = await call_next(request)

        # Intercept and buffer streaming body for caching
        response_body = [chunk async for chunk in response.body_iterator]
        full_body_bytes = b"".join(response_body)

        async def async_iter():
            yield full_body_bytes

        response.body_iterator = async_iter()

        # Cache or release lock in Redis
        if r is not None:
            try:
                if response.status_code < 500:
                    body_text = full_body_bytes.decode("utf-8", errors="replace")
                    clean_headers = {
                        k: v for k, v in response.headers.items()
                        if k.lower() not in ("content-length", "set-cookie")
                    }
                    completed_payload = json.dumps({
                        "status": "completed",
                        "status_code": response.status_code,
                        "body": body_text,
                        "media_type": response.media_type,
                        "headers": clean_headers,
                    })
                    await r.set(redis_key, completed_payload, ex=DEFAULT_IDEMPOTENCY_TTL)
                    response.headers["X-Idempotency-Status"] = "STORED"
                    response.headers["X-Idempotency-Key"] = idempotency_key
                else:
                    # On server error, release key so client can retry
                    await r.delete(redis_key)
            except Exception as exc:
                logger.warning(f"Failed to persist idempotency response in Redis: {exc}")
            finally:
                await r.aclose()

        return response
