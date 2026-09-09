"""
REST API Views and ViewSets for Multi-Tenancy.
"""

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _

from apps.tenants.models import Organization, OrganizationMembership, OrganizationInvitation
from apps.tenants.serializers import (
    OrganizationSerializer,
    OrganizationMembershipSerializer,
    OrganizationInvitationSerializer,
    AcceptInvitationSerializer,
)


class OrganizationViewSet(viewsets.ModelViewSet):
    """
    CRUD API for Organizations and Workspaces.
    """
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Organization.objects.all().prefetch_related("memberships")
        return Organization.objects.filter(
            memberships__user=user,
            memberships__is_active=True
        ).distinct().prefetch_related("memberships")

    def perform_create(self, serializer):
        org = serializer.save()
        # Automatically make creator the primary Owner
        OrganizationMembership.objects.get_or_create(
            organization=org,
            user=self.request.user,
            defaults={
                "role": OrganizationMembership.ROLE_OWNER,
                "is_active": True,
            }
        )

    @action(detail=True, methods=["get", "post"], url_path="members")
    def members(self, request, pk=None):
        """List or add members in this workspace."""
        org = self.get_object()

        if request.method == "GET":
            memberships = org.memberships.filter(is_active=True).select_related("user")
            serializer = OrganizationMembershipSerializer(memberships, many=True)
            return Response(serializer.data)

        # POST: add member directly (requires admin or owner)
        if not self._is_admin_or_owner(request.user, org):
            return Response(
                {"detail": _("Only organization owners and admins can add members.")},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = OrganizationMembershipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(organization=org)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get", "post"], url_path="invite")
    def invite(self, request, pk=None):
        """List pending invitations or send a new invitation."""
        org = self.get_object()

        if request.method == "GET":
            invitations = org.invitations.filter(status=OrganizationInvitation.STATUS_PENDING)
            serializer = OrganizationInvitationSerializer(invitations, many=True)
            return Response(serializer.data)

        # POST: send invitation (requires admin or owner)
        if not self._is_admin_or_owner(request.user, org):
            return Response(
                {"detail": _("Only organization owners and admins can send invitations.")},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = OrganizationInvitationSerializer(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        invitation = serializer.save(organization=org)
        return Response(
            OrganizationInvitationSerializer(invitation).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"], url_path="switch")
    def switch(self, request, pk=None):
        """Switch active tenant context to this organization."""
        org = self.get_object()
        if not org.is_member(request.user) and not request.user.is_superuser:
            return Response(
                {"detail": _("You are not an active member of this organization.")},
                status=status.HTTP_403_FORBIDDEN
            )

        return Response({
            "message": _("Workspace active."),
            "organization_id": str(org.id),
            "organization_slug": org.slug,
            "organization_name": org.name,
            "header_hint": f"Pass 'X-Workspace-Slug: {org.slug}' in future API calls.",
        })

    def _is_admin_or_owner(self, user, org) -> bool:
        """Check if user has administrative privileges within org."""
        if user.is_superuser:
            return True
        return org.memberships.filter(
            user=user,
            role__in=[OrganizationMembership.ROLE_OWNER, OrganizationMembership.ROLE_ADMIN],
            is_active=True
        ).exists()


class InvitationAcceptAPIView(APIView):
    """
    Endpoint for authenticated users to accept an organization invitation via token.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, token=None):
        serializer = AcceptInvitationSerializer(data=request.data if not token else {"token": token})
        serializer.is_valid(raise_exception=True)
        raw_token = serializer.validated_data["token"]

        invitation = get_object_or_404(OrganizationInvitation, token=raw_token)

        try:
            membership = invitation.accept(request.user)
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "message": _("Invitation accepted successfully."),
            "organization": OrganizationSerializer(invitation.organization).data,
            "membership": OrganizationMembershipSerializer(membership).data,
        }, status=status.HTTP_200_OK)
