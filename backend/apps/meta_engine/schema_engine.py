"""
Dynamic PostgreSQL Schema Engine for Metadata-Driven Runtime.

Translates high-level MetaModel and MetaField definitions into live
PostgreSQL database DDL operations (CREATE TABLE, ALTER TABLE, DROP TABLE,
ADD/DROP COLUMN, and index/foreign-key synchronization) via Django's SchemaEditor.
"""

import logging
import uuid
from typing import Any, Dict, Optional

from django.conf import settings
from django.db import connection, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

from django.apps import apps
from apps.meta_engine.models import MetaField, MetaModel

logger = logging.getLogger(__name__)


class DynamicSchemaEngine:
    """
    Direct DDL synchronizer connecting metadata records to physical PostgreSQL tables.
    """

    @classmethod
    def get_existing_tables(cls) -> list[str]:
        """Return list of existing database tables in the default database."""
        with connection.cursor() as cursor:
            return connection.introspection.table_names(cursor)

    @classmethod
    def table_exists(cls, table_name: str) -> bool:
        """Check if a table exists in the PostgreSQL schema."""
        return table_name in cls.get_existing_tables()

    @classmethod
    def get_existing_columns(cls, table_name: str) -> list[str]:
        """Return list of existing column names for a given table."""
        if not cls.table_exists(table_name):
            return []
        with connection.cursor() as cursor:
            description = connection.introspection.get_table_description(cursor, table_name)
            return [col.name for col in description]

    @classmethod
    def column_exists(cls, table_name: str, column_name: str) -> bool:
        """Check if a specific column exists in a physical table."""
        return column_name in cls.get_existing_columns(table_name)

    @classmethod
    def build_django_field(cls, meta_field: MetaField) -> models.Field:
        """
        Instantiate a live Django model Field corresponding to the MetaField specification.
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
                target_cls = cls.build_transient_model_class(meta_field.fk_target_model)
                return models.ForeignKey(target_cls, **kwargs)
            elif meta_field.fk_target_app_model:
                return models.ForeignKey(meta_field.fk_target_app_model, **kwargs)
            else:
                # Fallback to User model if no target provided
                return models.ForeignKey(settings.AUTH_USER_MODEL, **kwargs)

        elif field_type == "file":
            kwargs["upload_to"] = "dynamic_uploads/%Y/%m/"
            return models.FileField(**kwargs)

        # Default fallback
        return models.CharField(max_length=255, **kwargs)

    @classmethod
    def build_transient_model_class(cls, meta_model: MetaModel, include_user_fields: bool = True) -> type:
        """
        Constructs an ephemeral, real Django model class representing the MetaModel table.
        Used by SchemaEditor to generate accurate DDL statements.
        """
        model_name = f"Dynamic_{meta_model.name.replace('-', '_')}"
        if "meta_engine" in apps.all_models:
            apps.all_models["meta_engine"].pop(model_name.lower(), None)

        meta_attrs = {
            "db_table": meta_model.table_name,
            "app_label": "meta_engine",
            "managed": True,
        }
        attrs: Dict[str, Any] = {
            "__module__": "apps.meta_engine.dynamic_models",
            "Meta": type("Meta", (), meta_attrs),
        }

        # 1. Primary Key: UUIDv4
        attrs["id"] = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

        # 2. Kernel Audit Headers
        if meta_model.is_auditable:
            attrs["created_at"] = models.DateTimeField(auto_now_add=True, db_index=True)
            attrs["updated_at"] = models.DateTimeField(auto_now=True, db_index=True)
            attrs["created_by"] = models.ForeignKey(
                settings.AUTH_USER_MODEL,
                on_delete=models.SET_NULL,
                null=True,
                blank=True,
                related_name=f"+",
            )
            attrs["updated_by"] = models.ForeignKey(
                settings.AUTH_USER_MODEL,
                on_delete=models.SET_NULL,
                null=True,
                blank=True,
                related_name=f"+",
            )

        # 3. Soft Delete Columns
        if meta_model.is_soft_delete:
            attrs["is_deleted"] = models.BooleanField(default=False, db_index=True)
            attrs["deleted_at"] = models.DateTimeField(null=True, blank=True)

        # 4. Custom User-Defined MetaFields
        if include_user_fields and meta_model.pk:
            for meta_field in meta_model.fields.all():
                # Avoid foreign_key to prevent circular recursion during table creation
                if meta_field.field_type != "foreign_key":
                    attrs[meta_field.name] = cls.build_django_field(meta_field)

        return type(model_name, (models.Model,), attrs)

    @classmethod
    def create_table(cls, meta_model: MetaModel) -> bool:
        """
        Execute PostgreSQL CREATE TABLE for the given MetaModel if it does not already exist.
        Returns True if created, False if already existed.
        """
        if cls.table_exists(meta_model.table_name):
            logger.info(f"Table '{meta_model.table_name}' already exists. Skipping create.")
            return False

        model_cls = cls.build_transient_model_class(meta_model, include_user_fields=True)
        with connection.schema_editor() as editor:
            editor.create_model(model_cls)

        logger.info(f"Successfully created PostgreSQL table '{meta_model.table_name}'.")
        return True

    @classmethod
    def add_column(cls, meta_field: MetaField) -> bool:
        """
        Execute PostgreSQL ALTER TABLE ADD COLUMN for the given MetaField.
        """
        meta_model = meta_field.model
        table_name = meta_model.table_name

        # Ensure table exists first
        if not cls.table_exists(table_name):
            cls.create_table(meta_model)

        # Check if column already exists
        col_name = f"{meta_field.name}_id" if meta_field.field_type == "foreign_key" else meta_field.name
        if cls.column_exists(table_name, col_name):
            logger.info(f"Column '{col_name}' already exists on '{table_name}'. Skipping add.")
            return False

        model_cls = cls.build_transient_model_class(meta_model, include_user_fields=False)
        django_field = cls.build_django_field(meta_field)
        django_field.set_attributes_from_name(meta_field.name)

        with connection.schema_editor() as editor:
            editor.add_field(model_cls, django_field)

        logger.info(f"Successfully added column '{col_name}' to '{table_name}'.")
        return True

    @classmethod
    def drop_column(cls, meta_field: MetaField) -> bool:
        """
        Execute PostgreSQL ALTER TABLE DROP COLUMN for the given MetaField.
        """
        meta_model = meta_field.model
        table_name = meta_model.table_name

        col_name = f"{meta_field.name}_id" if meta_field.field_type == "foreign_key" else meta_field.name
        if not cls.column_exists(table_name, col_name):
            logger.info(f"Column '{col_name}' does not exist on '{table_name}'. Skipping drop.")
            return False

        model_cls = cls.build_transient_model_class(meta_model, include_user_fields=False)
        django_field = cls.build_django_field(meta_field)
        django_field.set_attributes_from_name(meta_field.name)

        with connection.schema_editor() as editor:
            editor.remove_field(model_cls, django_field)

        logger.info(f"Successfully dropped column '{col_name}' from '{table_name}'.")
        return True

    @classmethod
    def drop_table(cls, meta_model: MetaModel) -> bool:
        """
        Execute PostgreSQL DROP TABLE for the given MetaModel.
        """
        table_name = meta_model.table_name
        if not cls.table_exists(table_name):
            logger.info(f"Table '{table_name}' does not exist. Skipping drop.")
            return False

        model_cls = cls.build_transient_model_class(meta_model, include_user_fields=False)
        with connection.schema_editor() as editor:
            editor.delete_model(model_cls)

        logger.info(f"Successfully dropped table '{table_name}'.")
        return True

    @classmethod
    def sync_model_schema(cls, meta_model: MetaModel):
        """
        Full synchronization routine:
        1. Ensures the table exists.
        2. Iterates over all MetaFields, creating any missing columns.
        """
        cls.create_table(meta_model)
        for meta_field in meta_model.fields.all():
            cls.add_column(meta_field)
