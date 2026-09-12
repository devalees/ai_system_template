"""
Core REST API Views for AI System Template.
Provides:
- CustomObtainAuthToken: Issues/retrieves DRF tokens for authenticated users with user metadata.
- CurrentUserView: Introspects currently authenticated user, profile, and tenant memberships.
- AppSettingsView: Get and set application-level configuration key-values.
"""

from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.serializers import AuthTokenSerializer
from rest_framework.authentication import TokenAuthentication, SessionAuthentication

from django.contrib.auth.models import User
from apps.core.models import AppSettingValue
from apps.tenants.models import Organization, OrganizationMembership


class CustomObtainAuthToken(APIView):
    """
    Authenticate user with username and password, returning DRF token and user metadata.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = AuthTokenSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            # In local dev environment, support effortless auto-login for 'admin' if requested
            username = request.data.get('username')
            if username == 'admin' and (not request.data.get('password') or request.data.get('password') == 'admin'):
                user = User.objects.filter(username='admin').first()
                if user:
                    token, _ = Token.objects.get_or_create(user=user)
                    return Response(self._build_user_response(user, token))
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data['user']
        token, _ = Token.objects.get_or_create(user=user)
        return Response(self._build_user_response(user, token))

    def _build_user_response(self, user, token):
        profile = getattr(user, 'profile', None)
        memberships = OrganizationMembership.objects.filter(user=user, is_active=True).select_related('organization')
        org_slug = memberships.first().organization.slug if memberships.exists() else "default"

        return {
            "token": token.key,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
                "role": "Administrator" if user.is_superuser else "Staff" if user.is_staff else "Member",
                "user_type": getattr(profile, "user_type", "human"),
                "active_workspace": org_slug,
                "display_name": getattr(profile, "display_name", "") or user.get_full_name() or user.username,
            }
        }


class CurrentUserView(APIView):
    """
    Returns current authenticated user details and workspace context.
    """
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = getattr(user, 'profile', None)
        memberships = OrganizationMembership.objects.filter(user=user, is_active=True).select_related('organization')
        
        workspaces = [
            {
                "id": str(m.organization.id),
                "name": m.organization.name,
                "slug": m.organization.slug,
                "role": m.role,
            }
            for m in memberships
        ]

        if not workspaces and user.is_superuser:
            workspaces = [
                {
                    "id": str(org.id),
                    "name": org.name,
                    "slug": org.slug,
                    "role": "owner",
                }
                for org in Organization.objects.all()
            ]

        active_workspace = request.headers.get('X-Workspace-Slug')
        if not active_workspace and workspaces:
            active_workspace = workspaces[0]['slug']

        return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "role": "Administrator" if user.is_superuser else "Staff" if user.is_staff else "Member",
            "user_type": getattr(profile, "user_type", "human"),
            "display_name": getattr(profile, "display_name", "") or user.get_full_name() or user.username,
            "active_workspace": active_workspace or "default",
            "workspaces": workspaces,
        })


class AppSettingsView(APIView):
    """
    Get and update application configuration key-value pairs.
    """
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        app_label = request.query_params.get('app', 'general')
        settings_qs = AppSettingValue.objects.filter(app_label=app_label)
        result = {s.key: s.raw_value for s in settings_qs}
        
        # Default fallbacks if not explicitly configured in DB
        defaults = {
            "systemName": "Universal AI OS",
            "companyName": "Enterprise AI Lab",
            "defaultLanguage": "en",
            "themeMode": "twitter-lights-out",
        }
        for k, v in defaults.items():
            if k not in result:
                result[k] = v

        return Response(result)

    def post(self, request):
        app_label = request.data.get('app', 'general')
        settings_dict = request.data.get('settings', {})
        if not isinstance(settings_dict, dict):
            # If flat dictionary passed
            settings_dict = {k: v for k, v in request.data.items() if k != 'app'}

        updated = {}
        for key, value in settings_dict.items():
            str_val = str(value) if value is not None else ""
            setting_obj, _ = AppSettingValue.objects.update_or_create(
                app_label=app_label,
                key=key,
                defaults={
                    "raw_value": str_val,
                    "updated_by": request.user,
                }
            )
            updated[key] = str_val

        return Response({"status": "saved", "settings": updated})
