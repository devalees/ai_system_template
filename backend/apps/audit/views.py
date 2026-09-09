"""
Views for Comprehensive Activity Audit Trail REST API.
"""

from rest_framework import filters, permissions, viewsets

from apps.audit.models import ActivityLog
from apps.audit.serializers import ActivityLogSerializer
from apps.tenants.context import get_current_tenant


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for inspecting activity audit trail records.

    Features:
    - Automatic multi-tenant filtering (scopes to active organization).
    - Query parameter filtering by action, actor_type, status, request_id, object_id.
    - Full-text search on target object and actor.
    - Reverse chronological ordering by timestamp.
    """
    queryset = ActivityLog.objects.select_related("actor", "organization", "content_type").all()
    serializer_class = ActivityLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["object_repr", "object_id", "actor__username", "actor__email", "ip_address"]
    ordering_fields = ["timestamp", "action", "status"]
    ordering = ["-timestamp"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # Superusers can view all audit records globally
        if not user.is_superuser:
            # Scoped to active organization if present
            active_org = getattr(self.request, "organization", None) or get_current_tenant()
            if active_org:
                qs = qs.filter(organization=active_org)
            else:
                # Fallback: users without active workspace can only inspect their own actions
                qs = qs.filter(actor=user)

        # Query param filters
        action_param = self.request.query_params.get("action")
        if action_param:
            qs = qs.filter(action=action_param)

        actor_type_param = self.request.query_params.get("actor_type")
        if actor_type_param:
            qs = qs.filter(actor_type=actor_type_param)

        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        request_id_param = self.request.query_params.get("request_id")
        if request_id_param:
            qs = qs.filter(request_id=request_id_param)

        object_id_param = self.request.query_params.get("object_id")
        if object_id_param:
            qs = qs.filter(object_id=object_id_param)

        return qs
