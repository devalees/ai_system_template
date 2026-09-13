"""Pydantic response schemas for Audit Trails."""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel


class AuditLogRead(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    actor_id: Optional[uuid.UUID]
    actor_type: str
    model_name: str
    record_id: uuid.UUID
    action: str
    changes: Dict[str, Any]
    ip_address: Optional[str]
    created_at: datetime
