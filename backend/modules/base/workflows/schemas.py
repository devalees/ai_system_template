"""Pydantic request and response schemas for Workflows and State Machine Engine."""

import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict


class WorkflowStateItem(BaseModel):
    """Schema defining an individual state node in a workflow state machine."""
    code: str = Field(..., max_length=50, description="Unique code for the state (e.g. 'draft', 'confirmed')")
    label: str = Field(..., max_length=100, description="Human-readable title (e.g. 'Draft', 'Confirmed')")
    is_frozen: bool = Field(default=False, description="Whether entities in this state are immutable/frozen")
    sequence: int = Field(default=10, ge=0, description="Display sequence order")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "posted",
                "label": "Posted / Finalized",
                "is_frozen": True,
                "sequence": 30,
            }
        }
    )


class WorkflowTransitionBase(BaseModel):
    """Base schema for state transitions."""
    trigger_name: str = Field(..., max_length=50, description="Action or trigger button identifier (e.g. 'post')")
    from_state: str = Field(..., max_length=50, description="Source state code or '*' for any state")
    to_state: str = Field(..., max_length=50, description="Destination state code")
    required_permission: Optional[str] = Field(
        None, max_length=100, description="Optional required RBAC permission (e.g. 'workflow:transition')"
    )
    guard_condition: Optional[Dict[str, Any]] = Field(
        None, description="Optional Universal AST condition dictionary evaluated against entity attributes"
    )
    freeze_record: bool = Field(default=False, description="Whether to lock the record upon executing this transition")
    sequence: int = Field(default=10, ge=0, description="Sequence priority for ordering triggers")


