"""Pydantic schemas for Document Attachments."""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class DocumentAttachmentRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "doc00000-0000-0000-0000-000000000001",
                "company_id": "a0000000-0000-0000-0000-000000000001",
                "name": "signed_contract_2026.pdf",
                "file_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "file_size": 245760,
                "mime_type": "application/pdf",
                "storage_path": "a0000000-0000-0000-0000-000000000001/e3/e3b0c442...",
                "res_model": "contract",
                "res_id": "c0000000-0000-0000-0000-000000000001",
                "description": "Executed SLA contract signed by client CEO",
                "created_at": "2026-09-14T02:30:00Z"
            }
        }
    )

    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    file_hash: str
    file_size: int
    mime_type: str
    storage_path: str
    res_model: Optional[str]
    res_id: Optional[uuid.UUID]
    description: Optional[str]
    created_at: datetime


class DocumentAttachmentUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "revised_contract_v2.pdf",
                "description": "Updated attachment description"
            }
        }
    )

    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
