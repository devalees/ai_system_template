"""
URL configuration for AI System Template.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
    path('admin/', admin.site.urls),
    path('api/', include('apps.integration.urls')),
    path('api/automation/', include('apps.automation.urls')),
]

