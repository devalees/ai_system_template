"""Pydantic request and response schemas for Chatter."""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict


class MailMessageCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "body": "Financial audit passed successfully without discrepancy.",
                "message_type": "comment",
                "metadata_info": {"confidence": 0.99, "agent_model": "hermes-3"}
            }
        }
    )

    body: str = Field(..., min_length=1, description="Message text content formatted in Markdown")
    message_type: Literal["comment", "notification", "ai_finding", "activity"] = Field(
        "comment", description="Category: user comment, system notification, AI finding, or task log"
    )
    metadata_info: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata attributes")


class MailMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    res_model: str
    res_id: uuid.UUID
    body: str
    message_type: str
    author_id: Optional[uuid.UUID]
    author_type: str
    metadata_info: Dict[str, Any]
    created_at: datetime


class ActivityCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "summary": "Conduct final contract and tax audit review",
                "activity_type": "review",
                "assigned_to_id": "u0000000-0000-0000-0000-000000000001",
                "due_date": "2026-09-20T17:00:00Z"
            }
        }
    )

    summary: str = Field(..., min_length=1, max_length=255, description="Brief title of scheduled action")
    activity_type: Literal["todo", "call", "meeting", "review"] = Field(
        "todo", description="Operational nature of activity"
    )
    assigned_to_id: Optional[uuid.UUID] = Field(None, description="Target assignee user or agent UUID")
    due_date: Optional[datetime] = Field(None, description="Deadline timestamp")


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    res_model: str
    res_id: uuid.UUID
    summary: str
    activity_type: str
    assigned_to_id: Optional[uuid.UUID]
    due_date: Optional[datetime]
    is_completed: bool
    completed_at: Optional[datetime]
    created_at: datetime
