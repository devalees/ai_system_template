"""Pydantic schemas and DTOs for Resource Scheduling & Capacity Allocation."""

import uuid
from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Resource Schemas
# ---------------------------------------------------------------------------

class ResourceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Resource display title")
    code: str = Field(..., min_length=1, max_length=50, description="Unique reference code")
    resource_type: str = Field(
        "human",
        pattern="^(human|equipment|vehicle|space)$",
        description="Type: human, equipment, vehicle, or space",
    )
    capacity_per_day: Decimal = Field(Decimal("8.00"), gt=0, description="Standard working hours per day")
    user_id: Optional[uuid.UUID] = Field(None, description="Linked user account for human resources")
    cost_per_hour: Decimal = Field(Decimal("0.00"), ge=0, description="Standard hourly cost")
    description: Optional[str] = Field(None, description="Operational specifications")


class ResourceCreate(ResourceBase):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Senior Solutions Architect",
                "code": "RES_ARCH_01",
                "resource_type": "human",
                "capacity_per_day": "8.00",
                "cost_per_hour": "120.00",
                "description": "Technical design and architecture lead",
            }
        }
    )


class ResourceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    resource_type: Optional[str] = Field(None, pattern="^(human|equipment|vehicle|space)$")
    capacity_per_day: Optional[Decimal] = Field(None, gt=0)
    user_id: Optional[uuid.UUID] = None
    cost_per_hour: Optional[Decimal] = Field(None, ge=0)
    is_active: Optional[bool] = None
    description: Optional[str] = None


class ResourceResponse(ResourceBase):
    id: uuid.UUID
    company_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Resource Allocation Schemas
# ---------------------------------------------------------------------------

class ResourceAllocationBase(BaseModel):
    resource_id: uuid.UUID = Field(..., description="Target resource UUID")
    res_model: Optional[str] = Field(None, max_length=100, description="Target entity model (e.g. 'work_items')")
    res_id: Optional[uuid.UUID] = Field(None, description="Target record UUID")
    start_time: datetime = Field(..., description="Booking start timestamp with timezone")
    end_time: datetime = Field(..., description="Booking end timestamp with timezone")
    hours_allocated: Decimal = Field(..., gt=0, description="Committed duration in hours")
    notes: Optional[str] = Field(None, description="Booking notes")

    @model_validator(mode="after")
    def validate_times(self):
        if self.start_time >= self.end_time:
            raise ValueError("end_time must be strictly greater than start_time.")
        return self


class ResourceAllocationCreate(ResourceAllocationBase):
    allow_overbooking: bool = Field(False, description="Whether to bypass collision prevention")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "resource_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
                "res_model": "work_items",
                "start_time": "2026-09-17T09:00:00Z",
                "end_time": "2026-09-17T17:00:00Z",
                "hours_allocated": "8.00",
                "allow_overbooking": False,
                "notes": "Sprint planning session",
            }
        }
    )


class ResourceAllocationUpdate(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    hours_allocated: Optional[Decimal] = Field(None, gt=0)
    status: Optional[str] = Field(None, pattern="^(planned|confirmed|completed|cancelled)$")
    notes: Optional[str] = None


class ResourceAllocationResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    resource_id: uuid.UUID
    resource_name: Optional[str] = None
    res_model: Optional[str] = None
    res_id: Optional[uuid.UUID] = None
    start_time: datetime
    end_time: datetime
    hours_allocated: Decimal
    status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Availability & Collision Check Schemas
# ---------------------------------------------------------------------------

class CheckAvailabilityRequest(BaseModel):
    resource_id: uuid.UUID = Field(..., description="Target resource UUID")
    start_time: datetime = Field(..., description="Desired booking start")
    end_time: datetime = Field(..., description="Desired booking end")
    exclude_allocation_id: Optional[uuid.UUID] = Field(None, description="Optional allocation to exclude (e.g. self when editing)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "resource_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
                "start_time": "2026-09-17T09:00:00Z",
                "end_time": "2026-09-17T17:00:00Z",
            }
        }
    )


class ConflictingAllocationItem(BaseModel):
    allocation_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    hours_allocated: Decimal
    status: str
    res_model: Optional[str] = None
    res_id: Optional[uuid.UUID] = None


class CheckAvailabilityResponse(BaseModel):
    resource_id: uuid.UUID
    resource_name: str
    is_available: bool = Field(..., description="True if no overlapping confirmed/planned allocations exist")
    conflicts_count: int
    conflicts: List[ConflictingAllocationItem]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "resource_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
                "resource_name": "Senior Solutions Architect",
                "is_available": True,
                "conflicts_count": 0,
                "conflicts": [],
            }
        }
    )
