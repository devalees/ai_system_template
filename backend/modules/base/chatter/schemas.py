"""Pydantic request and response schemas for Chatter."""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class MailMessageCreate(BaseModel):
    body: str = Field(..., min_length=1)
    message_type: Literal["comment", "notification", "ai_finding", "activity"] = "comment"
    metadata_info: Dict[str, Any] = Field(default_factory=dict)


class MailMessageRead(BaseModel):
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
    summary: str = Field(..., min_length=1, max_length=255)
    activity_type: Literal["todo", "call", "meeting", "review"] = "todo"
    assigned_to_id: Optional[uuid.UUID] = None
    due_date: Optional[datetime] = None


class ActivityRead(BaseModel):
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
