"""Pydantic request and response schemas for Automated Actions & TCA Engine."""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, Field

from modules.base.automated_actions.models import TriggerType, ExecutionMode, ActionExecutionStatus


class ActionHandlerMeta(BaseModel):
    """Self-describing metadata for an action handler including its JSON Schema."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "action_type": "send_email",
                "title": "Send Email",
                "description": "Dispatch dynamic transactional email using the Mail Gateway.",
                "config_schema": {"properties": {"template_code": {"type": "string"}}},
            }
        }
    )

    action_type: str = Field(..., description="Unique action handler identifier")
    title: str = Field(..., description="Human-readable title")
    description: str = Field(..., description="Description of the action handler capability")
    config_schema: Dict[str, Any] = Field(default_factory=dict, description="JSON Schema of required/optional parameters")


class AutomatedActionBase(BaseModel):
    """Base fields for an automated action rule."""
    name: str = Field(..., min_length=2, max_length=150, description="Descriptive rule name")
    description: Optional[str] = Field(None, description="Optional administrative notes or explanation")
    target_model: str = Field(..., max_length=100, description="Canonical model name (e.g. 'User', 'DocumentAttachment')")
    trigger_type: TriggerType = Field(default=TriggerType.ON_CREATE, description="Trigger event lifecycle hook")
    watched_fields: Optional[List[str]] = Field(None, description="List of field names to watch for on_update triggers")
    condition_tree: Optional[Dict[str, Any]] = Field(None, description="Universal AST filter group evaluating condition")
    action_type: str = Field(..., max_length=50, description="Identifier of registered action handler")
    action_config: Dict[str, Any] = Field(default_factory=dict, description="Parameters passed to action handler")
    execution_mode: ExecutionMode = Field(default=ExecutionMode.ASYNC_CELERY, description="SYNC or ASYNC_CELERY")
    sequence: int = Field(default=10, ge=0, le=1000, description="Execution priority order")
    is_active: bool = Field(default=True, description="Whether this automation rule is active")


class AutomatedActionCreate(AutomatedActionBase):
    """Payload for creating a new automated action rule."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Send Welcome Email on User Signup",
                "description": "Automatically enqueue welcome verification email when a new human user registers.",
                "target_model": "User",
                "trigger_type": "on_create",
                "watched_fields": None,
                "condition_tree": {
                    "logic": "AND",
                    "filters": [
                        {"field": "user_type", "operator": "eq", "value": "human"},
                        {"field": "is_active", "operator": "eq", "value": True}
                    ]
                },
                "action_type": "send_email",
                "action_config": {
                    "template_code": "WELCOME_VERIFICATION",
                    "recipient_field": "email"
                },
                "execution_mode": "async_celery",
                "sequence": 10,
                "is_active": True
            }
        }
    )


class AutomatedActionUpdate(BaseModel):
    """Payload for updating an existing automated action rule."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Send Welcome Email on User Signup (Updated)",
                "is_active": True,
                "sequence": 5
            }
        }
    )

    name: Optional[str] = Field(None, min_length=2, max_length=150)
    description: Optional[str] = None
    target_model: Optional[str] = Field(None, max_length=100)
    trigger_type: Optional[TriggerType] = None
    watched_fields: Optional[List[str]] = None
    condition_tree: Optional[Dict[str, Any]] = None
    action_type: Optional[str] = Field(None, max_length=50)
    action_config: Optional[Dict[str, Any]] = None
    execution_mode: Optional[ExecutionMode] = None
    sequence: Optional[int] = Field(None, ge=0, le=1000)
    is_active: Optional[bool] = None


class AutomatedActionRead(AutomatedActionBase):
    """Response representation of an automated action rule."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ActionExecutionLogRead(BaseModel):
    """Response representation of an action execution audit log entry."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    action_id: Optional[uuid.UUID] = None
    action_name: str
    target_model: str
    target_id: uuid.UUID
    trigger_type: str
    condition_matched: bool
    status: str
    execution_duration_ms: float
    error_message: Optional[str] = None
    execution_context: Optional[Dict[str, Any]] = None
    created_at: datetime


class ConditionTestRequest(BaseModel):
    """Request payload to test a condition tree against a live record."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "target_model": "User",
                "target_id": "6b4550dd-f558-418e-b506-95e26eeda277",
                "condition_tree": {
                    "logic": "AND",
                    "filters": [
                        {"field": "username", "operator": "eq", "value": "admin"}
                    ]
                }
            }
        }
    )

    target_model: str = Field(..., description="Target model name")
    target_id: uuid.UUID = Field(..., description="Target record UUID to evaluate against")
    condition_tree: Dict[str, Any] = Field(..., description="Universal AST condition tree to test")


class ConditionTestResponse(BaseModel):
    """Result of testing a condition tree against a live record."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "matched": True,
                "target_model": "User",
                "target_id": "6b4550dd-f558-418e-b506-95e26eeda277",
                "evaluated_record": {"username": "admin", "is_active": True}
            }
        }
    )

    matched: bool
    target_model: str
    target_id: uuid.UUID
    evaluated_record: Dict[str, Any]


# ---------------- Model & Field Introspection Schemas ----------------
class ModelIntrospectionItem(BaseModel):
    """Metadata summary of a registered ORM model."""
    model_name: str = Field(..., description="ORM model class name (e.g. 'User', 'DocumentAttachment')")
    module_name: str = Field(..., description="Module namespace that owns the model")
    table_name: str = Field(..., description="Physical PostgreSQL table name")
    title: str = Field(..., description="Human-friendly model title")
    description: Optional[str] = Field(None, description="Model docstring or description")
    is_tenant_scoped: bool = Field(..., description="True if model enforces multi-tenant company_id isolation")
    fields_count: int = Field(..., description="Number of columns defined on this model")


class FieldIntrospectionItem(BaseModel):
    """Detailed metadata for a single model field/column."""
    name: str = Field(..., description="Column/field name")
    title: str = Field(..., description="Human-friendly field title")
    type: str = Field(..., description="Normalized field data type (string, integer, float, boolean, uuid, datetime, date, json, enum)")
    nullable: bool = Field(..., description="Whether database column accepts null values")
    required: bool = Field(..., description="Whether field is strictly required when creating records via automation")
    read_only: bool = Field(..., description="Whether field is read-only (primary keys, audit timestamps)")
    is_relation: bool = Field(..., description="Whether field is a foreign key relationship")
    foreign_model: Optional[str] = Field(None, description="Target foreign model class name if relation")
    foreign_table: Optional[str] = Field(None, description="Target foreign table name if relation")
    foreign_column: Optional[str] = Field(None, description="Target foreign column name if relation")
    choices: Optional[List[Dict[str, Any]]] = Field(None, description="Allowed choices if enum type")
    default: Optional[str] = Field(None, description="Default value if configured")


class ModelFieldsIntrospectionResponse(BaseModel):
    """Complete field specification for a queried model."""
    model_name: str
    module_name: str
    table_name: str
    title: str
    description: Optional[str] = None
    fields: List[FieldIntrospectionItem]
