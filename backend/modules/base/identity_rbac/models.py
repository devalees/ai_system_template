"""Database models for Users, Groups, Permissions, and Contextual RBAC."""

import uuid
from typing import Optional, List
from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
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
    email_domain: Mapped[Optional[str]] = mapped_column(String(100), default=None, nullable=True)
    currency_id: Mapped[Optional[str]] = mapped_column(String(3), default="USD", nullable=True)

    __guarded_fields__ = ["email_domain", "currency_id"]


class User(BaseModel):
    """User account entity representing human employees and first-class AI agents."""
    __tablename__ = "users"

    __guarded_fields__ = ["two_factor_secret", "two_factor_recovery_codes"]

    email: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)

    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    user_type: Mapped[str] = mapped_column(String(20), default="human", nullable=False)  # "human" | "ai_agent"
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_primary_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    two_factor_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    two_factor_secret: Mapped[Optional[str]] = mapped_column(String(255), default=None, nullable=True)
    two_factor_recovery_codes: Mapped[Optional[List[str]]] = mapped_column(JSONB, default=None, nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), default=None, nullable=True)


class Group(BaseModel):
    """RBAC Role/Group collecting capabilities for users."""
    __tablename__ = "groups"

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(200), default="", nullable=True)
    group_type: Mapped[str] = mapped_column(String(20), default="role", nullable=False)  # "role" | "department" | "custom"


class Permission(BaseModel):
    """Granular capability with 3-tier ownership scope and optional field-level targeting."""
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)  # e.g. "sales.order.read" or "sales.order.discount:write"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    module_name: Mapped[str] = mapped_column(String(50), index=True, nullable=False)  # e.g. "sales"
    resource: Mapped[str] = mapped_column(String(50), index=True, nullable=False)  # e.g. "order"
    action: Mapped[str] = mapped_column(String(20), index=True, nullable=False)  # "read" | "create" | "update" | "delete" | "manage" | "approve" | "export"
    ownership_scope: Mapped[str] = mapped_column(String(20), default="GLOBAL", nullable=False)  # "GLOBAL", "TEAM", "OWN"
    permission_type: Mapped[str] = mapped_column(String(20), default="model", nullable=False)  # "model" | "field"
    field_name: Mapped[Optional[str]] = mapped_column(String(50), default=None, nullable=True)  # target field e.g. "discount"


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


class UserPermissionLink(BaseModel):
    """Direct user permission override (grant or explicit revocation) defeating role explosion."""
    __tablename__ = "user_permission_links"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    permission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False)
    is_granted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

