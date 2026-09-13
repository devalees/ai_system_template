"""Asynchronous in-process Event Bus with Redis Pub/Sub Bridge."""

import asyncio
import json
import logging
from typing import Callable, Coroutine, Dict, List, Any, Optional
from datetime import datetime, timezone
import redis.asyncio as aioredis
from core.config import settings

logger = logging.getLogger("sovereign.event_bus")

EventHandler = Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]


class EventBus:
    """High-performance event dispatcher coordinating in-process and distributed message pub/sub."""

    def __init__(self):
        self._subscribers: Dict[str, List[EventHandler]] = {}
        self._redis: Optional[aioredis.Redis] = None
        self._pubsub_task: Optional[asyncio.Task] = None
        self._running = False

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        """Register an asynchronous callback for a specific event pattern."""
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        if handler not in self._subscribers[event_name]:
            self._subscribers[event_name].append(handler)
            logger.debug(f"Registered subscriber for '{event_name}': {handler.__name__}")

    def on(self, event_name: str) -> Callable[[EventHandler], EventHandler]:
        """Decorator for subscribing to events."""
        def decorator(handler: EventHandler) -> EventHandler:
            self.subscribe(event_name, handler)
            return handler
        return decorator

    async def emit(self, event_name: str, payload: Dict[str, Any], broadcast_redis: bool = True) -> None:
        """Emit an event to all local subscribers and optionally broadcast across Redis Pub/Sub."""
        event_message = {
            "event": event_name,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # 1. Execute local in-process subscribers concurrently
        handlers = self._subscribers.get(event_name, [])
        # Also check wildcard handlers (e.g. "entity.*")
        if "*" in event_name or any("*" in k for k in self._subscribers):
            for pattern, pattern_handlers in self._subscribers.items():
                if pattern.endswith(".*") and event_name.startswith(pattern[:-2]):
                    handlers = handlers + [h for h in pattern_handlers if h not in handlers]

        if handlers:
            tasks = [asyncio.create_task(self._safe_execute(h, event_message)) for h in handlers]
            await asyncio.gather(*tasks, return_exceptions=True)

        # 2. Broadcast to Redis Pub/Sub for distributed workers & WebSocket gateways
        if broadcast_redis and settings.REDIS_URL:
            try:
                r = await self._get_redis()
                await r.publish("sovereign:events", json.dumps(event_message))
            except Exception as e:
                logger.warning(f"Failed broadcasting event '{event_name}' to Redis: {e}")

    publish = emit

    async def _safe_execute(self, handler: EventHandler, event_message: Dict[str, Any]) -> None:
        """Execute a single handler with error isolation."""
        try:
            await handler(event_message)
        except Exception as exc:
            logger.error(f"Error in event handler {handler.__name__} for {event_message.get('event')}: {exc}", exc_info=True)

    async def _get_redis(self) -> aioredis.Redis:
        """Lazily initialize Redis connection."""
        if self._redis is None:
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    async def close(self) -> None:
        """Cleanup Redis connections and subscriber tasks."""
        self._running = False
        if self._pubsub_task:
            self._pubsub_task.cancel()
        if self._redis:
            await self._redis.aclose()
            self._redis = None


# Singleton platform event bus
event_bus = EventBus()
