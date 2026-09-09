"""
URL routing configuration for apps.audit REST API.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.audit.views import ActivityLogViewSet

app_name = "audit"

router = DefaultRouter()
router.register(r"logs", ActivityLogViewSet, basename="activity-log")

urlpatterns = [
    path("", include(router.urls)),
]
