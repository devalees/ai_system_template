"""
Central Service & Action Registry for Automation Engine.

Maintains unified directory of:
1. hermes_agent: Autonomous Hermes Agent profiles (auto-discovered from engine)
2. internal_app: Python functions in Django apps (discovered via actions.py)
3. script_service: Standalone project scripts
4. external_webhook: Outbound HTTP webhook dispatchers
"""

import inspect
from typing import Any, Callable, Dict, List, Optional, Tuple
from django.apps import apps


CATEGORY_CHOICES = [
    ('hermes_agent', '🤖 Hermes Agent Profile'),
    ('internal_app', '🐍 Internal Django App Handler'),
    ('script_service', '📜 Script / System Service'),
    ('external_webhook', '🌐 Outbound Webhook / API'),
]


class ActionDefinition:
    """Represents a registered executable action or service."""

    def __init__(
        self,
        name: str,
        category: str,
        description: str = "",
        handler: Optional[Callable] = None,
        schema: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.category = category
        self.description = description
        self.handler = handler
        self.schema = schema or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "schema": self.schema,
            "has_handler": self.handler is not None,
        }


class ServiceRegistry:
    """Singleton registry coordinating actions, services, and dynamic model discovery."""

    _instance: Optional['ServiceRegistry'] = None
    _actions: Dict[str, ActionDefinition] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._actions = {}
        return cls._instance

    @classmethod
    def register(
        cls,
        name: str,
        category: str = "internal_app",
        description: str = "",
        handler: Optional[Callable] = None,
        schema: Optional[Dict[str, Any]] = None,
    ):
        """Registers an action definition into the global registry."""
        cls._actions[name] = ActionDefinition(
            name=name,
            category=category,
            description=description,
            handler=handler,
            schema=schema,
        )

    @classmethod
    def get_action(cls, name: str) -> Optional[ActionDefinition]:
        """Retrieves registered action definition by name."""
        # Check standard registry
        if name in cls._actions:
            return cls._actions[name]

        # Check if it matches a dynamic Hermes profile name
        hermes_actions = cls.get_hermes_profile_actions()
        if name in hermes_actions:
            return hermes_actions[name]

        return None

    @classmethod
    def get_hermes_profile_actions(cls) -> Dict[str, ActionDefinition]:
        """Dynamically queries Hermes profiles from discovery service."""
        dynamic_actions: Dict[str, ActionDefinition] = {}
        try:
            from apps.integration.services.hermes_discovery import HermesDiscoveryService
            profiles = HermesDiscoveryService.list_available_profiles()
            for p in profiles:
                action_name = f"hermes_profile:{p['name']}"
                desc = p.get('description') or f"Dispatches task/prompt to Hermes profile: {p['name']}"
                dynamic_actions[action_name] = ActionDefinition(
                    name=action_name,
                    category="hermes_agent",
                    description=desc,
                    handler=None,  # Handled dynamically via Hermes task dispatcher
                    schema={
                        "profile_name": p['name'],
                        "model": p.get('model', ''),
                        "role": p.get('role', ''),
                    }
                )
        except Exception:
            pass
        return dynamic_actions

    @classmethod
    def list_actions(cls, category: Optional[str] = None) -> List[ActionDefinition]:
        """Lists all actions, optionally filtered by category."""
        all_actions = dict(cls._actions)
        all_actions.update(cls.get_hermes_profile_actions())

        if category:
            return [a for a in all_actions.values() if a.category == category]
        return list(all_actions.values())

    @classmethod
    def get_action_choices(cls) -> List[Tuple[str, str]]:
        """Returns grouped choices list for Django model and form dropdowns."""
        all_actions = dict(cls._actions)
        all_actions.update(cls.get_hermes_profile_actions())

        category_labels = dict(CATEGORY_CHOICES)
        grouped: Dict[str, List[Tuple[str, str]]] = {cat: [] for cat, _ in CATEGORY_CHOICES}

        for action in all_actions.values():
            cat = action.category if action.category in grouped else 'internal_app'
            label = f"{action.name} — {action.description[:60]}" if action.description else action.name
            grouped[cat].append((action.name, label))

        result = []
        for cat, items in grouped.items():
            if items:
                result.append((category_labels.get(cat, cat), sorted(items, key=lambda x: x[0])))
        return result

    @classmethod
    def get_registered_model_choices(cls) -> List[Tuple[str, str]]:
        """
        Dynamically enumerates models across all installed Django apps.
        Groups them by App verbose_name / label.
        """
        EXCLUDED_APPS = {'admin', 'contenttypes', 'sessions', 'messages', 'staticfiles'}
        grouped: Dict[str, List[Tuple[str, str]]] = {}

        for app_config in apps.get_app_configs():
            if app_config.label in EXCLUDED_APPS:
                continue

            app_models = []
            for model in app_config.get_models():
                model_identifier = f"{app_config.label}.{model.__name__}"
                verbose = model._meta.verbose_name.title()
                app_models.append((model_identifier, f"{verbose} ({model_identifier})"))

            if app_models:
                grouped[app_config.verbose_name] = sorted(app_models, key=lambda x: x[1])

        result = []
        for app_title in sorted(grouped.keys()):
            result.append((app_title, grouped[app_title]))
        return result


def register_action(
    name: str,
    category: str = "internal_app",
    description: str = "",
    schema: Optional[Dict[str, Any]] = None,
):
    """
    Decorator for registering action handler functions.
    Usage:
        @register_action(name="provision_hermes_profile", category="hermes_agent", description="...")
        def provision_profile(context):
            ...
    """
    def decorator(fn: Callable):
        doc = description or inspect.getdoc(fn) or ""
        ServiceRegistry.register(
            name=name,
            category=category,
            description=doc.strip().splitlines()[0] if doc else "",
            handler=fn,
            schema=schema,
        )
        return fn
    return decorator