class WorkflowTransitionCreate(WorkflowTransitionBase):
    """Schema for creating a new workflow transition."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "trigger_name": "approve",
                "from_state": "submitted",
                "to_state": "approved",
                "required_permission": "workflow:transition",
                "guard_condition": {
                    "field": "credit_limit",
                    "operator": "gt",
                    "value": 0,
                },
                "freeze_record": False,
                "sequence": 20,
            }
        }
    )


class WorkflowTransitionUpdate(BaseModel):
    """Schema for updating an existing workflow transition."""
    trigger_name: Optional[str] = Field(None, max_length=50)
    from_state: Optional[str] = Field(None, max_length=50)
    to_state: Optional[str] = Field(None, max_length=50)
    required_permission: Optional[str] = Field(None, max_length=100)
    guard_condition: Optional[Dict[str, Any]] = None
    freeze_record: Optional[bool] = None
    sequence: Optional[int] = Field(None, ge=0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "freeze_record": True,
                "sequence": 25,
            }
        }
    )


class WorkflowTransitionResponse(WorkflowTransitionBase):
    """Full schema for a workflow transition response."""
    id: uuid.UUID
    workflow_id: uuid.UUID
    company_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "11111111-1111-1111-1111-111111111111",
                "workflow_id": "22222222-2222-2222-2222-222222222222",
                "company_id": "00000000-0000-0000-0000-000000000001",
                "trigger_name": "post",
                "from_state": "approved",
                "to_state": "posted",
                "required_permission": "workflow:transition",
                "guard_condition": None,
                "freeze_record": True,
                "sequence": 30,
                "created_at": "2026-09-16T12:00:00Z",
                "updated_at": "2026-09-16T12:00:00Z",
            }
        },
    )


class WorkflowDefinitionBase(BaseModel):
    """Base schema for workflow definition attributes."""
    name: str = Field(..., max_length=100, description="Display name of the workflow")
    code: str = Field(..., max_length=50, description="Unique code for this workflow within company")
    res_model: str = Field(..., max_length=100, description="Target entity model name (e.g. 'Party', 'Invoice')")
    state_field: str = Field(default="state", max_length=50, description="Field name storing state on target record")
    initial_state: str = Field(default="draft", max_length=50, description="Initial state code when records are created")
    states: List[WorkflowStateItem] = Field(default_factory=list, description="Ordered list of state descriptors")
    is_active: bool = Field(default=True, description="Whether workflow is operational")


class WorkflowDefinitionCreate(WorkflowDefinitionBase):
    """Schema for registering a new workflow definition."""
    transitions: List[WorkflowTransitionCreate] = Field(
        default_factory=list, description="Initial list of state transitions"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Standard Order Workflow",
                "code": "so_workflow_standard",
                "res_model": "sales_order",
                "state_field": "state",
                "initial_state": "draft",
                "states": [
                    {"code": "draft", "label": "Draft", "is_frozen": False, "sequence": 10},
                    {"code": "confirmed", "label": "Confirmed", "is_frozen": False, "sequence": 20},
                    {"code": "posted", "label": "Posted", "is_frozen": True, "sequence": 30},
                    {"code": "cancelled", "label": "Cancelled", "is_frozen": True, "sequence": 40},
                ],
                "is_active": True,
                "transitions": [
                    {
                        "trigger_name": "confirm",
                        "from_state": "draft",
                        "to_state": "confirmed",
                        "freeze_record": False,
                        "sequence": 10,
                    },
                    {
                        "trigger_name": "post",
                        "from_state": "confirmed",
                        "to_state": "posted",
                        "freeze_record": True,
                        "sequence": 20,
                    },
                    {
                        "trigger_name": "cancel",
                        "from_state": "*",
                        "to_state": "cancelled",
                        "freeze_record": True,
                        "sequence": 30,
                    },
                ],
            }
        }
    )


class WorkflowDefinitionUpdate(BaseModel):
    """Schema for updating an existing workflow definition."""
    name: Optional[str] = Field(None, max_length=100)
    state_field: Optional[str] = Field(None, max_length=50)
    initial_state: Optional[str] = Field(None, max_length=50)
    states: Optional[List[WorkflowStateItem]] = None
    is_active: Optional[bool] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Standard Order Workflow v2",
                "is_active": True,
            }
        }
    )


class WorkflowDefinitionResponse(WorkflowDefinitionBase):
    """Full schema for workflow definition response including transitions."""
    id: uuid.UUID
    company_id: uuid.UUID
    transitions: List[WorkflowTransitionResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "22222222-2222-2222-2222-222222222222",
                "company_id": "00000000-0000-0000-0000-000000000001",
                "name": "Standard Order Workflow",
                "code": "so_workflow_standard",
                "res_model": "sales_order",
                "state_field": "state",
                "initial_state": "draft",
                "states": [
                    {"code": "draft", "label": "Draft", "is_frozen": False, "sequence": 10},
                    {"code": "posted", "label": "Posted", "is_frozen": True, "sequence": 20},
                ],
                "is_active": True,
                "transitions": [],
                "created_at": "2026-09-16T12:00:00Z",
                "updated_at": "2026-09-16T12:00:00Z",
            }
        },
    )


class ExecuteTransitionRequest(BaseModel):
    """Request payload to trigger a state transition on a business entity."""
    trigger_name: str = Field(..., max_length=50, description="Trigger action name (e.g. 'post', 'confirm')")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Optional context metadata recorded in transition log"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "trigger_name": "post",
                "metadata": {"reason": "End-of-month finalization"},
            }
        }
    )


class WorkflowTransitionResult(BaseModel):
    """Result of an executed state transition."""
    res_model: str
    record_id: uuid.UUID
    from_state: str
    to_state: str
    trigger_name: str
    is_frozen: bool
    state_field: str
    transition_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "res_model": "party",
                "record_id": "33333333-3333-3333-3333-333333333333",
                "from_state": "draft",
                "to_state": "posted",
                "trigger_name": "post",
                "is_frozen": True,
                "state_field": "state",
                "transition_time": "2026-09-16T12:00:00Z",
            }
        }
    )


class AvailableTransitionResponse(BaseModel):
    """Available trigger for a given record in its current state."""
    trigger_name: str
    from_state: str
    to_state: str
    freeze_record: bool
    required_permission: Optional[str] = None
    sequence: int = 10

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "trigger_name": "confirm",
                "from_state": "draft",
                "to_state": "confirmed",
                "freeze_record": False,
                "required_permission": "workflow:transition",
                "sequence": 10,
            }
        }
    )


class WorkflowExecutionLogResponse(BaseModel):
    """Audit trail response schema for past workflow state transitions."""
    id: uuid.UUID
    workflow_id: Optional[uuid.UUID]
    transition_id: Optional[uuid.UUID]
    res_model: str
    res_id: uuid.UUID
    from_state: str
    to_state: str
    trigger_name: str
    actor_id: Optional[uuid.UUID]
    metadata_snapshot: Optional[Dict[str, Any]]
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "44444444-4444-4444-4444-444444444444",
                "workflow_id": "22222222-2222-2222-2222-222222222222",
                "transition_id": "11111111-1111-1111-1111-111111111111",
                "res_model": "party",
                "res_id": "33333333-3333-3333-3333-333333333333",
                "from_state": "draft",
                "to_state": "posted",
                "trigger_name": "post",
                "actor_id": "55555555-5555-5555-5555-555555555555",
                "metadata_snapshot": {"state_field": "state", "frozen": True},
                "created_at": "2026-09-16T12:00:00Z",
            }
        },
    )
