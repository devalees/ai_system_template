"""
Admin configuration for Developer API Gateway models.
"""

from django.contrib import admin
from apps.api_gateway.models import APIKey, InboundWebhook, WebhookEvent


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ["name", "prefix", "user", "organization", "is_active", "expires_at", "last_used_at", "created_at"]
    list_filter = ["is_active", "organization", "created_at"]
    search_fields = ["name", "prefix", "user__email"]
    readonly_fields = ["prefix", "hashed_key", "last_used_at"]


@admin.register(InboundWebhook)
class InboundWebhookAdmin(admin.ModelAdmin):
    list_display = ["name", "endpoint_slug", "provider", "organization", "is_active", "created_at"]
    list_filter = ["provider", "is_active", "organization"]
    search_fields = ["name", "endpoint_slug"]


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ["webhook", "event_type", "status", "organization", "created_at"]
    list_filter = ["status", "event_type", "organization"]
    search_fields = ["event_type", "error_message"]
    readonly_fields = ["webhook", "event_type", "payload", "headers", "status", "error_message"]
