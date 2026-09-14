"""REST API endpoints for managing TCA Automated Actions, testing conditions, and inspecting logs."""

import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.base_models import BaseModel as AppBaseModel
from modules.base.identity_rbac.dependencies import get_current_user
from modules.base.identity_rbac.models import User
from modules.base.automated_actions.models import AutomatedAction, ActionExecutionLog
from modules.base.automated_actions.schemas import (
    ActionHandlerMeta,
    AutomatedActionCreate,
    AutomatedActionUpdate,
    AutomatedActionRead,
    ActionExecutionLogRead,
    ConditionTestRequest,
    ConditionTestResponse,
    ModelIntrospectionItem,
    ModelFieldsIntrospectionResponse,
)
from modules.base.automated_actions.introspection import (
    get_registered_models,
    get_model_fields,
    validate_create_record_config,
    validate_update_record_config,
)
from modules.base.automated_actions.engine.registry import action_registry
from modules.base.automated_actions.engine.evaluator import ASTConditionEvaluator
from modules.base.automated_actions.engine.interceptors import extract_instance_state

router = APIRouter()


# ---------------- Model & Field Introspection ----------------
@router.get("/introspection/models", response_model=List[ModelIntrospectionItem], tags=["Automated Actions - Introspection"])
async def list_models_introspection(
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Retrieve catalog of all registered SQLAlchemy ORM models available for event triggers and actions."""
    return get_registered_models()


@router.get("/introspection/models/{model_name}/fields", response_model=ModelFieldsIntrospectionResponse, tags=["Automated Actions - Introspection"])
async def get_model_fields_introspection(
    model_name: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve comprehensive field specification, data types, choices, and requirement flags for a model."""
    spec = get_model_fields(model_name)
    if not spec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_name}' not found in registry.",
        )
    return spec


