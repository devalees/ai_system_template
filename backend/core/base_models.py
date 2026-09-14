"""Declarative base models, mixins, and multi-tenancy primitives for SQLAlchemy 2.0."""

import uuid
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy import DateTime, Boolean, text, event
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from core.context import get_active_company_id, get_current_user_id


class Base(DeclarativeBase):
    """Declarative Base class for all Sovereign Platform SQLAlchemy models."""
    pass


class UUIDPrimaryKeyMixin:
    """Provides non-enumerable UUID primary key."""
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    def __init__(self, **kwargs):
        if "id" not in kwargs:
            kwargs["id"] = uuid.uuid4()
        super().__init__(**kwargs)


class TimestampMixin:
    """Standardized creation and modification audit timestamps."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class AuditActorMixin:
    """Tracks the identity of users or AI agents responsible for record creation and updates."""
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        default=None,
        nullable=True,
    )
    updated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        default=None,
        nullable=True,
    )


class TenantMixin:
    """Enforces multi-tenancy data isolation via company_id."""
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )


class ExtensibleModelMixin:
    """Provides dynamic custom attributes via PostgreSQL JSONB with GIN index."""
    custom_fields: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )

    def get_custom_field(self, key: str, default: Any = None) -> Any:
        """Get value from custom_fields dict."""
        return (self.custom_fields or {}).get(key, default)

    def set_custom_field(self, key: str, value: Any) -> None:
        """Set value in custom_fields dict."""
        if self.custom_fields is None:
            self.custom_fields = {}
        self.custom_fields[key] = value


class ArchivableMixin:
    """Provides operational active/inactive toggle."""
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )


class SoftDeleteMixin:
    """Provides paranoid soft-delete capabilities with kernel auto-filtration."""
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        default=None,
        nullable=True,
        index=True,
    )
    deleted_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        default=None,
        nullable=True,
    )

    @property
    def is_deleted(self) -> bool:
        """Check if record is marked as soft-deleted."""
        return self.deleted_at is not None

    def soft_delete(self, user_id: Optional[uuid.UUID] = None) -> None:
        """Mark record as soft-deleted."""
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by_id = user_id or get_current_user_id()

    def restore(self) -> None:
        """Restore a soft-deleted record."""
        self.deleted_at = None
        self.deleted_by_id = None


class BaseModel(
    Base,
    UUIDPrimaryKeyMixin,
    TenantMixin,
    TimestampMixin,
    AuditActorMixin,
    ExtensibleModelMixin,
    SoftDeleteMixin,
    ArchivableMixin,
):
    """Canonical abstract base model for all multi-tenant enterprise business entities."""

    __abstract__ = True

    def __init__(self, **kwargs):
        # Auto-populate company_id from context if not provided
        if "company_id" not in kwargs:
            active_comp = get_active_company_id()
            if active_comp:
                kwargs["company_id"] = active_comp
        # Auto-populate created_by_id from context if not provided
        if "created_by_id" not in kwargs:
            curr_user = get_current_user_id()
            if curr_user:
                kwargs["created_by_id"] = curr_user
        super().__init__(**kwargs)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize model instance attributes to a dictionary."""
        result = {}
        for column in self.__table__.columns:
            val = getattr(self, column.name)
            if isinstance(val, uuid.UUID):
                result[column.name] = str(val)
            elif isinstance(val, datetime):
                result[column.name] = val.isoformat()
            else:
                result[column.name] = val
        return result
