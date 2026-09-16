"""Pydantic schemas for Multi-Level Governance and Approval Engine."""

import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict


class ApprovalRuleBase(BaseModel):
    """Base schema for approval rule configuration."""
    name: str = Field(..., max_length=100, description="Descriptive title of approval rule")
    code: str = Field(..., max_length=50, description="Unique code for rule within company")
    res_model: str = Field(..., max_length=100, description="Target entity model name (e.g. 'party', 'invoice')")
    tier: int = Field(default=1, ge=1, description="Sequential tier level (1, 2, 3...)")
    condition: Optional[Dict[str, Any]] = Field(
        None, description="Universal AST filter criteria evaluated against entity attributes to trigger approval"
    )
    approver_group_id: Optional[uuid.UUID] = Field(
        None, description="Optional RBAC group ID authorized to review this tier"
    )
    approver_user_id: Optional[uuid.UUID] = Field(
        None, description="Optional specific user ID designated as tier approver"
    )
    is_active: bool = Field(default=True, description="Whether rule is operational")


class ApprovalRuleCreate(ApprovalRuleBase):
    """Schema for registering a new approval rule."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "High Credit Limit Sign-off",
                "code": "rule_high_credit",
                "res_model": "party",
                "tier": 1,
                "condition": {
                    "field": "credit_limit",
                    "operator": "gt",
                    "value": 50000.0,
                },
                "approver_group_id": None,
                "approver_user_id": None,
                "is_active": True,
            }
        }
    )


class ApprovalRuleUpdate(BaseModel):
    """Schema for updating an existing approval rule."""
    name: Optional[str] = Field(None, max_length=100)
    tier: Optional[int] = Field(None, ge=1)
    condition: Optional[Dict[str, Any]] = None
    approver_group_id: Optional[uuid.UUID] = None
    approver_user_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Executive Credit Limit Sign-off",
                "tier": 2,
            }
        }
    )


class ApprovalRuleResponse(ApprovalRuleBase):
    """Response schema for approval rule."""
    id: uuid.UUID
    company_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "11111111-1111-1111-1111-111111111111",
                "company_id": "00000000-0000-0000-0000-000000000001",
                "name": "High Credit Limit Sign-off",
                "code": "rule_high_credit",
                "res_model": "party",
                "tier": 1,
                "condition": {"field": "credit_limit", "operator": "gt", "value": 50000.0},
                "approver_group_id": None,
                "approver_user_id": None,
                "is_active": True,
                "created_at": "2026-09-16T12:00:00Z",
                "updated_at": "2026-09-16T12:00:00Z",
            }
        },
    )


class ApprovalActionResponse(BaseModel):
    """Response schema for an executed approval or rejection action."""
    id: uuid.UUID
    request_id: uuid.UUID
    actor_id: Optional[uuid.UUID]
    action: str
    comments: Optional[str]
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "22222222-2222-2222-2222-222222222222",
                "request_id": "33333333-3333-3333-3333-333333333333",
                "actor_id": "44444444-4444-4444-4444-444444444444",
                "action": "approve",
                "comments": "Credit assessment verified against commercial registration.",
                "created_at": "2026-09-16T12:00:00Z",
            }
        },
    )


class ApprovalRequestCreate(BaseModel):
    """Request payload to initiate an approval ticket for an entity."""
    res_model: str = Field(..., max_length=100, description="Target entity model name")
    res_id: uuid.UUID = Field(..., description="Target record UUID")
    summary: Optional[str] = Field(None, max_length=255, description="Brief justification for request")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "res_model": "party",
                "res_id": "55555555-5555-5555-5555-555555555555",
                "summary": "Customer requested 100k credit limit expansion",
            }
        }
    )


class ApprovalRequestResponse(BaseModel):
    """Response schema representing an approval request and its action trail."""
    id: uuid.UUID
    company_id: uuid.UUID
    rule_id: Optional[uuid.UUID]
    res_model: str
    res_id: uuid.UUID
    requested_by_id: Optional[uuid.UUID]
    approver_group_id: Optional[uuid.UUID]
    approver_user_id: Optional[uuid.UUID]
    tier: int
    state: str
    summary: Optional[str]
    target_snapshot: Optional[Dict[str, Any]]
    actions: List[ApprovalActionResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "33333333-3333-3333-3333-333333333333",
                "company_id": "00000000-0000-0000-0000-000000000001",
                "rule_id": "11111111-1111-1111-1111-111111111111",
                "res_model": "party",
                "res_id": "55555555-5555-5555-5555-555555555555",
                "requested_by_id": "66666666-6666-6666-6666-666666666666",
                "approver_group_id": None,
                "approver_user_id": None,
                "tier": 1,
                "state": "pending",
                "summary": "Customer requested 100k credit limit expansion",
                "target_snapshot": {"credit_limit": 100000.0},
                "actions": [],
                "created_at": "2026-09-16T12:00:00Z",
                "updated_at": "2026-09-16T12:00:00Z",
            }
        },
    )


class ApprovalDecisionRequest(BaseModel):
    """Request payload to approve or reject a ticket."""
    comments: Optional[str] = Field(None, description="Audited commentary or justification for decision")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "comments": "Approved based on Q3 audited financial balance sheet.",
            }
        }
    )


class ApprovalDecisionResponse(BaseModel):
    """Response representing result of an approval decision."""
    request_id: uuid.UUID
    res_model: str
    res_id: uuid.UUID
    state: str
    action: str
    actor_id: Optional[uuid.UUID]
    comments: Optional[str]
    action_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "request_id": "33333333-3333-3333-3333-333333333333",
                "res_model": "party",
                "res_id": "55555555-5555-5555-5555-555555555555",
                "state": "approved",
                "action": "approve",
                "actor_id": "44444444-4444-4444-4444-444444444444",
                "comments": "Approved based on Q3 audited financial balance sheet.",
                "action_time": "2026-09-16T12:00:00Z",
            }
        }
    )
