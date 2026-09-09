"""
DRF ViewSets and Endpoints for Universal Notifications Engine.

Provides:
- NotificationViewSet: User inbox listing, filtering, mark-read, mark-all-read, and unread-count endpoints.
- NotificationPreferenceViewSet: Retrieval and update endpoints for user notification preferences.
"""

from django.core.cache import cache
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.notifications.dispatcher import NotificationDispatcher
from apps.notifications.models import Notification, NotificationPreference
from apps.notifications.serializers import (
    NotificationPreferenceSerializer,
    NotificationSerializer,
)
from apps.notifications.signals import get_unread_cache_key


class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user inbox notifications.
    Operations are strictly scoped to the authenticated requesting user.
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filter notifications by requesting user recipient and active tenant context."""
        user = self.request.user
        qs = Notification.objects.filter(recipient=user)

        # Filter by tenant organization if present in context
        org = getattr(self.request, "tenant", None)
        if org:
            qs = qs.filter(organization=org)

        # Optional query filters
        is_read_param = self.request.query_params.get("is_read")
        if is_read_param is not None:
            if is_read_param.lower() in ("true", "1"):
                qs = qs.filter(is_read=True)
            elif is_read_param.lower() in ("false", "0"):
                qs = qs.filter(is_read=False)

        level_param = self.request.query_params.get("level")
        if level_param:
            qs = qs.filter(level=level_param)

        return qs.order_by("-created_at")

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        """Mark individual notification as read."""
        notification = self.get_object()
        notification.mark_as_read()
        return Response(self.get_serializer(notification).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        """Mark all unread notifications for the user in the workspace as read."""
        qs = self.get_queryset().filter(is_read=False)
        updated_count = qs.update(is_read=True, read_at=timezone.now())

        # Invalidate unread count cache
        org = getattr(request, "tenant", None)
        org_id = str(org.id) if org else "global"
        cache.delete(get_unread_cache_key(str(request.user.id), org_id))

        return Response(
            {"status": "success", "marked_read_count": updated_count},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        """Return ultra-fast Redis-cached unread notification count."""
        org = getattr(request, "tenant", None)
        org_id = org.id if org else None
        count = NotificationDispatcher.get_unread_count(request.user.id, org_id)
        return Response({"unread_count": count}, status=status.HTTP_200_OK)


class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    """
    ViewSet managing user delivery preferences and multi-channel endpoints.
    """
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return preference record for the authenticated requesting user."""
        return NotificationPreference.objects.filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        """Get or create preference for the current user."""
        pref, _ = NotificationPreference.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(pref)
        return Response(serializer.data, status=status.HTTP_200_OK)
