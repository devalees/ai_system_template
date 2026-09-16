"""Pydantic schemas and DTOs for Universal Work Items, Tasks & Dependencies."""

import uuid
from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Stage Schemas
# ---------------------------------------------------------------------------

class WorkItemStageBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Stage display title")
    code: str = Field(..., min_length=1, max_length=50, description="Unique reference code")
    sequence: int = Field(10, description="Pipeline sequence order")
    is_closed: bool = Field(False, description="Whether this stage represents a terminal closed state")
    color: str = Field("#3b82f6", max_length=20, description="Hex color badge")
    description: Optional[str] = Field(None, description="Operational guidance for this stage")


class WorkItemStageCreate(WorkItemStageBase):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "In Development",
                "code": "IN_DEV",
                "sequence": 20,
                "is_closed": False,
                "color": "#eab308",
                "description": "Active implementation",
            }
        }
    )


class WorkItemStageUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    sequence: Optional[int] = None
    is_closed: Optional[bool] = None
    color: Optional[str] = None
    description: Optional[str] = None


class WorkItemStageResponse(WorkItemStageBase):
    id: uuid.UUID
    company_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Dependency Schemas
# ---------------------------------------------------------------------------

class WorkItemDependencyCreate(BaseModel):
    predecessor_id: uuid.UUID = Field(..., description="Predecessor task UUID that must be completed first")
    dependency_type: str = Field(
        "finish_to_start",
        pattern="^(finish_to_start|start_to_start|finish_to_finish|start_to_finish)$",
        description="Dependency relationship type",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "predecessor_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
                "dependency_type": "finish_to_start",
            }
        }
    )


class WorkItemDependencyResponse(BaseModel):
    id: uuid.UUID
    predecessor_id: uuid.UUID
    successor_id: uuid.UUID
    dependency_type: str
    predecessor_title: Optional[str] = None
    successor_title: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Work Item Schemas
# ---------------------------------------------------------------------------

class WorkItemBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Task headline or title")
    description: Optional[str] = Field(None, description="Detailed requirements or markdown specifications")
    res_model: Optional[str] = Field(None, max_length=100, description="Parent entity model (e.g. 'projects')")
    res_id: Optional[uuid.UUID] = Field(None, description="Parent entity UUID")
    parent_id: Optional[uuid.UUID] = Field(None, description="Parent task UUID for sub-task hierarchies")
    priority: str = Field("medium", pattern="^(low|medium|high|urgent)$", description="Priority level")
    stage_id: Optional[uuid.UUID] = Field(None, description="Current workflow stage UUID")
    assigned_to_id: Optional[uuid.UUID] = Field(None, description="Assigned user account UUID")
    estimated_hours: Decimal = Field(Decimal("0.00"), ge=0, description="Estimated work hours")
    spent_hours: Decimal = Field(Decimal("0.00"), ge=0, description="Logged work hours")
    due_date: Optional[datetime] = Field(None, description="Target completion deadline")


class WorkItemCreate(WorkItemBase):
    item_number: Optional[str] = Field(None, max_length=50, description="Optional custom task sequence number")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "item_number": "TASK-2026-001",
                "title": "Build Multi-Jurisdiction Tax Calculation Matrix",
                "description": "Implement inclusive vs exclusive rate extraction and compound rules.",
                "priority": "high",
                "estimated_hours": "16.00",
            }
        }
    )


class WorkItemUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None
    priority: Optional[str] = Field(None, pattern="^(low|medium|high|urgent)$")
    stage_id: Optional[uuid.UUID] = None
    assigned_to_id: Optional[uuid.UUID] = None
    estimated_hours: Optional[Decimal] = Field(None, ge=0)
    spent_hours: Optional[Decimal] = Field(None, ge=0)
    due_date: Optional[datetime] = None
    is_closed: Optional[bool] = None


class WorkItemResponse(WorkItemBase):
    id: uuid.UUID
    company_id: uuid.UUID
    item_number: str
    is_closed: bool
    stage_name: Optional[str] = None
    dependencies: List[WorkItemDependencyResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StageTransitionRequest(BaseModel):
    stage_id: uuid.UUID = Field(..., description="Destination stage UUID")


class WorkItemTreeNode(BaseModel):
    id: uuid.UUID
    item_number: str
    title: str
    priority: str
    is_closed: bool
    stage_name: Optional[str] = None
    children: List["WorkItemTreeNode"] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
