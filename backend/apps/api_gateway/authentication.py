"""
Authentication classes for Developer API Gateway.

Provides APIKeyAuthentication for DRF, verifying raw API keys against hashed DB entries,
checking expiration, IP allowlists, setting active tenant context, and tracking key usage.
"""

from typing import Optional, Tuple
from django.utils.translation import gettext_lazy as _
from rest_framework import authentication, exceptions
from apps.api_gateway.models import APIKey


class APIKeyAuthentication(authentication.BaseAuthentication):
    """
    Custom DRF Authentication class for Developer API Keys.
    
    Accepts keys via:
    - HTTP Header: X-API-Key: agy_live_...
    - HTTP Header: Authorization: Api-Key agy_live_...
    """

    def authenticate(self, request) -> Optional[Tuple[object, APIKey]]:
        raw_key = self.get_key_from_request(request)
        if not raw_key:
            return None

        # Keys must start with a valid prefix pattern and be at least 16 chars
        if len(raw_key) < 16:
            raise exceptions.AuthenticationFailed(_("Invalid API Key format."))

        prefix = raw_key[:12]
        
        try:
            api_key = APIKey.all_objects.select_related("user", "organization").get(
                prefix=prefix,
                is_active=True,
                is_deleted=False,
            )
        except APIKey.DoesNotExist:
            raise exceptions.AuthenticationFailed(_("Invalid or unknown API Key."))

        if not api_key.verify_key(raw_key):
            raise exceptions.AuthenticationFailed(_("Invalid or unknown API Key."))

        if api_key.is_expired:
            raise exceptions.AuthenticationFailed(_("API Key has expired."))

        # Verify IP allowlist if defined
        if api_key.allowed_ips:
            client_ip = self.get_client_ip(request)
            if not self.is_ip_allowed(client_ip, api_key.allowed_ips):
                raise exceptions.AuthenticationFailed(
                    _("Access denied from client IP address: %(ip)s") % {"ip": client_ip}
                )

        # Attach organization to tenant context if not already set
        if hasattr(request, "tenant") and api_key.organization:
            request.tenant = api_key.organization

        # Asynchronously or directly record usage timestamp
        api_key.record_usage()

        return (api_key.user, api_key)

    def authenticate_header(self, request) -> str:
        """Return WWW-Authenticate header string for 401 Unauthorized response formatting."""
        return 'Api-Key realm="api"'

    def get_key_from_request(self, request) -> Optional[str]:
        """Extract key from X-API-Key or Authorization headers."""
        api_key_header = request.META.get("HTTP_X_API_KEY")
        if api_key_header:
            return api_key_header.strip()

        auth_header = request.META.get("HTTP_AUTHORIZATION")
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() in ["api-key", "apikey"]:
                return parts[1].strip()

        return None

    def get_client_ip(self, request) -> str:
        """Extract remote IP address from request metadata."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR", "")
        return ip

    def is_ip_allowed(self, client_ip: str, allowed_ips: list) -> bool:
        """Check if client IP matches allowed IP list or wildcard."""
        if not allowed_ips or "*" in allowed_ips:
            return True
        return client_ip in allowed_ips
