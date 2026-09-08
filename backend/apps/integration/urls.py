from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    health_check,
    agent_handshake,
    list_handshake_logs,
    ping_hermes_gateway,
    AgentTaskViewSet,
)

router = DefaultRouter()
router.register(r'tasks', AgentTaskViewSet, basename='agent-task')

urlpatterns = [
    path('health/', health_check, name='api-health'),
    path('handshake/', agent_handshake, name='api-handshake'),
    path('handshake/logs/', list_handshake_logs, name='api-handshake-logs'),
    path('ping-hermes/', ping_hermes_gateway, name='api-ping-hermes'),
    path('', include(router.urls)),
]