# ---------------- Action Types Metadata ----------------
@router.get("/action-types", response_model=List[ActionHandlerMeta], tags=["Automated Actions - Registry"])
async def list_action_types(
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Retrieve self-describing metadata and JSON Schemas for all registered action handlers."""
    return action_registry.get_metadata()


# ---------------- Automated Action Rules CRUD ----------------
@router.get("/rules", response_model=List[AutomatedActionRead], tags=["Automated Actions - Rules"])
async def list_automated_actions(
    target_model: Optional[str] = Query(None, description="Filter rules by target model name"),
    trigger_type: Optional[str] = Query(None, description="Filter rules by trigger type"),
    is_active: Optional[bool] = Query(None, description="Filter active/inactive rules"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[AutomatedAction]:
    """List all automated action rules configured for the active tenant company."""
    stmt = (
        select(AutomatedAction)
        .where(AutomatedAction.company_id == current_user.company_id)
        .order_by(AutomatedAction.sequence.asc())
    )
    if target_model:
        stmt = stmt.where(AutomatedAction.target_model.ilike(target_model))
    if trigger_type:
        stmt = stmt.where(AutomatedAction.trigger_type == trigger_type)
    if is_active is not None:
        stmt = stmt.where(AutomatedAction.is_active == is_active)

    return (await db.execute(stmt)).scalars().all()


@router.post("/rules", response_model=AutomatedActionRead, status_code=status.HTTP_201_CREATED, tags=["Automated Actions - Rules"])
async def create_automated_action(
    payload: AutomatedActionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AutomatedAction:
    """Create and activate a new automated action rule for the tenant."""
    # 1. Validate action type exists in registry
    handler = action_registry.get(payload.action_type)
    if not handler:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Action type '{payload.action_type}' is not registered.",
        )

    # 2. Validate action configuration against handler schema
    try:
        handler.config_schema(**payload.action_config)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid action_config for handler '{payload.action_type}': {str(exc)}",
        )

    # 3. Pre-flight schema validation for record mutations
    if payload.action_type == "create_record":
        target_cls_name = payload.action_config.get("model_name", "")
        record_values = payload.action_config.get("values", {})
        val_errors = validate_create_record_config(target_cls_name, record_values)
        if val_errors:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"message": "Invalid create_record configuration", "errors": val_errors},
            )
    elif payload.action_type == "update_record":
        target_model = payload.target_model
        update_fields = payload.action_config.get("fields", {})
        val_errors = validate_update_record_config(target_model, update_fields)
        if val_errors:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"message": "Invalid update_record configuration", "errors": val_errors},
            )

    action = AutomatedAction(
        company_id=current_user.company_id,
        name=payload.name,
        description=payload.description,
        target_model=payload.target_model,
        trigger_type=payload.trigger_type.value,
        watched_fields=payload.watched_fields,
        condition_tree=payload.condition_tree,
        action_type=payload.action_type,
        action_config=payload.action_config,
        execution_mode=payload.execution_mode.value,
        sequence=payload.sequence,
        is_active=payload.is_active,
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)
    return action


@router.get("/rules/{id}", response_model=AutomatedActionRead, tags=["Automated Actions - Rules"])
async def get_automated_action(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AutomatedAction:
    """Get single automated action rule by ID."""
    stmt = select(AutomatedAction).where(
        AutomatedAction.id == id,
        AutomatedAction.company_id == current_user.company_id,
    )
    action = (await db.execute(stmt)).scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automated action rule not found.")
    return action


@router.patch("/rules/{id}", response_model=AutomatedActionRead, tags=["Automated Actions - Rules"])
async def update_automated_action(
    id: uuid.UUID,
    payload: AutomatedActionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AutomatedAction:
    """Update an automated action rule."""
    stmt = select(AutomatedAction).where(
        AutomatedAction.id == id,
        AutomatedAction.company_id == current_user.company_id,
    )
    action = (await db.execute(stmt)).scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automated action rule not found.")

    data = payload.model_dump(exclude_unset=True)

    # Validate action type if changed
    target_action_type = data.get("action_type", action.action_type)
    handler = action_registry.get(target_action_type)
    if not handler:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Action type '{target_action_type}' is not registered.")

    # Validate action config if changed
    if "action_config" in data:
        try:
            handler.config_schema(**data["action_config"])
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid action_config: {str(exc)}")

    # Pre-flight validation if action_type or action_config or target_model are being updated
    eff_action_type = data.get("action_type", action.action_type)
    eff_action_config = data.get("action_config", action.action_config)
    eff_target_model = data.get("target_model", action.target_model)

    if eff_action_type == "create_record" and ("action_config" in data or "action_type" in data):
        target_cls_name = eff_action_config.get("model_name", "")
        record_values = eff_action_config.get("values", {})
        val_errors = validate_create_record_config(target_cls_name, record_values)
        if val_errors:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"message": "Invalid create_record configuration", "errors": val_errors},
            )
    elif eff_action_type == "update_record" and ("action_config" in data or "target_model" in data or "action_type" in data):
        update_fields = eff_action_config.get("fields", {})
        val_errors = validate_update_record_config(eff_target_model, update_fields)
        if val_errors:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"message": "Invalid update_record configuration", "errors": val_errors},
            )

    for field_name, val in data.items():
        if hasattr(val, "value"):
            val = val.value
        setattr(action, field_name, val)

    action.updated_by_id = current_user.id
    await db.commit()
    await db.refresh(action)

    return action


@router.delete("/rules/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Automated Actions - Rules"])
async def delete_automated_action(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete an automated action rule."""
    stmt = select(AutomatedAction).where(
        AutomatedAction.id == id,
        AutomatedAction.company_id == current_user.company_id,
    )
    action = (await db.execute(stmt)).scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automated action rule not found.")

    action.soft_delete(current_user.id)
    await db.commit()
    return None


# ---------------- Condition Dry-Run Testing ----------------
@router.post("/rules/test-condition", response_model=ConditionTestResponse, tags=["Automated Actions - Testing"])
async def test_action_condition(
    payload: ConditionTestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConditionTestResponse:
    """Dry-run test an AST condition tree against a live record in the database."""
    # Find model class
    model_cls = None
    for mapper in AppBaseModel.registry.mappers:
        cls = mapper.class_
        if cls.__name__.lower() == payload.target_model.lower():
            model_cls = cls
            break

    if not model_cls:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Model '{payload.target_model}' not found in registry.")

    stmt = select(model_cls).where(
        getattr(model_cls, "id") == payload.target_id,
        getattr(model_cls, "company_id") == current_user.company_id,
    )
    record = (await db.execute(stmt)).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Record of type '{payload.target_model}' with ID '{payload.target_id}' not found.")

    record_data, _, _ = extract_instance_state(record)
    matched = ASTConditionEvaluator.evaluate(
        condition_tree=payload.condition_tree,
        record_data=record_data,
    )

    return ConditionTestResponse(
        matched=matched,
        target_model=payload.target_model,
        target_id=payload.target_id,
        evaluated_record=record_data,
    )


# ---------------- Execution Logs ----------------
@router.get("/logs", response_model=List[ActionExecutionLogRead], tags=["Automated Actions - Logs"])
async def list_action_execution_logs(
    action_id: Optional[uuid.UUID] = Query(None, description="Filter logs by automated action ID"),
    target_model: Optional[str] = Query(None, description="Filter logs by target model name"),
    status: Optional[str] = Query(None, description="Filter logs by status ('success', 'failed', 'skipped')"),
    limit: int = Query(50, ge=1, le=200, description="Max log rows to return"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ActionExecutionLog]:
    """Retrieve historical action execution telemetry logs for the active tenant."""
    stmt = (
        select(ActionExecutionLog)
        .where(ActionExecutionLog.company_id == current_user.company_id)
        .order_by(ActionExecutionLog.created_at.desc())
        .limit(limit)
    )
    if action_id:
        stmt = stmt.where(ActionExecutionLog.action_id == action_id)
    if target_model:
        stmt = stmt.where(ActionExecutionLog.target_model.ilike(target_model))
    if status:
        stmt = stmt.where(ActionExecutionLog.status == status)

    return (await db.execute(stmt)).scalars().all()
