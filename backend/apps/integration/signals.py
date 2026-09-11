"""
Django Signals for Integration App.

Automatically maintains 1-to-1 User Profile lifecycle across all
User creations (admin, seed command, API endpoints).
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    Ensures every Django auth.User has an attached Profile.
    If username starts with 'bot_', automatically configures as an AI Agent service account.
    """
    if created:
        is_bot = instance.username.startswith("bot_")
        profile_slug = instance.username.removeprefix("bot_") if is_bot else ""
        Profile.objects.get_or_create(
            user=instance,
            defaults={
                "display_name": instance.get_full_name() or instance.username,
                "name": profile_slug or instance.username,
                "hermes_profile_name": profile_slug,
                "is_agent": is_bot,
                "user_type": "agent" if is_bot else ("human" if instance.is_staff else "client"),
            }
        )
    else:
        # If user instance exists but has no profile, create it defensively
        if not hasattr(instance, "profile") or instance.profile is None:
            Profile.objects.get_or_create(user=instance)


@receiver(post_save, sender=Profile)
def sync_profile_on_save(sender, instance, **kwargs):
    """
    Synchronizes profile runtime .env and config when agent profile is updated.
    """
    if instance.is_agent:
        from apps.integration.services.credential_sync import sync_profile_runtime_env
        try:
            sync_profile_runtime_env(instance)
        except Exception:
            pass


from django.db.models.signals import post_delete
from .models import ProviderCredential
from apps.core.models import AppSettingValue


@receiver([post_save, post_delete], sender=ProviderCredential)
def sync_credentials_on_change(sender, instance, **kwargs):
    """
    Synchronizes runtime credentials across Hermes .env files whenever
    a ProviderCredential is created, updated, or removed.
    """
    from apps.integration.services.credential_sync import sync_hermes_runtime_credentials
    try:
        sync_hermes_runtime_credentials()
    except Exception:
        pass


@receiver(post_save, sender=AppSettingValue)
def sync_credentials_on_app_setting_change(sender, instance, **kwargs):
    """
    Synchronizes runtime credentials when an integration setting (API key) is changed in Settings Hub.
    """
    if instance.app_label == "integration" and instance.key.endswith("_API_KEY"):
        from apps.integration.services.credential_sync import sync_hermes_runtime_credentials
        try:
            sync_hermes_runtime_credentials()
        except Exception:
            pass

