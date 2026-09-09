"""
Targeted Model Lifecycle Signals Bridge for Automation Engine.

Connects signals specifically to models registered in active AutomationRules,
avoiding global signal overhead and preventing migration interference.
"""

from typing import Type
from django.apps import apps
from django.db.models import Model
from django.db.models.signals import pre_save, post_save, post_delete, post_migrate
from django.dispatch import receiver


_CONNECTED_MODELS = set()


def automation_pre_save_handler(sender: Type[Model], instance: Model, raw: bool = False, **kwargs):
    """Caches previous values before an update to allow state transition evaluations."""
    if raw or not hasattr(instance, 'pk') or instance.pk is None:
        return
    try:
        old_record = sender.objects.filter(pk=instance.pk).values().first()
        instance._automation_old_values = old_record or {}
    except Exception:
        instance._automation_old_values = {}


def automation_post_save_handler(sender: Type[Model], instance: Model, created: bool, raw: bool = False, **kwargs):
    """Specific handler connected to monitored models."""
    if raw or not hasattr(instance, 'pk') or instance.pk is None:
        return

    from .engine import AutomationEngine
    event_type = 'created' if created else 'updated'
    old_values = getattr(instance, '_automation_old_values', {})
    try:
        AutomationEngine.dispatch_model_event(instance, event_type, old_values=old_values)
    except Exception:
        pass


def automation_post_delete_handler(sender: Type[Model], instance: Model, **kwargs):
    """Specific handler connected to monitored models for deletion."""
    if not hasattr(instance, 'pk'):
        return

    from .engine import AutomationEngine
    try:
        AutomationEngine.dispatch_model_event(instance, 'deleted')
    except Exception:
        pass


def connect_model_signals(model_class: Type[Model]):
    """Connects pre_save, post_save, and post_delete to a specific model class idempotently."""
    global _CONNECTED_MODELS
    if model_class in _CONNECTED_MODELS:
        return

    pre_save.connect(automation_pre_save_handler, sender=model_class, weak=False)
    post_save.connect(automation_post_save_handler, sender=model_class, weak=False)
    post_delete.connect(automation_post_delete_handler, sender=model_class, weak=False)
    _CONNECTED_MODELS.add(model_class)


def bootstrap_core_signals():
    """Connects foundation template models at boot without database queries."""
    for model_str in ['auth.User', 'integration.Profile', 'integration.AgentTask']:
        try:
            model_cls = apps.get_model(model_str)
            if model_cls:
                connect_model_signals(model_cls)
        except Exception:
            pass


def sync_automation_signals():
    """
    Scans active AutomationRules and connects signals for all target models.
    Called post-migration and on rule creation/updates.
    """
    bootstrap_core_signals()
    try:
        from .models import AutomationRule
        target_models = (
            AutomationRule.objects.filter(is_active=True, trigger_type='model_event')
            .values_list('target_model', flat=True)
            .distinct()
        )

        for model_str in target_models:
            if not model_str or '.' not in model_str:
                continue
            try:
                model_cls = apps.get_model(model_str)
                if model_cls:
                    connect_model_signals(model_cls)
            except (LookupError, ValueError):
                pass
    except Exception:
        pass


@receiver(post_migrate)
def on_post_migrate_sync_signals(sender, **kwargs):
    """Ensures signal listeners are attached after migrations run."""
    sync_automation_signals()
