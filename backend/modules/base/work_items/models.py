"""SQLAlchemy models for Universal Work Items, Tasks & Dependencies."""

import uuid
from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String,
    Text,
    Boolean,
    Numeric,
    Integer,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_models import BaseModel
from modules.base.identity_rbac.models import User


class WorkItemStage(BaseModel):
    """Configurable Kanban pipeline stages (Backlog, In Progress, Review, Done)."""

    __tablename__ = "work_item_stages"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_work_item_stages_company_code"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, default=10, nullable=False, index=True)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    color: Mapped[str] = mapped_column(String(20), default="#3b82f6", nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None, nullable=True)


class WorkItem(BaseModel):
    """Universal execution unit supporting hierarchy, cross-model linkage, and stage tracking."""

    __tablename__ = "work_items"
    __table_args__ = (
        UniqueConstraint("company_id", "item_number", name="uq_work_items_company_number"),
    )

    item_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None, nullable=True)

    res_model: Mapped[Optional[str]] = mapped_column(String(100), default=None, nullable=True, index=True)
    res_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), default=None, nullable=True, index=True)

    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_items.id", ondelete="CASCADE"),
        default=None,
        nullable=True,
        index=True,
    )

    priority: Mapped[str] = mapped_column(String(20), default="medium", nullable=False, index=True)  # low, medium, high, urgent
    stage_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_item_stages.id", ondelete="SET NULL"),
        default=None,
        nullable=True,
        index=True,
    )
    assigned_to_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
        nullable=True,
        index=True,
    )

    estimated_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0.00"), nullable=False)
    spent_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0.00"), nullable=False)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None, nullable=True)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    stage: Mapped[Optional["WorkItemStage"]] = relationship(
        "WorkItemStage",
        lazy="selectin",
    )
    parent: Mapped[Optional["WorkItem"]] = relationship(
        "WorkItem",
        remote_side="WorkItem.id",
        back_populates="children",
        lazy="selectin",
    )
    children: Mapped[List["WorkItem"]] = relationship(
        "WorkItem",
        back_populates="parent",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    dependencies: Mapped[List["WorkItemDependency"]] = relationship(
        "WorkItemDependency",
        foreign_keys="WorkItemDependency.successor_id",
        back_populates="successor",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def stage_name(self) -> Optional[str]:
        if "stage" in self.__dict__ and self.stage:
            return self.stage.name
        return None


class WorkItemDependency(BaseModel):
    """Directed dependency graph edge connecting a predecessor task to a successor task."""

    __tablename__ = "work_item_dependencies"
    __table_args__ = (
        UniqueConstraint("predecessor_id", "successor_id", name="uq_work_item_dependency_pair"),
    )

    predecessor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    successor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dependency_type: Mapped[str] = mapped_column(
        String(30), default="finish_to_start", nullable=False
    )  # finish_to_start, start_to_start, finish_to_finish, start_to_finish

    predecessor: Mapped["WorkItem"] = relationship(
        "WorkItem",
        foreign_keys=[predecessor_id],
        lazy="selectin",
    )
    successor: Mapped["WorkItem"] = relationship(
        "WorkItem",
        foreign_keys=[successor_id],
        back_populates="dependencies",
        lazy="selectin",
    )

    @property
    def predecessor_title(self) -> Optional[str]:
        if "predecessor" in self.__dict__ and self.predecessor:
            return self.predecessor.title
        return None

    @property
    def successor_title(self) -> Optional[str]:
        if "successor" in self.__dict__ and self.successor:
            return self.successor.title
        return None
