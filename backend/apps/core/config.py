"""
Runtime Configuration & Settings Resolution Service.

Provides unified, fast, dual-layer settings access:
1. Sub-millisecond Redis Cache
2. PostgreSQL `AppSettingValue` database store
3. Django `settings.py` / `.env` fallback
"""

import logging
from typing import Any, Dict, Optional
from django.conf import settings as django_settings
from django.core.cache import cache

from apps.core.models import AppSettingValue
from apps.core.settings_registry import settings_registry

logger = logging.getLogger(__name__)

CACHE_TTL_DATABASE = 86400  # 24 hours for explicitly stored values
CACHE_TTL_DEFAULT = 3600    # 1 hour for resolved defaults


def _split_setting_path(setting_path: str) -> tuple[str, str]:
    """Split 'app_label.KEY' into ('app_label', 'KEY')."""
    if "." in setting_path:
        parts = setting_path.split(".", 1)
        return parts[0].strip().lower(), parts[1].strip()
    return "general", setting_path.strip()


def get_setting(setting_path: str, default: Any = None) -> Any:
    """
    Retrieve a configuration setting using high-speed dual-layer resolution.

    Priority Chain:
    1. Redis Cache (`core:setting:<app_label>:<key>`)
    2. Database (`AppSettingValue`)
    3. Registered Setting Default (`Setting.default`)
    4. Django Settings (`settings.py` / `.env`)
    5. Caller-provided `default`

    Args:
        setting_path: Dot-separated setting path (e.g. 'automation.HERMES_TIMEOUT')
        default: Fallback value if setting is completely undefined

    Returns:
        Typed setting value
    """
    app_label, key = _split_setting_path(setting_path)
    cache_key = AppSettingValue.get_cache_key(app_label, key)

    # 1. Sub-millisecond Redis Cache lookup
    cached_val = cache.get(cache_key)
    if cached_val is not None:
        return cached_val

    # 2. Database lookup
    setting_def = settings_registry.get_setting_definition(app_label, key)
    db_record = AppSettingValue.objects.filter(app_label=app_label, key=key).first()

    if db_record is not None:
        if setting_def:
            typed_val = setting_def.to_python(db_record.raw_value)
        else:
            # Fallback type coercion if definition not yet loaded
            if db_record.data_type == "int":
                typed_val = int(db_record.raw_value)
            elif db_record.data_type == "float":
                typed_val = float(db_record.raw_value)
            elif db_record.data_type == "bool":
                typed_val = db_record.raw_value.lower() in ("true", "1", "yes", "on")
            else:
                typed_val = db_record.raw_value

        cache.set(cache_key, typed_val, timeout=CACHE_TTL_DATABASE)
        return typed_val

    # 3. Registered definition default
    resolved_val = None
    if setting_def is not None and setting_def.default is not None:
        resolved_val = setting_def.default

    # 4. Django settings.py or .env fallback
    if resolved_val is None:
        env_candidates = [
            f"{app_label.upper()}_{key.upper()}",
            key.upper(),
            key,
        ]
        for candidate in env_candidates:
            if hasattr(django_settings, candidate):
                resolved_val = getattr(django_settings, candidate)
                break

    # 5. Caller-provided default
    if resolved_val is None:
        resolved_val = default

    # Cache the resolved default to avoid repetitive database misses
    if resolved_val is not None:
        cache.set(cache_key, resolved_val, timeout=CACHE_TTL_DEFAULT)

    return resolved_val


def set_setting(setting_path: str, value: Any) -> Any:
    """
    Persist a setting to the database and update Redis cache immediately.

    Args:
        setting_path: Dot-separated setting path (e.g. 'automation.HERMES_TIMEOUT')
        value: New value to store

    Returns:
        Typed, validated stored value
    """
    app_label, key = _split_setting_path(setting_path)
    setting_def = settings_registry.get_setting_definition(app_label, key)

    if setting_def:
        validated_val = setting_def.validate(value)
        raw_val = setting_def.to_storage(validated_val)
        data_type = setting_def.data_type
    else:
        validated_val = value
        raw_val = str(value)
        data_type = "str"

    obj, _ = AppSettingValue.objects.update_or_create(
        app_label=app_label,
        key=key,
        defaults={
            "raw_value": raw_val,
            "data_type": data_type,
        },
    )

    # Populate cache directly with validated typed value
    cache_key = obj.get_cache_key(app_label, key)
    cache.set(cache_key, validated_val, timeout=CACHE_TTL_DATABASE)

    return validated_val


def get_all_settings_for_app(app_label: str) -> Dict[str, Any]:
    """
    Retrieve all resolved settings for an application group.

    Returns:
        Dictionary mapping {key: typed_value}
    """
    group = settings_registry.get_group(app_label)
    if not group:
        return {}

    result = {}
    for key in group.settings:
        result[key] = get_setting(f"{app_label}.{key}")
    return result
