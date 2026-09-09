"""
URL routing configuration for Dynamic Visual Reporting Engine API.
"""

from rest_framework.routers import DefaultRouter

from apps.reports.views import ReportExecutionLogViewSet, ReportTemplateViewSet

router = DefaultRouter()
router.register(r"templates", ReportTemplateViewSet, basename="report-template")
router.register(r"logs", ReportExecutionLogViewSet, basename="report-log")

urlpatterns = router.urls
