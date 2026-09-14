"""Settings resolution service with multi-tenant Redis caching and typed schema registry."""

import json
import uuid
import logging
from enum import Enum
from typing import Dict, Any, List, Optional, Type
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from core.config import settings
from modules.base.settings.models import ModuleSettings
from modules.base.settings.schemas import SettingFieldMeta, SettingOption

logger = logging.getLogger("sovereign.settings")


class SettingsService:
    """Service for resolving and updating module configuration with zero-downtime Redis caching."""

    _registry: Dict[str, Type[BaseModel]] = {}

    @classmethod
    def register_module_settings(cls, module_name: str, schema_cls: Type[BaseModel]) -> None:
        """Register a typed Pydantic settings schema for a specific module namespace."""
        cls._registry[module_name] = schema_cls
        logger.info(f"Registered settings schema for module '{module_name}' ({schema_cls.__name__})")

    @classmethod
    def get_registered_schema(cls, module_name: str) -> Optional[Type[BaseModel]]:
        """Return registered Pydantic settings schema class for module if exists."""
        return cls._registry.get(module_name)

    @classmethod
    def get_module_schema(cls, module_name: str) -> List[SettingFieldMeta]:
        """Extract self-describing field metadata from registered settings schema."""
        schema_cls = cls._registry.get(module_name)
        if not schema_cls:
            return []

        fields: List[SettingFieldMeta] = []
        for name, field in schema_cls.model_fields.items():
            title = field.title or name.replace("_", " ").title()
            desc = field.description or ""
            annotation = field.annotation
            extra = field.json_schema_extra or {}

            options = None
            if isinstance(extra, dict) and "options" in extra:
                field_type = "select"
                raw_opts = extra["options"]
                options = [
                    SettingOption(value=o["value"], label=o["label"]) if isinstance(o, dict) else SettingOption(value=o, label=str(o))
                    for o in raw_opts
                ]
            elif isinstance(annotation, type) and issubclass(annotation, Enum):
                field_type = "select"
                options = [
                    SettingOption(value=e.value, label=e.name.replace("_", " ").title())
                    for e in annotation
                ]
            elif annotation is bool or annotation == bool:
                field_type = "boolean"
            elif annotation is int or annotation == int:
                field_type = "integer"
            elif annotation is float or annotation == float:
                field_type = "float"
            else:
                field_type = "string"

            category = extra.get("category", "General") if isinstance(extra, dict) else "General"
            default_val = field.default if field.default != ... else None

            fields.append(SettingFieldMeta(
                key=name,
                label=title,
                description=desc,
                type=field_type,
                default=default_val,
                options=options,
                category=category,
            ))
        return fields

    @staticmethod
    def _cache_key(company_id: uuid.UUID, module_name: str) -> str:
        return f"sovereign:settings:{company_id}:{module_name}"

    @classmethod
    def get_default_settings(cls, module_name: str) -> Dict[str, Any]:
        """Return registered defaults for a module."""
        schema_cls = cls._registry.get(module_name)
        if schema_cls:
            try:
                return schema_cls().model_dump()
            except Exception:
                pass
        return {}

    @classmethod
    async def get_settings(
        cls,
        db: AsyncSession,
        module_name: str,
        company_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Fetch module settings for tenant company with transparent default fallback and Redis caching."""
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
        stored_data = row.settings_data if row and row.settings_data else {}

        # 3. Merge with registered defaults
        defaults = cls.get_default_settings(module_name)
        merged = {**defaults, **stored_data}

        # 4. Validate through registered schema if available
        schema_cls = cls._registry.get(module_name)
        if schema_cls:
            try:
                validated = schema_cls.model_validate(merged)
                result_data = validated.model_dump()
            except Exception as e:
                logger.warning(f"Settings validation failed for {module_name}, using raw merged: {e}")
                result_data = merged
        else:
            result_data = merged

        # 5. Populate Redis cache
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
        """Validate, merge, and persist updated settings into database and invalidate Redis cache."""
        # Validate against schema if registered
        schema_cls = cls._registry.get(module_name)
        current = await cls.get_settings(db, module_name, company_id)
        merged = {**current, **new_data}

        if schema_cls:
            validated = schema_cls.model_validate(merged)
            to_save = validated.model_dump()
        else:
            to_save = merged

        stmt = select(ModuleSettings).where(
            ModuleSettings.company_id == company_id,
            ModuleSettings.module_name == module_name,
        )
        row = (await db.execute(stmt)).scalar_one_or_none()

        if row is None:
            row = ModuleSettings(
                company_id=company_id,
                module_name=module_name,
                settings_data=to_save,
            )
            db.add(row)
        else:
            row.settings_data = to_save

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

