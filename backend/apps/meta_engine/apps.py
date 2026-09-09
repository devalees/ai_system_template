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

        try:
            from django.db.models.signals import post_migrate

            def _on_post_migrate(**kwargs):
                from apps.meta_engine.model_factory import DynamicModelFactory
                DynamicModelFactory.load_all_active_models()

            post_migrate.connect(_on_post_migrate, sender=self)
        except Exception:
            pass
