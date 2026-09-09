from django.apps import AppConfig

class IntegrationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.integration'
    verbose_name = 'AI Agent Integration'

    def ready(self):
        import apps.integration.signals

