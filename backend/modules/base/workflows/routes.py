"""FastAPI route endpoints for Workflow definitions, transitions, and state execution."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.context import get_active_company_id
from core.exceptions import EntityNotFoundException, ValidationException
from modules.base.identity_rbac.models import User
from modules.base.identity_rbac.dependencies import get_current_user, require_permission

from modules.base.workflows.service import WorkflowService
from modules.base.workflows.schemas import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionUpdate,
    WorkflowDefinitionResponse,
    WorkflowTransitionCreate,
    WorkflowTransitionResponse,
    ExecuteTransitionRequest,
    WorkflowTransitionResult,
    AvailableTransitionResponse,
    WorkflowExecutionLogResponse,
)

router = APIRouter(prefix="", tags=["Workflows & State Machine Engine"])


def _resolve_company_id(user: User) -> uuid.UUID:
    """Resolve active company ID from context or fallback to user default."""
    cid = get_active_company_id() or user.company_id
    if not cid:
        raise ValidationException("Active company context (X-Company-ID) is required.")
    return cid


# ---------------------------------------------------------------------------
# Workflow Definitions Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/definitions",
    response_model=WorkflowDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Workflow Definition",
    description="Registers a new declarative state machine lifecycle for a target entity model.",
)
async def create_workflow_definition(
    payload: WorkflowDefinitionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = _resolve_company_id(current_user)
    return await WorkflowService.create_definition(db, company_id, payload)


@router.get(
    "/definitions",
    response_model=List[WorkflowDefinitionResponse],
    summary="List Workflow Definitions",
    description="Lists all state machine definitions for the active tenant, with optional filtering.",
)
async def list_workflow_definitions(
    res_model: Optional[str] = Query(None, description="Filter by target model name"),
    is_active: Optional[bool] = Query(None, description="Filter by operational status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = _resolve_company_id(current_user)
    return await WorkflowService.list_definitions(db, company_id, res_model, is_active)


@router.get(
    "/definitions/{id}",
    response_model=WorkflowDefinitionResponse,
    summary="Get Workflow Definition",
    description="Retrieves a workflow definition with its full list of state transitions.",
)
async def get_workflow_definition(
    id: uuid.UUID = Path(..., description="Workflow definition UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = _resolve_company_id(current_user)
    wf = await WorkflowService.get_definition(db, company_id, id)
    if not wf:
        raise EntityNotFoundException("WorkflowDefinition", id)
    return wf


@router.put(
    "/definitions/{id}",
    response_model=WorkflowDefinitionResponse,
    summary="Update Workflow Definition",
    description="Updates metadata, state list, or active status of a workflow definition.",
)
async def update_workflow_definition(
    payload: WorkflowDefinitionUpdate,
    id: uuid.UUID = Path(..., description="Workflow definition UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = _resolve_company_id(current_user)
    return await WorkflowService.update_definition(db, company_id, id, payload)


@router.delete(
    "/definitions/{id}",
    summary="Delete Workflow Definition",
    description="Permanently deletes a workflow definition and all its transitions.",
)
async def delete_workflow_definition(
    id: uuid.UUID = Path(..., description="Workflow definition UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = _resolve_company_id(current_user)
    await WorkflowService.delete_definition(db, company_id, id)
    return {"status": "success", "message": "Workflow definition deleted successfully."}


# ---------------------------------------------------------------------------
# Workflow Transitions Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/definitions/{id}/transitions",
    response_model=WorkflowTransitionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Workflow Transition",
    description="Adds a transition rule (with optional AST guard conditions and record freeze flags).",
)
async def add_workflow_transition(
    payload: WorkflowTransitionCreate,
    id: uuid.UUID = Path(..., description="Workflow definition UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = _resolve_company_id(current_user)
    return await WorkflowService.add_transition(db, company_id, id, payload)


@router.delete(
    "/transitions/{transition_id}",
    summary="Delete Workflow Transition",
    description="Deletes a specific transition rule.",
)
async def delete_workflow_transition(
    transition_id: uuid.UUID = Path(..., description="Transition rule UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = _resolve_company_id(current_user)
    await WorkflowService.delete_transition(db, company_id, transition_id)
    return {"status": "success", "message": "Workflow transition deleted successfully."}


# ---------------------------------------------------------------------------
# Workflow Execution & Record State Operations
# ---------------------------------------------------------------------------

@router.get(
    "/{res_model}/{res_id}/transitions",
    response_model=List[AvailableTransitionResponse],
    summary="Get Available Transitions for Record",
    description="Computes which triggers are currently actionable for a specific record based on its state, RBAC, and guards.",
)
async def get_available_transitions_for_record(
    res_model: str = Path(..., description="Target model name (e.g. 'party', 'sales_order')"),
    res_id: uuid.UUID = Path(..., description="Target record UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = _resolve_company_id(current_user)
    return await WorkflowService.get_available_transitions(db, company_id, current_user, res_model, res_id)


@router.post(
    "/{res_model}/{res_id}/execute",
    response_model=WorkflowTransitionResult,
    summary="Execute Workflow Transition",
    description="Triggers a state machine transition on a business record, verifying guards, RBAC, and applying record freezes.",
)
async def execute_workflow_transition(
    payload: ExecuteTransitionRequest,
    res_model: str = Path(..., description="Target model name (e.g. 'party', 'sales_order')"),
    res_id: uuid.UUID = Path(..., description="Target record UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = _resolve_company_id(current_user)
    return await WorkflowService.execute_transition(
        db,
        company_id,
        current_user,
        res_model,
        res_id,
        payload.trigger_name,
        payload.metadata,
    )


@router.post(
    "/{res_model}/{res_id}/unfreeze",
    summary="Administrative Record Unfreeze",
    description="Overrides a frozen record lock to permit operational corrections.",
)
async def unfreeze_record(
    res_model: str = Path(..., description="Target model name"),
    res_id: uuid.UUID = Path(..., description="Target record UUID"),
    reason: str = Query(default="", description="Audited operational reason for unfreezing"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = _resolve_company_id(current_user)
    await WorkflowService.unfreeze_record(db, company_id, current_user, res_model, res_id, reason)
    return {"status": "success", "message": f"Record '{res_model}' ({res_id}) has been unfrozen."}


@router.get(
    "/{res_model}/{res_id}/history",
    response_model=List[WorkflowExecutionLogResponse],
    summary="Get Record Workflow History",
    description="Returns chronological audit logs of all past state transitions executed on the record.",
)
async def get_record_workflow_history(
    res_model: str = Path(..., description="Target model name"),
    res_id: uuid.UUID = Path(..., description="Target record UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = _resolve_company_id(current_user)
    return await WorkflowService.get_transition_history(db, company_id, res_model, res_id)
