"""Immutable audit trail database model."""

import uuid
from typing import Optional, Dict, Any
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.base_models import Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin


class AuditLog(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    """Immutable audit trail record capturing entity state diffs and actor attribution."""
    __tablename__ = "audit_logs"

    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    actor_type: Mapped[str] = mapped_column(String(20), default="human", nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # CREATE | UPDATE | DELETE | RESTORE
    changes: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
