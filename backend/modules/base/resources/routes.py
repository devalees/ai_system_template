"""FastAPI route endpoints for Resource Scheduling & Capacity Allocation."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.context import get_active_company_id
from core.exceptions import ValidationException
from modules.base.identity_rbac.models import User
from modules.base.identity_rbac.dependencies import get_current_user

from modules.base.resources.service import ResourceService
from modules.base.resources.schemas import (
    ResourceCreate,
    ResourceUpdate,
    ResourceResponse,
    ResourceAllocationCreate,
    ResourceAllocationUpdate,
    ResourceAllocationResponse,
    CheckAvailabilityRequest,
    CheckAvailabilityResponse,
)

router = APIRouter(prefix="", tags=["Resource Scheduling & Capacity Allocation"])


def _resolve_company_id(user: User) -> uuid.UUID:
    """Resolve active company tenant context."""
    cid = get_active_company_id() or user.company_id
    if not cid:
        raise ValidationException("Active company context (X-Company-ID) is required.")
    return cid


# ---------------------------------------------------------------------------
# Resource Management Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=ResourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Resource",
    description="Registers a new schedulable resource (personnel, equipment, vehicle, or room).",
)
async def create_resource(
    payload: ResourceCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ResourceResponse:
    company_id = _resolve_company_id(user)
    res = await ResourceService.create_resource(db, company_id, payload)
    return ResourceResponse.model_validate(res)


@router.get(
    "",
    response_model=List[ResourceResponse],
    summary="List Resources",
    description="Lists resources for current tenant company.",
)
async def list_resources(
    resource_type: Optional[str] = Query(None, description="Filter by resource type: human, equipment, vehicle, space"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[ResourceResponse]:
    company_id = _resolve_company_id(user)
    resources = await ResourceService.list_resources(
        db, company_id, resource_type=resource_type, is_active=is_active
    )
    return [ResourceResponse.model_validate(r) for r in resources]


@router.get(
    "/{resource_id}",
    response_model=ResourceResponse,
    summary="Get Resource",
    description="Fetch single resource details by UUID.",
)
async def get_resource(
    resource_id: uuid.UUID = Path(..., description="Resource UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ResourceResponse:
    res = await ResourceService.get_resource(db, resource_id)
    return ResourceResponse.model_validate(res)


@router.patch(
    "/{resource_id}",
    response_model=ResourceResponse,
    summary="Update Resource",
    description="Updates resource parameters, capacity, or active status.",
)
async def update_resource(
    payload: ResourceUpdate,
    resource_id: uuid.UUID = Path(..., description="Resource UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ResourceResponse:
    res = await ResourceService.update_resource(db, resource_id, payload)
    return ResourceResponse.model_validate(res)


@router.delete(
    "/{resource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Resource",
    description="Soft-deletes a resource.",
)
async def delete_resource(
    resource_id: uuid.UUID = Path(..., description="Resource UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await ResourceService.delete_resource(db, resource_id)


# ---------------------------------------------------------------------------
# Availability & Collision Check Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/check-availability",
    response_model=CheckAvailabilityResponse,
    summary="Check Resource Availability",
    description="Detects overlapping bookings and verifies if a resource is available during a given timeframe.",
)
async def check_availability(
    payload: CheckAvailabilityRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CheckAvailabilityResponse:
    company_id = _resolve_company_id(user)
    return await ResourceService.check_availability(db, company_id, payload)


# ---------------------------------------------------------------------------
# Allocation Management Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/allocations",
    response_model=ResourceAllocationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Resource Allocation",
    description="Books capacity on a resource with collision prevention.",
)
async def create_allocation(
    payload: ResourceAllocationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ResourceAllocationResponse:
    company_id = _resolve_company_id(user)
    alloc = await ResourceService.create_allocation(db, company_id, payload)
    return ResourceAllocationResponse.model_validate(alloc)


@router.get(
    "/allocations",
    response_model=List[ResourceAllocationResponse],
    summary="List Resource Allocations",
    description="Lists allocations for current tenant with optional filtering.",
)
async def list_allocations(
    resource_id: Optional[uuid.UUID] = Query(None, description="Filter by resource UUID"),
    status: Optional[str] = Query(None, description="Filter by status (planned, confirmed, completed, cancelled)"),
    res_model: Optional[str] = Query(None, description="Filter by target model"),
    res_id: Optional[uuid.UUID] = Query(None, description="Filter by target entity UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[ResourceAllocationResponse]:
    company_id = _resolve_company_id(user)
    allocs = await ResourceService.list_allocations(
        db, company_id, resource_id=resource_id, status=status, res_model=res_model, res_id=res_id
    )
    return [ResourceAllocationResponse.model_validate(a) for a in allocs]


@router.get(
    "/allocations/{allocation_id}",
    response_model=ResourceAllocationResponse,
    summary="Get Resource Allocation",
    description="Fetch single allocation details by UUID.",
)
async def get_allocation(
    allocation_id: uuid.UUID = Path(..., description="Allocation UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ResourceAllocationResponse:
    alloc = await ResourceService.get_allocation(db, allocation_id)
    return ResourceAllocationResponse.model_validate(alloc)


@router.patch(
    "/allocations/{allocation_id}",
    response_model=ResourceAllocationResponse,
    summary="Update Resource Allocation",
    description="Update timing, allocated hours, status, or notes.",
)
async def update_allocation(
    payload: ResourceAllocationUpdate,
    allocation_id: uuid.UUID = Path(..., description="Allocation UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ResourceAllocationResponse:
    alloc = await ResourceService.update_allocation(db, allocation_id, payload)
    return ResourceAllocationResponse.model_validate(alloc)


@router.delete(
    "/allocations/{allocation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Resource Allocation",
    description="Deletes a resource allocation.",
)
async def delete_allocation(
    allocation_id: uuid.UUID = Path(..., description="Allocation UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await ResourceService.delete_allocation(db, allocation_id)
