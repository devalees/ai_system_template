"""Database models for document attachments and content-addressable storage."""

import uuid
from typing import Optional
from sqlalchemy import String, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.base_models import BaseModel, CategorizableMixin


class DocumentAttachment(BaseModel, CategorizableMixin):
    """File attachment record referencing content-addressable storage blobs."""
    __tablename__ = "document_attachments"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), default="application/octet-stream", nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    res_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    res_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
