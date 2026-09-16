"""FastAPI route endpoints for Universal Work Items, Tasks & Dependencies."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.context import get_active_company_id
from core.exceptions import ValidationException
from modules.base.identity_rbac.models import User
from modules.base.identity_rbac.dependencies import get_current_user

from modules.base.work_items.service import WorkItemService
from modules.base.work_items.schemas import (
    WorkItemStageCreate,
    WorkItemStageUpdate,
    WorkItemStageResponse,
    WorkItemCreate,
    WorkItemUpdate,
    WorkItemResponse,
    WorkItemDependencyCreate,
    WorkItemDependencyResponse,
    WorkItemTreeNode,
    StageTransitionRequest,
)

router = APIRouter(prefix="", tags=["Universal Work Items, Tasks & Dependencies"])


def _resolve_company_id(user: User) -> uuid.UUID:
    """Resolve active company tenant context."""
    cid = get_active_company_id() or user.company_id
    if not cid:
        raise ValidationException("Active company context (X-Company-ID) is required.")
    return cid


# ---------------------------------------------------------------------------
# Stage Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/stages",
    response_model=WorkItemStageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Stage",
    description="Registers a new workflow pipeline stage.",
)
async def create_stage(
    payload: WorkItemStageCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WorkItemStageResponse:
    company_id = _resolve_company_id(user)
    stage = await WorkItemService.create_stage(db, company_id, payload)
    return WorkItemStageResponse.model_validate(stage)


@router.get(
    "/stages",
    response_model=List[WorkItemStageResponse],
    summary="List Stages",
    description="Lists workflow stages ordered by pipeline sequence.",
)
async def list_stages(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[WorkItemStageResponse]:
    company_id = _resolve_company_id(user)
    stages = await WorkItemService.list_stages(db, company_id)
    return [WorkItemStageResponse.model_validate(s) for s in stages]


@router.get(
    "/stages/{stage_id}",
    response_model=WorkItemStageResponse,
    summary="Get Stage",
    description="Fetch single stage by UUID.",
)
async def get_stage(
    stage_id: uuid.UUID = Path(..., description="Stage UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WorkItemStageResponse:
    stage = await WorkItemService.get_stage(db, stage_id)
    return WorkItemStageResponse.model_validate(stage)


@router.patch(
    "/stages/{stage_id}",
    response_model=WorkItemStageResponse,
    summary="Update Stage",
    description="Update stage properties or ordering.",
)
async def update_stage(
    payload: WorkItemStageUpdate,
    stage_id: uuid.UUID = Path(..., description="Stage UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WorkItemStageResponse:
    stage = await WorkItemService.update_stage(db, stage_id, payload)
    return WorkItemStageResponse.model_validate(stage)


@router.delete(
    "/stages/{stage_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Stage",
    description="Soft-deletes a workflow stage.",
)
async def delete_stage(
    stage_id: uuid.UUID = Path(..., description="Stage UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await WorkItemService.delete_stage(db, stage_id)


# ---------------------------------------------------------------------------
# Work Item Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=WorkItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Work Item",
    description="Creates a new task or sub-task.",
)
async def create_work_item(
    payload: WorkItemCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WorkItemResponse:
    company_id = _resolve_company_id(user)
    item = await WorkItemService.create_work_item(db, company_id, payload)
    return WorkItemResponse.model_validate(item)


@router.get(
    "",
    response_model=List[WorkItemResponse],
    summary="List Work Items",
    description="Lists work items for active company with flexible filtering.",
)
async def list_work_items(
    stage_id: Optional[uuid.UUID] = Query(None, description="Filter by stage UUID"),
    assigned_to_id: Optional[uuid.UUID] = Query(None, description="Filter by assigned user UUID"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    is_closed: Optional[bool] = Query(None, description="Filter by completion status"),
    res_model: Optional[str] = Query(None, description="Filter by parent model"),
    res_id: Optional[uuid.UUID] = Query(None, description="Filter by parent record UUID"),
    parent_id: Optional[uuid.UUID] = Query(None, description="Filter by parent task UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[WorkItemResponse]:
    company_id = _resolve_company_id(user)
    items = await WorkItemService.list_work_items(
        db,
        company_id,
        stage_id=stage_id,
        assigned_to_id=assigned_to_id,
        priority=priority,
        is_closed=is_closed,
        res_model=res_model,
        res_id=res_id,
        parent_id=parent_id,
    )
    return [WorkItemResponse.model_validate(i) for i in items]


@router.get(
    "/{item_id}",
    response_model=WorkItemResponse,
    summary="Get Work Item",
    description="Fetch single work item with stage and dependencies.",
)
async def get_work_item(
    item_id: uuid.UUID = Path(..., description="Work Item UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WorkItemResponse:
    item = await WorkItemService.get_work_item(db, item_id)
    return WorkItemResponse.model_validate(item)


@router.patch(
    "/{item_id}",
    response_model=WorkItemResponse,
    summary="Update Work Item",
    description="Update work item properties or status.",
)
async def update_work_item(
    payload: WorkItemUpdate,
    item_id: uuid.UUID = Path(..., description="Work Item UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WorkItemResponse:
    item = await WorkItemService.update_work_item(db, item_id, payload)
    return WorkItemResponse.model_validate(item)


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Work Item",
    description="Soft-deletes a work item and cascades to child sub-tasks.",
)
async def delete_work_item(
    item_id: uuid.UUID = Path(..., description="Work Item UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await WorkItemService.delete_work_item(db, item_id)


# ---------------------------------------------------------------------------
# Sub-task Tree Hierarchy Endpoint
# ---------------------------------------------------------------------------

@router.get(
    "/{item_id}/tree",
    response_model=WorkItemTreeNode,
    summary="Get Sub-task Tree",
    description="Fetches recursive hierarchical sub-task tree rooted at this work item.",
)
async def get_subtask_tree(
    item_id: uuid.UUID = Path(..., description="Root Work Item UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WorkItemTreeNode:
    return await WorkItemService.get_subtask_tree(db, item_id)


# ---------------------------------------------------------------------------
# Dependencies & DAG Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{item_id}/dependencies",
    response_model=WorkItemDependencyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Task Dependency",
    description="Appends a predecessor requirement to this work item with cycle prevention.",
)
async def add_dependency(
    payload: WorkItemDependencyCreate,
    item_id: uuid.UUID = Path(..., description="Successor Work Item UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WorkItemDependencyResponse:
    company_id = _resolve_company_id(user)
    dep = await WorkItemService.add_dependency(db, company_id, item_id, payload)
    return WorkItemDependencyResponse.model_validate(dep)


@router.delete(
    "/dependencies/{dependency_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Dependency",
    description="Removes a dependency constraint edge.",
)
async def delete_dependency(
    dependency_id: uuid.UUID = Path(..., description="Dependency UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await WorkItemService.delete_dependency(db, dependency_id)


# ---------------------------------------------------------------------------
# Kanban Stage Transition Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/{item_id}/stage",
    response_model=WorkItemResponse,
    summary="Transition Stage",
    description="Moves work item to a new Kanban stage and automatically marks closed if terminal.",
)
async def transition_stage(
    payload: StageTransitionRequest,
    item_id: uuid.UUID = Path(..., description="Work Item UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WorkItemResponse:
    item = await WorkItemService.transition_stage(db, item_id, payload.stage_id)
    return WorkItemResponse.model_validate(item)
