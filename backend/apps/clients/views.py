"""
REST API ViewSets for Client Management.
"""

from decimal import Decimal
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication, SessionAuthentication

from apps.clients.models import Client
from apps.clients.serializers import ClientSerializer


class ClientViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing external Client accounts.
    Provides CRUD operations, organization filtering, and budget status actions.
    """
    queryset = Client.objects.filter(is_deleted=False).select_related('organization')
    serializer_class = ClientSerializer
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['organization', 'status', 'is_ai_enabled']
    search_fields = ['name', 'slug', 'primary_contact_name', 'primary_contact_email']
    ordering_fields = ['name', 'created_at', 'ai_budget_usd', 'ai_spend_usd']
    lookup_field = 'id'

    @action(detail=True, methods=['get', 'post'], url_path='budget-status')
    def budget_status(self, request, id=None):
        """
        Query or increment the AI service dollar budget for this client.
        GET: Returns current spend, budget ceiling, percentage, status, and milestone checks.
        POST: Accepts `spend_delta_usd` and/or `ai_budget_usd` override.
        """
        client = self.get_object()

        if request.method == 'POST':
            spend_delta = request.data.get('spend_delta_usd')
            budget_override = request.data.get('ai_budget_usd')

            if spend_delta is not None:
                try:
                    delta = Decimal(str(spend_delta))
                    client.ai_spend_usd += delta
                except Exception as e:
                    return Response({"detail": f"Invalid spend_delta_usd: {e}"}, status=status.HTTP_400_BAD_REQUEST)

            if budget_override is not None:
                try:
                    client.ai_budget_usd = Decimal(str(budget_override))
                except Exception as e:
                    return Response({"detail": f"Invalid ai_budget_usd: {e}"}, status=status.HTTP_400_BAD_REQUEST)

            client.save(update_fields=['ai_spend_usd', 'ai_budget_usd'])

        pct = client.ai_budget_percentage
        budget_status = client.ai_budget_status

        # Determine threshold action
        if budget_status == 'exceeded':
            action_desc = "100% Milestone Reached: Block further AI tasks and escalate to Account Manager."
        elif budget_status == 'warning':
            action_desc = "75% Milestone Reached: Emit advisory notice to client/account manager."
        elif budget_status == 'velocity_check':
            action_desc = "50% Milestone Reached: Perform mid-tier velocity check."
        elif not client.is_ai_enabled:
            action_desc = "AI Service Disabled for this client account."
        else:
            action_desc = "Spend within normal parameters."

        return Response({
            "client_id": str(client.id),
            "slug": client.slug,
            "name": client.name,
            "organization_name": client.organization.name,
            "is_ai_enabled": client.is_ai_enabled,
            "can_use_ai": client.can_use_ai(),
            "ai_budget_usd": str(client.ai_budget_usd),
            "ai_spend_usd": str(client.ai_spend_usd),
            "percentage_used": pct,
            "budget_status": budget_status,
            "action_required": action_desc,
            "milestones": {
                "silent_check_25_reached": pct >= 25.0,
                "velocity_check_50_reached": pct >= 50.0,
                "advisory_75_reached": pct >= 75.0,
                "exceeded_100_reached": pct >= 100.0,
            }
        })
