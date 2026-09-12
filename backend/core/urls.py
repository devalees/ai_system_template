"""
URL configuration for AI System Template.
"""

from django.contrib import admin
from django.urls import path, include
from apps.core.views import CustomObtainAuthToken, CurrentUserView, AppSettingsView

urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
    path('admin/', admin.site.urls),
    path('api/token-auth/', CustomObtainAuthToken.as_view(), name='api-token-auth'),
    path('api/auth/token/', CustomObtainAuthToken.as_view(), name='api-auth-token'),
    path('api/auth/me/', CurrentUserView.as_view(), name='api-auth-me'),
    path('api/settings/', AppSettingsView.as_view(), name='api-settings'),
    path('api/', include('apps.integration.urls')),
    path('api/automation/', include('apps.automation.urls')),
    path('api/v1/', include('apps.tenants.urls')),
    path('api/v1/audit/', include('apps.audit.urls')),
    path('api/v1/notifications/', include('apps.notifications.urls')),
    path('api/v1/media/', include('apps.media.urls')),
    path('api/v1/clients/', include('apps.clients.urls')),
    path('api/v1/gateway/', include('apps.api_gateway.urls')),
    path('api/v1/reports/', include('apps.reports.urls')),
]


