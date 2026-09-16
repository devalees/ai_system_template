"""Business logic and collision detection engine for Resource Scheduling & Capacity Allocation."""

import uuid
from typing import Optional, List
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import EntityNotFoundException, ValidationException
from modules.base.resources.models import Resource, ResourceAllocation
from modules.base.resources.schemas import (
    ResourceCreate,
    ResourceUpdate,
    ResourceAllocationCreate,
    ResourceAllocationUpdate,
    CheckAvailabilityRequest,
    CheckAvailabilityResponse,
    ConflictingAllocationItem,
)


class ResourceService:
    """Enterprise scheduling engine managing resource availability, allocations, and collision guards."""

    # -----------------------------------------------------------------------
    # Resource CRUD
    # -----------------------------------------------------------------------

    @classmethod
    async def create_resource(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        payload: ResourceCreate,
    ) -> Resource:
        """Create new schedulable resource."""
        res = Resource(
            company_id=company_id,
            name=payload.name,
            code=payload.code,
            resource_type=payload.resource_type,
            capacity_per_day=payload.capacity_per_day,
            user_id=payload.user_id,
            cost_per_hour=payload.cost_per_hour,
            description=payload.description,
            is_active=True,
        )
        db.add(res)
        await db.commit()
        await db.refresh(res)
        return res

    @classmethod
    async def get_resource(
        cls,
        db: AsyncSession,
        resource_id: uuid.UUID,
    ) -> Resource:
        """Fetch resource by ID."""
        stmt = select(Resource).where(Resource.id == resource_id)
        result = await db.execute(stmt)
        res = result.scalar_one_or_none()
        if not res:
            raise EntityNotFoundException("Resource", resource_id)
        return res

    @classmethod
    async def list_resources(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        resource_type: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[Resource]:
        """List resources for tenant company."""
        stmt = select(Resource).where(Resource.company_id == company_id)
        if resource_type:
            stmt = stmt.where(Resource.resource_type == resource_type)
        if is_active is not None:
            stmt = stmt.where(Resource.is_active == is_active)
        stmt = stmt.order_by(Resource.name.asc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def update_resource(
        cls,
        db: AsyncSession,
        resource_id: uuid.UUID,
        payload: ResourceUpdate,
    ) -> Resource:
        """Update resource parameters."""
        res = await cls.get_resource(db, resource_id)
        for field, val in payload.model_dump(exclude_unset=True).items():
            setattr(res, field, val)
        await db.commit()
        await db.refresh(res)
        return res

    @classmethod
    async def delete_resource(
        cls,
        db: AsyncSession,
        resource_id: uuid.UUID,
    ) -> bool:
        """Soft-delete resource."""
        res = await cls.get_resource(db, resource_id)
        await db.delete(res)
        await db.commit()
        return True

    # -----------------------------------------------------------------------
    # Availability & Collision Detection
    # -----------------------------------------------------------------------

    @classmethod
    async def check_availability(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        payload: CheckAvailabilityRequest,
    ) -> CheckAvailabilityResponse:
        """Check for time slot overlaps and calculate availability conflicts."""
        resource = await cls.get_resource(db, payload.resource_id)
        if resource.company_id != company_id:
            raise ValidationException("Resource does not belong to active company.")

        # Collision query: start_time < candidate_end AND end_time > candidate_start
        stmt = select(ResourceAllocation).where(
            ResourceAllocation.company_id == company_id,
            ResourceAllocation.resource_id == payload.resource_id,
            ResourceAllocation.status.in_(["planned", "confirmed"]),
            ResourceAllocation.start_time < payload.end_time,
            ResourceAllocation.end_time > payload.start_time,
        )
        if payload.exclude_allocation_id:
            stmt = stmt.where(ResourceAllocation.id != payload.exclude_allocation_id)

        result = await db.execute(stmt)
        overlapping = list(result.scalars().all())

        conflicts = [
            ConflictingAllocationItem(
                allocation_id=alloc.id,
                start_time=alloc.start_time,
                end_time=alloc.end_time,
                hours_allocated=alloc.hours_allocated,
                status=alloc.status,
                res_model=alloc.res_model,
                res_id=alloc.res_id,
            )
            for alloc in overlapping
        ]

        return CheckAvailabilityResponse(
            resource_id=resource.id,
            resource_name=resource.name,
            is_available=len(conflicts) == 0,
            conflicts_count=len(conflicts),
            conflicts=conflicts,
        )

    # -----------------------------------------------------------------------
    # Resource Allocation Management
    # -----------------------------------------------------------------------

    @classmethod
    async def create_allocation(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        payload: ResourceAllocationCreate,
    ) -> ResourceAllocation:
        """Book resource capacity with automated collision guard."""
        # 1. Collision check if overbooking is not explicitly allowed
        if not payload.allow_overbooking:
            check_req = CheckAvailabilityRequest(
                resource_id=payload.resource_id,
                start_time=payload.start_time,
                end_time=payload.end_time,
            )
            avail = await cls.check_availability(db, company_id, check_req)
            if not avail.is_available:
                raise ValidationException(
                    f"Resource collision detected: '{avail.resource_name}' has {avail.conflicts_count} overlapping booking(s)."
                )

        alloc = ResourceAllocation(
            company_id=company_id,
            resource_id=payload.resource_id,
            res_model=payload.res_model,
            res_id=payload.res_id,
            start_time=payload.start_time,
            end_time=payload.end_time,
            hours_allocated=payload.hours_allocated,
            status="planned",
            notes=payload.notes,
        )
        db.add(alloc)
        await db.commit()
        stmt = (
            select(ResourceAllocation)
            .where(ResourceAllocation.id == alloc.id)
            .options(selectinload(ResourceAllocation.resource))
        )
        res = await db.execute(stmt)
        return res.scalar_one()

    @classmethod
    async def get_allocation(
        cls,
        db: AsyncSession,
        allocation_id: uuid.UUID,
    ) -> ResourceAllocation:
        """Fetch allocation by ID."""
        stmt = (
            select(ResourceAllocation)
            .where(ResourceAllocation.id == allocation_id)
            .options(selectinload(ResourceAllocation.resource))
        )
        result = await db.execute(stmt)
        alloc = result.scalar_one_or_none()
        if not alloc:
            raise EntityNotFoundException("ResourceAllocation", allocation_id)
        return alloc

    @classmethod
    async def list_allocations(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        resource_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        res_model: Optional[str] = None,
        res_id: Optional[uuid.UUID] = None,
    ) -> List[ResourceAllocation]:
        """List allocations for tenant company with flexible filters."""
        stmt = (
            select(ResourceAllocation)
            .where(ResourceAllocation.company_id == company_id)
            .options(selectinload(ResourceAllocation.resource))
        )
        if resource_id:
            stmt = stmt.where(ResourceAllocation.resource_id == resource_id)
        if status:
            stmt = stmt.where(ResourceAllocation.status == status)
        if res_model:
            stmt = stmt.where(ResourceAllocation.res_model == res_model)
        if res_id:
            stmt = stmt.where(ResourceAllocation.res_id == res_id)
        stmt = stmt.order_by(ResourceAllocation.start_time.asc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def update_allocation(
        cls,
        db: AsyncSession,
        allocation_id: uuid.UUID,
        payload: ResourceAllocationUpdate,
    ) -> ResourceAllocation:
        """Update existing allocation timing, status, or notes."""
        alloc = await cls.get_allocation(db, allocation_id)
        for field, val in payload.model_dump(exclude_unset=True).items():
            setattr(alloc, field, val)
        await db.commit()
        return await cls.get_allocation(db, alloc.id)

    @classmethod
    async def delete_allocation(
        cls,
        db: AsyncSession,
        allocation_id: uuid.UUID,
    ) -> bool:
        """Delete allocation."""
        alloc = await cls.get_allocation(db, allocation_id)
        await db.delete(alloc)
        await db.commit()
        return True
