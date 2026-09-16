"""Declarative workflow state machine and execution log data models."""

import uuid
from typing import Optional, Dict, Any, List
from sqlalchemy import String, Boolean, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_models import BaseModel


class WorkflowDefinition(BaseModel):
    """Configuration defining a state machine lifecycle for a specific business entity model."""

    __tablename__ = "workflow_definitions"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    res_model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    state_field: Mapped[str] = mapped_column(String(50), default="state", nullable=False)
    initial_state: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    states: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="Ordered list of state descriptors: [{'code': 'draft', 'label': 'Draft', 'is_frozen': false}]",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    transitions: Mapped[List["WorkflowTransition"]] = relationship(
        "WorkflowTransition",
        back_populates="workflow",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="WorkflowTransition.sequence",
    )

    __table_args__ = (
        UniqueConstraint("company_id", "res_model", "code", name="uq_workflow_model_code"),
    )


class WorkflowTransition(BaseModel):
    """Allowed state transition triggered by an action button or API trigger."""

    __tablename__ = "workflow_transitions"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trigger_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    from_state: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Source state code or '*' for transitions permitted from any state",
    )
    to_state: Mapped[str] = mapped_column(String(50), nullable=False)
    required_permission: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Optional RBAC permission required to trigger transition (e.g. 'sales:approve')",
    )
    guard_condition: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        default=None,
        nullable=True,
        comment="Universal AST condition expression evaluated in-memory before allowing transition",
    )
    freeze_record: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether transitioning to destination state marks record as immutable/frozen",
    )
    sequence: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    # Relationships
    workflow: Mapped["WorkflowDefinition"] = relationship(
        "WorkflowDefinition",
        back_populates="transitions",
    )


class WorkflowExecutionLog(BaseModel):
    """Audit trail recording historical state transitions executed on business entities."""

    __tablename__ = "workflow_execution_logs"

    workflow_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_definitions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    transition_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    res_model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    res_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    from_state: Mapped[str] = mapped_column(String(50), nullable=False)
    to_state: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_name: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    metadata_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        default=dict,
        nullable=True,
    )
