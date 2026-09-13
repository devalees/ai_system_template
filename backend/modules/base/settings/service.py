"""Settings resolution service with multi-tenant Redis caching."""

import json
import uuid
import logging
from typing import Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from core.config import settings
from modules.base.settings.models import ModuleSettings

logger = logging.getLogger("sovereign.settings")


class SettingsService:
    """Service for resolving and updating module configuration with zero-downtime Redis caching."""

    @staticmethod
    def _cache_key(company_id: uuid.UUID, module_name: str) -> str:
        return f"sovereign:settings:{company_id}:{module_name}"

    @classmethod
    async def get_settings(
        cls,
        db: AsyncSession,
        module_name: str,
        company_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Fetch module settings for tenant company with Redis caching."""
        cache_key = cls._cache_key(company_id, module_name)

        # 1. Try Redis cache
        try:
            r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            cached = await r.get(cache_key)
            await r.aclose()
            if cached:
                return json.loads(cached)
        except Exception as exc:
            logger.debug(f"Redis cache miss/error for {cache_key}: {exc}")

        # 2. Database lookup
        stmt = select(ModuleSettings).where(
            ModuleSettings.company_id == company_id,
            ModuleSettings.module_name == module_name,
        )
        row = (await db.execute(stmt)).scalar_one_or_none()
        result_data = row.settings_data if row else {}

        # 3. Populate Redis cache
        try:
            r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            await r.set(cache_key, json.dumps(result_data), ex=3600)  # 1 hour TTL
            await r.aclose()
        except Exception:
            pass

        return result_data

    @classmethod
    async def update_settings(
        cls,
        db: AsyncSession,
        module_name: str,
        company_id: uuid.UUID,
        new_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Merge and persist updated settings into database and invalidate Redis cache."""
        stmt = select(ModuleSettings).where(
            ModuleSettings.company_id == company_id,
            ModuleSettings.module_name == module_name,
        )
        row = (await db.execute(stmt)).scalar_one_or_none()

        if row is None:
            row = ModuleSettings(
                company_id=company_id,
                module_name=module_name,
                settings_data=new_data,
            )
            db.add(row)
        else:
            # Merge dictionary
            merged = dict(row.settings_data or {})
            merged.update(new_data)
            row.settings_data = merged

        await db.commit()
        await db.refresh(row)

        # Invalidate Redis cache
        cache_key = cls._cache_key(company_id, module_name)
        try:
            r = aioredis.from_url(settings.REDIS_URL)
            await r.delete(cache_key)
            await r.aclose()
        except Exception:
            pass

        return row.settings_data
