"""Pydantic response schemas for Audit Trails."""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "log00000-0000-0000-0000-000000000001",
                "company_id": "a0000000-0000-0000-0000-000000000001",
                "actor_id": "u0000000-0000-0000-0000-000000000001",
                "actor_type": "human",
                "model_name": "Invoice",
                "record_id": "inv00000-0000-0000-0000-000000000001",
                "action": "UPDATE",
                "changes": {
                    "status": {"old": "draft", "new": "posted"},
                    "total_amount": {"old": "1000.00", "new": "1150.00"}
                },
                "ip_address": "192.168.1.50",
                "created_at": "2026-09-14T02:00:00Z"
            }
        }
    )

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
