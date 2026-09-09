"""
Multi-Tenant Resolution & Context Injection Middleware.

Inspects incoming requests to resolve the active Organization via:
1. HTTP Header: `X-Organization-ID` (UUID or slug) or `X-Workspace-Slug`
2. Query Parameter: `workspace` (?workspace=slug)
3. Host Subdomain: e.g. `<slug>.platform.com` or custom domain
4. User's Default Active Membership
5. System Default Fallback Workspace

Injects `request.tenant`, `request.organization`, and binds the active tenant
to the Python 3.11 `contextvars` context with guaranteed cleanup.
"""

import uuid
from typing import Optional

from django.http import JsonResponse
from django.utils.translation import gettext_lazy as _

from apps.tenants.context import set_current_tenant, clear_current_tenant
from apps.tenants.models import Organization, OrganizationMembership


class TenantMiddleware:
    """
    Middleware that identifies the active tenant per request and manages
    thread-safe/async-safe context scoping.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        organization, is_explicit = self.resolve_tenant(request)

        # Security check: if an explicit workspace was requested, verify user access
        user = getattr(request, "user", None)
        if is_explicit and organization and user and user.is_authenticated:
            if not user.is_superuser:
                # Check membership or bot service account privileges
                has_access = OrganizationMembership.objects.filter(
                    organization=organization,
                    user=user,
                    is_active=True
                ).exists()
                if not has_access:
                    return JsonResponse(
                        {
                            "error": "Forbidden",
                            "detail": _("You do not have permission to access workspace '%(slug)s'.")
                            % {"slug": organization.slug}
                        },
                        status=403
                    )

        # Attach tenant to request
        request.tenant = organization
        request.organization = organization

        # Bind to contextvars
        token = set_current_tenant(organization)
        try:
            response = self.get_response(request)
            return response
        finally:
            clear_current_tenant(token)

    def resolve_tenant(self, request) -> tuple[Optional[Organization], bool]:
        """
        Resolve the active organization.

        Returns:
            Tuple of (Organization instance or None, is_explicit: bool)
        """
        # 1. HTTP Headers
        header_val = (
            request.META.get("HTTP_X_ORGANIZATION_ID")
            or request.META.get("HTTP_X_WORKSPACE_SLUG")
        )
        if header_val:
            org = self._find_org_by_id_or_slug(header_val)
            if org:
                return org, True

        # 2. Query Parameter
        param_val = request.GET.get("workspace")
        if param_val:
            org = self._find_org_by_id_or_slug(param_val)
            if org:
                return org, True

        # 3. Host domain or subdomain
        host = request.get_host().split(":")[0].lower()
        if host and host not in ("localhost", "127.0.0.1", "testserver"):
            # Check direct domain match
            org_domain = Organization.objects.filter(domain__iexact=host, is_active=True).first()
            if org_domain:
                return org_domain, True

            # Check subdomain (e.g. acme.platform.com -> acme)
            parts = host.split(".")
            if len(parts) >= 3:
                subdomain = parts[0]
                org_sub = Organization.objects.filter(slug__iexact=subdomain, is_active=True).first()
                if org_sub:
                    return org_sub, True

        # 4. Authenticated User's Membership
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            membership = OrganizationMembership.objects.filter(
                user=user,
                is_active=True,
                organization__is_active=True
            ).select_related("organization").first()
            if membership:
                return membership.organization, False

        # 5. Global System Default Fallback
        default_org = Organization.objects.filter(slug="default", is_active=True).first()
        return default_org, False

    def _find_org_by_id_or_slug(self, identifier: str) -> Optional[Organization]:
        """Lookup organization by UUID or slug."""
        identifier = identifier.strip()
        # Check if valid UUID
        try:
            uuid_obj = uuid.UUID(identifier)
            return Organization.objects.filter(id=uuid_obj, is_active=True).first()
        except ValueError:
            pass

        # Otherwise search by slug
        return Organization.objects.filter(slug__iexact=identifier, is_active=True).first()
