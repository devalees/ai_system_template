"""
URL Router Configuration for Universal Document & Media Management.
"""

from rest_framework.routers import DefaultRouter

from apps.media.views import DocumentViewSet

router = DefaultRouter()
router.register(r"documents", DocumentViewSet, basename="documents")

urlpatterns = router.urls
