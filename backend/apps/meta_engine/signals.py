"""
Database Lifecycle Signals for Dynamic Metadata Engine.

Automatically dispatches DDL operations (CREATE TABLE, ALTER TABLE, DROP TABLE)
when MetaModel and MetaField instances are created, modified, or deleted.
"""

import logging
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.meta_engine.models import MetaField, MetaModel
from apps.meta_engine.schema_engine import DynamicSchemaEngine

logger = logging.getLogger(__name__)


@receiver(post_save, sender=MetaModel)
def on_meta_model_saved(sender, instance: MetaModel, created: bool, **kwargs):
    """
    Ensure the physical PostgreSQL table exists upon MetaModel creation.
    """
    try:
        DynamicSchemaEngine.create_table(instance)
    except Exception as exc:
        logger.error(f"Failed to synchronize schema for MetaModel '{instance.name}': {exc}", exc_info=True)


@receiver(post_delete, sender=MetaModel)
def on_meta_model_deleted(sender, instance: MetaModel, **kwargs):
    """
    Drop the physical PostgreSQL table upon MetaModel deletion.
    """
    try:
        DynamicSchemaEngine.drop_table(instance)
    except Exception as exc:
        logger.error(f"Failed to drop table for deleted MetaModel '{instance.name}': {exc}", exc_info=True)


@receiver(post_save, sender=MetaField)
def on_meta_field_saved(sender, instance: MetaField, created: bool, **kwargs):
    """
    Ensure the physical database column exists on the model's table.
    """
    try:
        DynamicSchemaEngine.add_column(instance)
    except Exception as exc:
        logger.error(f"Failed to add column for MetaField '{instance.name}': {exc}", exc_info=True)


@receiver(post_delete, sender=MetaField)
def on_meta_field_deleted(sender, instance: MetaField, **kwargs):
    """
    Drop the column upon MetaField deletion.
    """
    try:
        DynamicSchemaEngine.drop_column(instance)
    except Exception as exc:
        logger.error(f"Failed to drop column for deleted MetaField '{instance.name}': {exc}", exc_info=True)
