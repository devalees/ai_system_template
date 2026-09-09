from django.apps import AppConfig
from django.utils.module_loading import autodiscover_modules


class AutomationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.automation'
    verbose_name = 'Automation & Orchestration'

    def ready(self):
        """
        Bootstrap actions discovery and model signals on Django startup.
        """
        # Auto-discover actions.py in all installed apps
        autodiscover_modules('actions')

        # Connect targeted signal listeners without database queries
        try:
            from .signals import bootstrap_core_signals
            bootstrap_core_signals()
        except Exception:
            pass
