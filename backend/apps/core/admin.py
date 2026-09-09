"""
Django Admin Interface for Application Settings & System Configuration Hub.
"""

import json
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.core.config import get_setting, set_setting
from apps.core.models import AppSettingValue
from apps.core.settings_registry import settings_registry


@admin.register(AppSettingValue)
class AppSettingValueAdmin(admin.ModelAdmin):
    """
    Administrative model management and visual Settings Hub controller.
    """
    list_display = ["app_label", "key", "display_value", "data_type", "updated_at"]
    list_filter = ["app_label", "data_type"]
    search_fields = ["app_label", "key", "raw_value"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["app_label", "key"]

    def display_value(self, obj):
        """Display formatted value or masked secret in list view."""
        if obj.data_type == "secret":
            from apps.core.crypto import mask_secret, decrypt_secret
            decrypted = decrypt_secret(obj.raw_value)
            return mask_secret(decrypted)
        if len(obj.raw_value) > 60:
            return f"{obj.raw_value[:60]}..."
        return obj.raw_value or "-"
    display_value.short_description = _("Current Value")

    def changelist_view(self, request, extra_context=None):
        """Add link to the visual Settings Hub in changelist extra context."""
        extra_context = extra_context or {}
        extra_context["settings_hub_url"] = reverse("admin:core_settings_hub")
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        """Register custom URL endpoint for the visual Settings Hub."""
        urls = super().get_urls()
        custom_urls = [
            path(
                "hub/",
                self.admin_site.admin_view(self.settings_hub_view),
                name="core_settings_hub",
            ),
        ]
        return custom_urls + urls

    def settings_hub_view(self, request):
        """
        Odoo-style single-screen settings dashboard controller.
        """
        settings_registry.ensure_discovered()
        groups = settings_registry.get_all_groups()

        if request.method == "POST":
            app_label = request.POST.get("_app_label")
            group = settings_registry.get_group(app_label)
            if group:
                for key, setting_def in group.settings.items():
                    if setting_def.data_type == "bool":
                        # Checkboxes only submit if checked
                        val = key in request.POST
                    else:
                        val = request.POST.get(key)

                    if val is not None:
                        try:
                            set_setting(f"{app_label}.{key}", val)
                        except Exception as e:
                            messages.error(
                                request,
                                _("Error saving %(key)s: %(err)s") % {"key": key, "err": str(e)},
                            )

                messages.success(
                    request,
                    _("Successfully updated %(group)s settings.") % {"group": group.verbose_name},
                )
            return HttpResponseRedirect(f"{request.path}?tab={app_label}")

        active_tab = request.GET.get("tab")
        if not active_tab and groups:
            active_tab = groups[0].app_label

        prepared_groups = []
        for group in groups:
            items = []
            for key, setting_def in group.settings.items():
                current_val = get_setting(f"{group.app_label}.{key}")
                json_str = ""
                if setting_def.data_type == "json":
                    try:
                        json_str = json.dumps(current_val, indent=2)
                    except Exception:
                        json_str = "{}"

                items.append({
                    "key": key,
                    "setting": setting_def,
                    "current_value": current_val,
                    "current_value_json": json_str,
                })

            prepared_groups.append({
                "app_label": group.app_label,
                "verbose_name": group.verbose_name,
                "icon": group.icon,
                "items": items,
            })

        context = {
            **self.admin_site.each_context(request),
            "title": _("System Configuration Hub"),
            "groups": prepared_groups,
            "active_tab": active_tab,
        }
        return TemplateResponse(request, "admin/core/settings_hub.html", context)
