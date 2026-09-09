"""
URL Configuration for Universal Notifications Engine.
"""

from rest_framework.routers import DefaultRouter

from apps.notifications.views import (
    NotificationPreferenceViewSet,
    NotificationViewSet,
)

router = DefaultRouter()
router.register(r"preferences", NotificationPreferenceViewSet, basename="notification-preferences")
router.register(r"", NotificationViewSet, basename="notifications")

urlpatterns = router.urls
