"""
URL Routing for apps.automation.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AutomationRuleViewSet, AutomationLogViewSet, list_registered_services, model_introspection

router = DefaultRouter()
router.register(r'rules', AutomationRuleViewSet, basename='automation-rule')
router.register(r'logs', AutomationLogViewSet, basename='automation-log')

urlpatterns = [
    path('services/', list_registered_services, name='automation-services-list'),
    path('introspection/', model_introspection, name='automation-model-introspection'),
    path('', include(router.urls)),
]
