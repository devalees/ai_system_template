"""Action handlers for direct database record mutations (field updates and record creation)."""

import uuid
from typing import Optional, Dict, Any
from jinja2 import Template
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.base_models import BaseModel as AppBaseModel
from modules.base.automated_actions.handlers.base import BaseActionHandler, ActionContext


class UpdateRecordActionConfig(BaseModel):
    """Configuration schema for Update Record action."""
    fields: Dict[str, Any] = Field(..., description="Key-value mapping of field names to update on target record")
    target_relation: Optional[str] = Field(None, description="Optional relation path to update (e.g. 'company', 'parent'). None updates current record.")


class UpdateRecordActionHandler(BaseActionHandler):
    """Action handler that updates specified field values on the trigger record."""

    action_type = "update_record"
    title = "Update Record Fields"
    description = "Directly update one or more fields on the trigger record or a related entity."
    config_schema = UpdateRecordActionConfig

    async def execute(
        self,
        db: AsyncSession,
        context: ActionContext,
        config: UpdateRecordActionConfig,
    ) -> Dict[str, Any]:
        target = context.record
        if config.target_relation and hasattr(context.record, config.target_relation):
            target = getattr(context.record, config.target_relation)

        if not target:
            return {"status": "skipped", "reason": "Target record instance not available"}

        template_vars = {
            "record": context.record_data,
            "diff": context.diff or {},
            "company_id": str(context.company_id),
            "target_model": context.target_model,
            "target_id": str(context.target_id),
        }

        updated_fields: Dict[str, Any] = {}
        for field_name, val in config.fields.items():
            if not hasattr(target, field_name):
                continue

            # Render string templates if Jinja2 syntax present
            if isinstance(val, str) and "{{" in val:
                val = Template(val).render(**template_vars)

            setattr(target, field_name, val)
            updated_fields[field_name] = val

        if hasattr(target, "updated_by_id") and context.user_id:
            setattr(target, "updated_by_id", context.user_id)

        await db.commit()
        await db.refresh(target)

        return {
            "status": "updated",
            "target_model": context.target_model,
            "target_id": str(context.target_id),
            "updated_fields": updated_fields,
        }


class CreateRecordActionConfig(BaseModel):
    """Configuration schema for Create Record action."""
    model_name: str = Field(..., description="Target model name to instantiate (e.g. 'Activity', 'DocumentAttachment')")
    values: Dict[str, Any] = Field(..., description="Initial field values for the new record")


class CreateRecordActionHandler(BaseActionHandler):
    """Action handler that instantiates and persists a new record in any target module."""

    action_type = "create_record"
    title = "Create New Record"
    description = "Instantiate a new record in any target module (e.g. create a follow-up task or activity)."
    config_schema = CreateRecordActionConfig

    async def execute(
        self,
        db: AsyncSession,
        context: ActionContext,
        config: CreateRecordActionConfig,
    ) -> Dict[str, Any]:
        from core.kernel import kernel

        # Find model class across loaded modules
        model_cls = None
        for mapper in AppBaseModel.registry.mappers:
            cls = mapper.class_
            if cls.__name__.lower() == config.model_name.lower():
                model_cls = cls
                break

        if not model_cls:
            return {"status": "failed", "reason": f"Target model '{config.model_name}' not found in registry"}

        template_vars = {
            "record": context.record_data,
            "diff": context.diff or {},
            "company_id": str(context.company_id),
            "target_model": context.target_model,
            "target_id": str(context.target_id),
        }

        # Build initial attributes
        init_kwargs: Dict[str, Any] = {"company_id": context.company_id}
        if hasattr(model_cls, "created_by_id") and context.user_id:
            init_kwargs["created_by_id"] = context.user_id

        for k, v in config.values.items():
            if isinstance(v, str) and "{{" in v:
                v = Template(v).render(**template_vars)
            # Auto-cast UUID strings
            if isinstance(v, str) and len(v) == 36 and "-" in v:
                try:
                    v = uuid.UUID(v)
                except ValueError:
                    pass
            init_kwargs[k] = v

        new_instance = model_cls(**init_kwargs)
        db.add(new_instance)
        await db.commit()
        await db.refresh(new_instance)

        return {
            "status": "created",
            "model_name": config.model_name,
            "new_record_id": str(getattr(new_instance, "id", "")),
        }
