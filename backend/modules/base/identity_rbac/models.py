"""Database models for Users, Groups, Permissions, and Contextual RBAC."""

import uuid
from typing import Optional, List
from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_models import (
    Base,
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    AuditActorMixin,
    ExtensibleModelMixin,
    SoftDeleteMixin,
    ArchivableMixin,
    BaseModel,
)


class Company(
    Base,
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    AuditActorMixin,
    ExtensibleModelMixin,
    SoftDeleteMixin,
    ArchivableMixin,
):
    """Tenant company/organization entity governing workspace boundaries and registration policy."""
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    allow_registration: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_domain: Mapped[Optional[str]] = mapped_column(String(100), default=None, nullable=True)
    currency_id: Mapped[Optional[str]] = mapped_column(String(3), default="USD", nullable=True)


class User(BaseModel):
    """User account entity representing human employees and first-class AI agents."""
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    user_type: Mapped[str] = mapped_column(String(20), default="human", nullable=False)  # "human" | "ai_agent"
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    preferred_language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), default=None, nullable=True)


class Group(BaseModel):
    """RBAC Role/Group collecting capabilities for users."""
    __tablename__ = "groups"

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(200), default="", nullable=True)


class Permission(BaseModel):
    """Granular model-level capability with 3-tier ownership scope."""
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)  # e.g. "sales.order.read"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    module_name: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    ownership_scope: Mapped[str] = mapped_column(String(20), default="GLOBAL", nullable=False)  # "GLOBAL", "TEAM", "OWN"


class UserGroupLink(BaseModel):
    """Associates users with RBAC groups."""
    __tablename__ = "user_group_links"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)


class GroupPermissionLink(BaseModel):
    """Associates RBAC groups with permissions."""
    __tablename__ = "group_permission_links"

    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    permission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False)
