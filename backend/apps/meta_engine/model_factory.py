"""
Dynamic In-Memory Django Model Factory & Runtime App Registry Injection.

Compiles MetaModel and MetaField definitions into live, full-featured
Django Model classes in memory and registers them into django.apps.apps.
Enables standard Django ORM operations (filter, create, update, delete, joins)
on dynamic metadata entities with zero code generation on disk.
"""

import logging
import uuid
from typing import Any, Dict, Optional, Type

from django.apps import apps
from django.conf import settings
from django.db import models

from apps.core.models import AuditableModel, SoftDeleteModel, TimeStampedModel, UUIDModel
from apps.meta_engine.models import MetaField, MetaModel
from apps.meta_engine.schema_engine import DynamicSchemaEngine

logger = logging.getLogger(__name__)


class DynamicModelFactory:
    """
    Constructs and registers live Django Model classes in memory from MetaModel definitions.
    """

    _registry: Dict[str, Type[models.Model]] = {}

    @classmethod
    def get_registered_model(cls, model_slug: str) -> Optional[Type[models.Model]]:
        """Retrieve an in-memory compiled model by its slug."""
        normalized_slug = model_slug.lower().replace("-", "_")
        return cls._registry.get(normalized_slug)

    @classmethod
    def get_by_slug(cls, model_slug: str) -> Optional[Type[models.Model]]:
        """
        Retrieve model class by slug, compiling it from MetaModel if not yet loaded.
        """
        normalized_slug = model_slug.lower().replace("-", "_")
        if normalized_slug in cls._registry:
            return cls._registry[normalized_slug]
        meta_model = MetaModel.objects.filter(name=normalized_slug, is_active=True).first()
        if meta_model:
            return cls.get_or_create_model(meta_model)
        return None

    @classmethod
    def unregister_model(cls, model_slug: str):
        """
        Unregister a dynamic model from both the internal factory and Django app registry.
        """
        normalized_slug = model_slug.lower().replace("-", "_")
        model_cls = cls._registry.pop(normalized_slug, None)
        if model_cls:
            app_label = model_cls._meta.app_label
            model_name = model_cls._meta.model_name
            if app_label in apps.all_models:
                apps.all_models[app_label].pop(model_name, None)
            apps.clear_cache()
            logger.info(f"Unregistered dynamic model '{app_label}.{model_name}' from memory.")

    @classmethod
    def build_field(cls, meta_field: MetaField) -> models.Field:
        """
        Instantiate a live Django model Field for a MetaField.
        Resolves foreign keys to dynamic or static targets.
        """
        field_type = meta_field.field_type
        required = meta_field.required
        kwargs: Dict[str, Any] = {
            "verbose_name": meta_field.label,
            "help_text": meta_field.help_text,
            "null": not required,
            "blank": not required,
            "db_index": meta_field.index,
        }

        if field_type == "char":
            kwargs["max_length"] = meta_field.max_length or 255
            kwargs["unique"] = meta_field.unique
            if meta_field.default_value:
                kwargs["default"] = meta_field.default_value
            elif not required:
                kwargs["default"] = ""
            return models.CharField(**kwargs)

        elif field_type == "text":
            if meta_field.default_value:
                kwargs["default"] = meta_field.default_value
            elif not required:
                kwargs["default"] = ""
            return models.TextField(**kwargs)

        elif field_type == "integer":
            kwargs["unique"] = meta_field.unique
            if meta_field.default_value and meta_field.default_value.strip().lstrip("-").isdigit():
                kwargs["default"] = int(meta_field.default_value)
            return models.IntegerField(**kwargs)

        elif field_type == "float":
            if meta_field.default_value:
                try:
                    kwargs["default"] = float(meta_field.default_value)
                except ValueError:
                    pass
            return models.FloatField(**kwargs)

        elif field_type == "decimal":
            kwargs["max_digits"] = meta_field.max_digits or 12
            kwargs["decimal_places"] = meta_field.decimal_places or 2
            if meta_field.default_value:
                kwargs["default"] = meta_field.default_value
            return models.DecimalField(**kwargs)

        elif field_type == "boolean":
            kwargs.pop("null", None)
            kwargs.pop("blank", None)
            default_val = False
            if meta_field.default_value:
                default_val = meta_field.default_value.lower() in ("true", "1", "yes")
            kwargs["default"] = default_val
            return models.BooleanField(**kwargs)

        elif field_type == "date":
            return models.DateField(**kwargs)

        elif field_type == "datetime":
            return models.DateTimeField(**kwargs)

        elif field_type == "json":
            kwargs["default"] = dict
            return models.JSONField(**kwargs)

        elif field_type == "foreign_key":
            on_delete = getattr(models, meta_field.on_delete_behavior or "SET_NULL", models.SET_NULL)
            kwargs["on_delete"] = on_delete
            kwargs["null"] = True
            kwargs["blank"] = True

            if meta_field.fk_target_model:
                target_model_cls = cls.get_or_create_model(meta_field.fk_target_model)
                return models.ForeignKey(
                    target_model_cls,
                    related_name=f"referencing_{meta_field.model.name}_{meta_field.name}",
                    **kwargs,
                )
            elif meta_field.fk_target_app_model:
                return models.ForeignKey(
                    meta_field.fk_target_app_model,
                    related_name=f"referencing_{meta_field.model.name}_{meta_field.name}",
                    **kwargs,
                )
            else:
                return models.ForeignKey(settings.AUTH_USER_MODEL, **kwargs)

        elif field_type == "file":
            kwargs["upload_to"] = "dynamic_uploads/%Y/%m/"
            return models.FileField(**kwargs)

        return models.CharField(max_length=255, **kwargs)

    @classmethod
    def get_or_create_model(cls, meta_model: MetaModel, force_reload: bool = False) -> Type[models.Model]:
        """
        Compile and register a live Django Model class from a MetaModel definition.
        """
        slug = meta_model.name.lower().replace("-", "_")
        if not force_reload and slug in cls._registry:
            return cls._registry[slug]

        app_label = meta_model.app_label or "dynamic_entities"
        class_name = "".join(part.capitalize() for part in slug.split("_"))

        # Determine base classes based on model capabilities
        # Order matters for Python MRO: UUIDModel, TenantAwareModel/AuditableModel, SoftDeleteModel
        bases = []
        bases.append(UUIDModel)
        if getattr(meta_model, "is_tenant_aware", False):
            from apps.tenants.base_models import TenantAwareModel
            bases.append(TenantAwareModel)
            if meta_model.is_soft_delete:
                bases.append(SoftDeleteModel)
        else:
            if meta_model.is_soft_delete:
                bases.append(SoftDeleteModel)
            if meta_model.is_auditable:
                bases.append(AuditableModel)
            else:
                bases.append(TimeStampedModel)

        # Meta options
        meta_attrs = {
            "db_table": meta_model.table_name,
            "app_label": app_label,
            "ordering": [meta_model.ordering_field or "-created_at"],
            "verbose_name": meta_model.label,
            "verbose_name_plural": meta_model.label_plural or f"{meta_model.label}s",
            "managed": False,  # Physical DDL managed explicitly via DynamicSchemaEngine
        }

        # Model attributes dictionary
        attrs: Dict[str, Any] = {
            "__module__": f"apps.meta_engine.dynamic.{app_label}",
            "Meta": type("Meta", (), meta_attrs),
            "_meta_model_id": meta_model.id,
            "_meta_model_slug": slug,
            "_audit_enabled": getattr(meta_model, "is_auditable", False),
        }

        # Dynamic string representation
        def __str__(self):
            # Try common display fields: name, title, label, subject, or ID
            for display_field in ("name", "title", "label", "subject", "sku", "code"):
                val = getattr(self, display_field, None)
                if val:
                    return str(val)
            return f"{meta_model.label} #{str(self.pk)[:8]}"

        attrs["__str__"] = __str__

        # Attach custom MetaFields
        for meta_field in meta_model.fields.all():
            try:
                django_field = cls.build_field(meta_field)
                attrs[meta_field.name] = django_field
            except Exception as exc:
                logger.error(f"Failed to build field '{meta_field.name}' on '{slug}': {exc}", exc_info=True)

        # Remove prior registration in Django app registry if reloading
        if app_label in apps.all_models:
            apps.all_models[app_label].pop(class_name.lower(), None)
        apps.clear_cache()

        # Construct class in memory (ModelBase.__new__ automatically registers with apps)
        model_cls = type(class_name, tuple(bases), attrs)

        # Register in audit engine if marked as auditable
        if getattr(meta_model, "is_auditable", False):
            try:
                from apps.audit.registry import register_auditable
                register_auditable(model_cls)
            except ImportError:
                pass

        # Store in factory registry
        cls._registry[slug] = model_cls
        logger.info(f"Successfully compiled dynamic model '{app_label}.{class_name}'.")

        return model_cls

    @classmethod
    def load_all_active_models(cls):
        """
        Bootstrap all active MetaModels into memory and register them.
        Called on application boot in MetaEngineConfig.ready().
        """
        try:
            active_models = MetaModel.objects.filter(is_active=True).prefetch_related("fields")
            for meta_model in active_models:
                try:
                    cls.get_or_create_model(meta_model)
                except Exception as exc:
                    logger.warning(f"Could not load dynamic model '{meta_model.name}': {exc}")
        except Exception:
            # Database may not be ready during migrations
            pass
