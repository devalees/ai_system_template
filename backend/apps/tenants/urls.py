"""
URL routing for Multi-Tenancy REST APIs.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.tenants.views import OrganizationViewSet, InvitationAcceptAPIView

app_name = "tenants"

router = DefaultRouter()
router.register(r"organizations", OrganizationViewSet, basename="organization")

urlpatterns = [
    path("", include(router.urls)),
    path("invitations/accept/", InvitationAcceptAPIView.as_view(), name="invitation_accept_post"),
    path("invitations/<str:token>/accept/", InvitationAcceptAPIView.as_view(), name="invitation_accept"),
]
