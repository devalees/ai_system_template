"""
Universal Declarative REST API Gateway & Modular App Store Endpoints.

Provides polymorphic CRUD operations, schema introspection, row-level MetaRule security,
and module management over dynamic metadata models.
"""

import json
import logging
from typing import Any, Dict

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.meta_engine.app_installer import AppInstaller
from apps.meta_engine.app_uninstaller import AppUninstaller
from apps.meta_engine.manifest_reader import AppManifestReader
from apps.meta_engine.model_factory import DynamicModelFactory
from apps.meta_engine.models import MetaModel, MetaRule, SystemModule
from apps.meta_engine.serializers import (
    DynamicEntitySerializerFactory,
    SystemModuleSerializer,
)

logger = logging.getLogger(__name__)


class DefaultPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200


class UniversalEntityGatewayView(APIView):
    """
    Polymorphic REST API gateway providing dynamic CRUD operations and schema introspection
    for any active MetaModel.
    """
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = DefaultPagination

    def _get_model_and_class(self, model_slug: str):
        """Resolve MetaModel and compiled in-memory model class."""
        meta_model = get_object_or_404(
            MetaModel.objects.filter(is_active=True).prefetch_related("fields", "views", "reports"),
            name=model_slug.lower().replace("-", "_"),
        )
        model_cls = DynamicModelFactory.get_or_create_model(meta_model)
        if not model_cls:
            return None, None
        return meta_model, model_cls

    def _check_rules_and_filter_qs(self, request, meta_model: MetaModel, model_cls, action_type: str):
        """
        Evaluate MetaRule permissions and apply row-level domain filters.
        """
        qs = model_cls.objects.all()

        # Superusers and staff bypass MetaRules
        if request.user.is_superuser or request.user.is_staff:
            return qs

        user_groups = request.user.groups.all()
        rules = MetaRule.objects.filter(model=meta_model, is_active=True).filter(
            Q(group__isnull=True) | Q(group__in=user_groups)
        )

        if not rules.exists():
            return qs

        # Check action permissions
        has_permission = False
        domain_filters = []

        for rule in rules:
            if action_type == "read" and rule.perm_read:
                has_permission = True
            elif action_type == "create" and rule.perm_create:
                has_permission = True
            elif action_type == "write" and rule.perm_write:
                has_permission = True
            elif action_type == "delete" and rule.perm_delete:
                has_permission = True

            if rule.domain_filter:
                domain_filters.append(rule.domain_filter)

        if not has_permission:
            return None

        # Apply row-level domain filters
        for d_filter in domain_filters:
            filter_kwargs = {}
            for k, v in d_filter.items():
                if isinstance(v, str) and "{{user.id}}" in v:
                    v = v.replace("{{user.id}}", str(request.user.id))
                filter_kwargs[k] = v
            try:
                qs = qs.filter(**filter_kwargs)
            except Exception as exc:
                logger.warning(f"Could not apply domain filter {filter_kwargs}: {exc}")

        return qs

    def get(self, request, model_slug: str, pk: str = None):
        """List records or retrieve a single record."""
        meta_model, model_cls = self._get_model_and_class(model_slug)
        if not meta_model:
            return Response({"detail": "Dynamic entity could not be loaded."}, status=status.HTTP_404_NOT_FOUND)

        qs = self._check_rules_and_filter_qs(request, meta_model, model_cls, "read")
        if qs is None:
            return Response({"detail": "Access denied by security rules."}, status=status.HTTP_403_FORBIDDEN)

        serializer_cls = DynamicEntitySerializerFactory.get_serializer_class(meta_model, model_cls)

        if pk:
            obj = get_object_or_404(qs, pk=pk)
            serializer = serializer_cls(obj)
            return Response(serializer.data)

        # Filtering
        valid_fields = {f.name for f in model_cls._meta.fields}
        filter_kwargs = {}
        for param, val in request.query_params.items():
            if param in valid_fields:
                filter_kwargs[param] = val
        if filter_kwargs:
            qs = qs.filter(**filter_kwargs)

        # Search
        search_query = request.query_params.get("search")
        if search_query:
            search_q = Q()
            for f in model_cls._meta.fields:
                if f.get_internal_type() in ("CharField", "TextField"):
                    search_q |= Q(**{f"{f.name}__icontains": search_query})
            qs = qs.filter(search_q)

        # Ordering
        ordering = request.query_params.get("ordering")
        if ordering and ordering.lstrip("-") in valid_fields:
            qs = qs.order_by(ordering)

        # Pagination
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            serializer = serializer_cls(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = serializer_cls(qs, many=True)
        return Response(serializer.data)

    def post(self, request, model_slug: str, pk: str = None):
        """Create a new record."""
        meta_model, model_cls = self._get_model_and_class(model_slug)
        if not meta_model:
            return Response({"detail": "Dynamic entity could not be loaded."}, status=status.HTTP_404_NOT_FOUND)

        qs = self._check_rules_and_filter_qs(request, meta_model, model_cls, "create")
        if qs is None:
            return Response({"detail": "Creation denied by security rules."}, status=status.HTTP_403_FORBIDDEN)

        serializer_cls = DynamicEntitySerializerFactory.get_serializer_class(meta_model, model_cls)
        serializer = serializer_cls(data=request.data)
        serializer.is_valid(raise_exception=True)

        extra_save_kwargs = {}
        if meta_model.is_auditable and request.user.is_authenticated:
            extra_save_kwargs["created_by"] = request.user
            extra_save_kwargs["updated_by"] = request.user

        instance = serializer.save(**extra_save_kwargs)
        return Response(serializer_cls(instance).data, status=status.HTTP_201_CREATED)

    def put(self, request, model_slug: str, pk: str):
        """Update a record (full)."""
        return self._update(request, model_slug, pk, partial=False)

    def patch(self, request, model_slug: str, pk: str):
        """Update a record (partial)."""
        return self._update(request, model_slug, pk, partial=True)

    def _update(self, request, model_slug: str, pk: str, partial: bool):
        meta_model, model_cls = self._get_model_and_class(model_slug)
        if not meta_model:
            return Response({"detail": "Dynamic entity could not be loaded."}, status=status.HTTP_404_NOT_FOUND)

        qs = self._check_rules_and_filter_qs(request, meta_model, model_cls, "write")
        if qs is None:
            return Response({"detail": "Modification denied by security rules."}, status=status.HTTP_403_FORBIDDEN)

        obj = get_object_or_404(qs, pk=pk)
        serializer_cls = DynamicEntitySerializerFactory.get_serializer_class(meta_model, model_cls)
        serializer = serializer_cls(obj, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        extra_save_kwargs = {}
        if meta_model.is_auditable and request.user.is_authenticated:
            extra_save_kwargs["updated_by"] = request.user

        instance = serializer.save(**extra_save_kwargs)
        return Response(serializer_cls(instance).data)

    def delete(self, request, model_slug: str, pk: str):
        """Delete a record (standard or paranoid soft-delete)."""
        meta_model, model_cls = self._get_model_and_class(model_slug)
        if not meta_model:
            return Response({"detail": "Dynamic entity could not be loaded."}, status=status.HTTP_404_NOT_FOUND)

        qs = self._check_rules_and_filter_qs(request, meta_model, model_cls, "delete")
        if qs is None:
            return Response({"detail": "Deletion denied by security rules."}, status=status.HTTP_403_FORBIDDEN)

        obj = get_object_or_404(qs, pk=pk)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EntitySchemaIntrospectionView(APIView):
    """
    Returns declarative schema introspection for a dynamic entity.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, model_slug: str):
        meta_model = get_object_or_404(
            MetaModel.objects.filter(is_active=True).prefetch_related("fields", "views", "reports"),
            name=model_slug.lower().replace("-", "_"),
        )

        fields_data = []
        for f in meta_model.fields.all():
            fk_target = None
            if f.fk_target_model:
                fk_target = f.fk_target_model.name
            elif f.fk_target_app_model:
                fk_target = f.fk_target_app_model

            fields_data.append({
                "name": f.name,
                "label": f.label,
                "field_type": f.field_type,
                "required": f.required,
                "unique": f.unique,
                "default": f.default_value,
                "choices": f.choices,
                "fk_target": fk_target,
                "sequence": f.sequence,
                "is_readonly": f.is_readonly,
            })

        views_data = [
            {
                "name": v.name,
                "view_type": v.view_type,
                "is_default": v.is_default,
                "layout_schema": v.layout_schema,
            }
            for v in meta_model.views.filter(is_active=True)
        ]

        reports_data = [
            {
                "name": r.name,
                "slug": r.slug,
                "report_type": r.report_type,
                "paper_format": r.paper_format,
                "orientation": r.orientation,
                "is_default": r.is_default,
            }
            for r in meta_model.reports.filter(is_active=True)
        ]

        return Response({
            "model": {
                "name": meta_model.name,
                "label": meta_model.label,
                "label_plural": meta_model.label_plural,
                "app_label": meta_model.app_label,
                "table_name": meta_model.table_name,
                "is_auditable": meta_model.is_auditable,
                "is_soft_delete": meta_model.is_soft_delete,
                "ordering_field": meta_model.ordering_field,
            },
            "fields": fields_data,
            "views": views_data,
            "reports": reports_data,
        })


class SystemModuleViewSet(viewsets.ModelViewSet):
    """
    CRUD and management endpoints for modular app packages.
    """
    queryset = SystemModule.objects.all()
    serializer_class = SystemModuleSerializer
    permission_classes = [permissions.IsAdminUser]

    @action(detail=False, methods=["post"], url_path="sync-discovered")
    def sync_discovered(self, request):
        """Scan disk and synchronize available modular packages."""
        modules = AppManifestReader.sync_discovered_modules()
        serializer = self.get_serializer(modules, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="install")
    def install_module(self, request, pk=None):
        """1-Click Install module and its prerequisite dependencies."""
        module = self.get_object()
        try:
            installed = AppInstaller.install(module.app_id)
            serializer = self.get_serializer(installed, many=True)
            return Response({
                "status": "installed",
                "installed_modules": serializer.data,
            })
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="uninstall")
    def uninstall_module(self, request, pk=None):
        """Safely uninstall module using requested data policy."""
        module = self.get_object()
        policy = request.data.get("data_policy", AppUninstaller.POLICY_ARCHIVE)
        force = request.data.get("force", False)

        try:
            summary = AppUninstaller.uninstall(module.app_id, data_policy=policy, force=force)
            return Response(summary)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
