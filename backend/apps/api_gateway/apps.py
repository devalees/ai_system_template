"""
App configuration for Developer API Gateway, Scoped Keys & Inbound Webhooks (apps.api_gateway).
"""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ApiGatewayConfig(AppConfig):
    """AppConfig registering api_gateway app."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.api_gateway"
    verbose_name = _("Developer API Gateway & Inbound Webhooks")
