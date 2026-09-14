"""Database models for backup archives and restore checkpoints."""

from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.base_models import BaseModel


class BackupRecord(BaseModel):
    """Archival backup bundle record with checksum and content telemetry."""
    __tablename__ = "backup_records"

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)  # pending | generating | completed | failed | restored
    backup_type: Mapped[str] = mapped_column(String(30), default="full", nullable=False)  # full | database_only | filestore_only
    includes_filestore: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    details: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
