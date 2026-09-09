"""
Modular Application Settings Registry.

Provides an Odoo-style declarative configuration registry where any installed
Django app can declare and type-validate its configuration parameters.
"""

import importlib
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from django.apps import apps
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.core.crypto import decrypt_secret, encrypt_secret

logger = logging.getLogger(__name__)

SUPPORTED_TYPES = {"str", "int", "float", "bool", "choice", "secret", "json"}


class Setting:
    """
    Descriptor and validator for a single typed configuration parameter.
    """

    def __init__(
        self,
        data_type: str,
        default: Any = None,
        verbose_name: Optional[str] = None,
        help_text: Optional[str] = None,
        choices: Optional[List[Tuple[Any, str]]] = None,
        order: int = 10,
        is_public: bool = False,
        validators: Optional[List[Callable[[Any], None]]] = None,
    ):
        if data_type not in SUPPORTED_TYPES:
            raise ValueError(f"Unsupported setting data_type '{data_type}'. Must be one of {SUPPORTED_TYPES}")

        self.data_type = data_type
        self.default = default
        self.verbose_name = verbose_name or ""
        self.help_text = help_text or ""
        self.choices = choices or []
        self.order = order
        self.is_public = is_public
        self.validators = validators or []
        self.name: Optional[str] = None

    def validate(self, value: Any) -> Any:
        """Validate value against data_type constraints, choices, and custom validators."""
        if value is None:
            return self.default

        # Type Coercion & Verification
        try:
            if self.data_type == "int":
                val = int(value)
            elif self.data_type == "float":
                val = float(value)
            elif self.data_type == "bool":
                if isinstance(value, str):
                    val = value.strip().lower() in ("true", "1", "yes", "on")
                else:
                    val = bool(value)
            elif self.data_type == "str":
                val = str(value)
            elif self.data_type == "secret":
                val = str(value)
            elif self.data_type == "choice":
                val = str(value)
                valid_choices = [str(c[0]) for c in self.choices]
                if val not in valid_choices:
                    raise ValidationError(
                        _(f"Value '{val}' is not a valid choice. Allowed: {valid_choices}")
                    )
            elif self.data_type == "json":
                if isinstance(value, str):
                    val = json.loads(value)
                else:
                    val = value
            else:
                val = value
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ValidationError(_(f"Invalid value for type '{self.data_type}': {exc}"))

        # Run custom validators
        for validator in self.validators:
            validator(val)

        return val

    def to_python(self, raw_value: Any) -> Any:
        """Convert a raw stored database string/value into its rich Python type."""
        if raw_value is None:
            return self.default

        if self.data_type == "secret":
            return decrypt_secret(str(raw_value))
        elif self.data_type == "bool":
            if isinstance(raw_value, str):
                return raw_value.strip().lower() in ("true", "1", "yes", "on")
            return bool(raw_value)
        elif self.data_type == "int":
            return int(raw_value)
        elif self.data_type == "float":
            return float(raw_value)
        elif self.data_type == "json":
            if isinstance(raw_value, str):
                try:
                    return json.loads(raw_value)
                except Exception:
                    return self.default
            return raw_value
        return str(raw_value)

    def to_storage(self, python_value: Any) -> str:
        """Convert a python value into a string representation for database storage."""
        if python_value is None:
            return ""

        if self.data_type == "secret":
            return encrypt_secret(str(python_value))
        elif self.data_type == "json":
            if isinstance(python_value, str):
                return python_value
            return json.dumps(python_value)
        elif self.data_type == "bool":
            return "true" if python_value else "false"
        return str(python_value)


class SettingsGroup:
    """Represents a categorized group of settings belonging to an application."""

    def __init__(
        self,
        app_label: str,
        verbose_name: Optional[str] = None,
        icon: str = "⚙️",
        order: int = 100,
    ):
        self.app_label = app_label
        self.verbose_name = verbose_name or app_label.title()
        self.icon = icon
        self.order = order
        self.settings: Dict[str, Setting] = {}

    def add_setting(self, key: str, setting: Setting):
        """Add a setting definition to this group."""
        setting.name = key
        if not setting.verbose_name:
            setting.verbose_name = key.replace("_", " ").title()
        self.settings[key] = setting

    def get_setting(self, key: str) -> Optional[Setting]:
        """Retrieve setting definition by key."""
        return self.settings.get(key)


class SettingsRegistry:
    """Central in-memory registry holding all modular application setting definitions."""

    def __init__(self):
        self._groups: Dict[str, SettingsGroup] = {}
        self._discovered: bool = False

    def register_group(
        self,
        app_label: str,
        verbose_name: Optional[str] = None,
        icon: str = "⚙️",
        order: int = 100,
    ) -> SettingsGroup:
        """Create or retrieve a settings group."""
        if app_label not in self._groups:
            self._groups[app_label] = SettingsGroup(
                app_label=app_label,
                verbose_name=verbose_name,
                icon=icon,
                order=order,
            )
        else:
            if verbose_name:
                self._groups[app_label].verbose_name = verbose_name
            if icon:
                self._groups[app_label].icon = icon
            if order:
                self._groups[app_label].order = order
        return self._groups[app_label]

    def register_setting(self, app_label: str, key: str, setting: Setting):
        """Register a single setting under an app group."""
        group = self.register_group(app_label)
        group.add_setting(key, setting)

    def get_group(self, app_label: str) -> Optional[SettingsGroup]:
        """Get group definition by app label."""
        self.ensure_discovered()
        return self._groups.get(app_label)

    def get_setting_definition(self, app_label: str, key: str) -> Optional[Setting]:
        """Get individual setting definition."""
        self.ensure_discovered()
        group = self._groups.get(app_label)
        if group:
            return group.get_setting(key)
        return None

    def get_all_groups(self) -> List[SettingsGroup]:
        """Return all registered groups sorted by order."""
        self.ensure_discovered()
        return sorted(self._groups.values(), key=lambda g: g.order)

    def ensure_discovered(self):
        """Zero-touch discovery importing `<app>.conf` across installed apps."""
        if self._discovered:
            return
        self._discovered = True
        for app_config in apps.get_app_configs():
            # Try importing app.conf
            module_name = f"{app_config.name}.conf"
            try:
                importlib.import_module(module_name)
            except ModuleNotFoundError:
                pass
            except Exception as e:
                logger.warning(f"Error loading {module_name}: {e}")


# Singleton instance
settings_registry = SettingsRegistry()


def register_settings_group(
    app_label: str,
    verbose_name: Optional[str] = None,
    icon: str = "⚙️",
    order: int = 100,
):
    """
    Class decorator to declare settings groups in an application's `conf.py`.

    Usage:
        @register_settings_group('automation', verbose_name='Automation', icon='⚡')
        class AutomationSettings:
            TIMEOUT = Setting(data_type='int', default=120)
    """
    def decorator(cls):
        group = settings_registry.register_group(
            app_label=app_label,
            verbose_name=verbose_name,
            icon=icon,
            order=order,
        )
        for attr_name, attr_val in vars(cls).items():
            if isinstance(attr_val, Setting):
                group.add_setting(attr_name, attr_val)
        return cls
    return decorator
