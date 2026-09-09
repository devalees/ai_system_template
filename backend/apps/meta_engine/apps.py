from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class MetaEngineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.meta_engine"
    verbose_name = _("Metadata Engine & Declarative Runtime")

    def ready(self):
        """
        Bootstrap the dynamic models and register application signals.
        """
        try:
            import apps.meta_engine.signals  # noqa
        except Exception:
            pass
