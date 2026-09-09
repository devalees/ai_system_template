"""
URL routing for apps.meta_engine REST API Gateway and App Store.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    EntitySchemaIntrospectionView,
    SystemModuleViewSet,
    UniversalEntityGatewayView,
)

router = DefaultRouter()
router.register(r"modules", SystemModuleViewSet, basename="system-modules")

urlpatterns = [
    path("", include(router.urls)),
    path("entities/<str:model_slug>/schema/", EntitySchemaIntrospectionView.as_view(), name="entity-schema"),
    path("entities/<str:model_slug>/", UniversalEntityGatewayView.as_view(), name="entity-list-create"),
    path("entities/<str:model_slug>/<str:pk>/", UniversalEntityGatewayView.as_view(), name="entity-detail"),
]
