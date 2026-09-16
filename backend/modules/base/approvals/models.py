"""Multi-Level Governance and Approval Engine data models."""

import uuid
from typing import Optional, Dict, Any, List
from sqlalchemy import String, Boolean, Integer, Text, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_models import BaseModel


class ApprovalRule(BaseModel):
    """Declarative criteria defining tiered approval obligations for specific business models."""

    __tablename__ = "approval_rules"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    res_model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tier: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        comment="Sequential approval level hierarchy (1 = Supervisor, 2 = Department Head, 3 = CFO)",
    )
    condition: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        default=None,
        nullable=True,
        comment="Universal AST filter criteria evaluated against entity attributes to trigger rule",
    )
    approver_group_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("groups.id", ondelete="SET NULL"),
        default=None,
        nullable=True,
        index=True,
    )
    approver_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("company_id", "res_model", "code", name="uq_approval_rule_code"),
    )


class ApprovalRequest(BaseModel):
    """Pending, approved, or rejected approval ticket bound to an operational entity."""

    __tablename__ = "approval_requests"

    rule_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("approval_rules.id", ondelete="SET NULL"),
        default=None,
        nullable=True,
        index=True,
    )
    res_model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    res_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    requested_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
        nullable=True,
        index=True,
    )
    approver_group_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("groups.id", ondelete="SET NULL"),
        default=None,
        nullable=True,
        index=True,
    )
    approver_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
        nullable=True,
        index=True,
    )
    tier: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    state: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        index=True,
        comment="Approval lifecycle state: pending, approved, rejected, cancelled",
    )
    summary: Mapped[Optional[str]] = mapped_column(String(255), default=None, nullable=True)
    target_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        default=dict,
        nullable=True,
    )

    # Relationships
    rule: Mapped[Optional["ApprovalRule"]] = relationship("ApprovalRule", lazy="selectin")
    actions: Mapped[List["ApprovalAction"]] = relationship(
        "ApprovalAction",
        back_populates="request",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ApprovalAction.created_at.desc()",
    )


class ApprovalAction(BaseModel):
    """Individual sign-off or rejection decision recorded in the governance audit trail."""

    __tablename__ = "approval_actions"

    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("approval_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Decision outcome: approve, reject, cancel",
    )
    comments: Mapped[Optional[str]] = mapped_column(Text, default=None, nullable=True)

    # Relationships
    request: Mapped["ApprovalRequest"] = relationship("ApprovalRequest", back_populates="actions")
