"""SQLAlchemy models for Resource Scheduling & Capacity Allocation."""

import uuid
from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String,
    Text,
    Boolean,
    Numeric,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_models import BaseModel
from modules.base.identity_rbac.models import User


class Resource(BaseModel):
    """Universal enterprise schedulable entity (personnel, equipment, vehicle, conference space)."""

    __tablename__ = "resources"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_resources_company_code"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(20), default="human", nullable=False)  # human, equipment, vehicle, space
    capacity_per_day: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("8.00"), nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
        nullable=True,
        index=True,
    )
    cost_per_hour: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None, nullable=True)

    allocations: Mapped[List["ResourceAllocation"]] = relationship(
        "ResourceAllocation",
        back_populates="resource",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ResourceAllocation(BaseModel):
    """Time-bounded capacity booking linked to tasks, projects, or work items."""

    __tablename__ = "resource_allocations"

    resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    res_model: Mapped[Optional[str]] = mapped_column(String(100), default=None, nullable=True, index=True)
    res_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), default=None, nullable=True, index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    hours_allocated: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="planned", nullable=False, index=True)  # planned, confirmed, completed, cancelled
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None, nullable=True)

    resource: Mapped["Resource"] = relationship(
        "Resource",
        back_populates="allocations",
        lazy="selectin",
    )

    @property
    def resource_name(self) -> Optional[str]:
        if "resource" in self.__dict__ and self.resource:
            return self.resource.name
        return None
