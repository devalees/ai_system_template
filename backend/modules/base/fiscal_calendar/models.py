"""SQLAlchemy data models for Fiscal Years and Fiscal Accounting Periods."""

import uuid
from datetime import date
from typing import List
from sqlalchemy import String, Boolean, Date, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_models import BaseModel


class FiscalYear(BaseModel):
    """Annual financial accounting year governing period boundaries and annual closing."""
    __tablename__ = "fiscal_years"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_fiscal_year_company_code"),
    )

    periods: Mapped[List["FiscalPeriod"]] = relationship(
        "FiscalPeriod",
        back_populates="fiscal_year",
        cascade="all, delete-orphan",
        order_by="FiscalPeriod.date_from",
        lazy="selectin",
    )


class FiscalPeriod(BaseModel):
    """Sub-annual operational accounting period (monthly, quarterly) with state locking."""
    __tablename__ = "fiscal_periods"

    fiscal_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fiscal_years.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    date_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    date_to: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_type: Mapped[str] = mapped_column(String(20), default="month", nullable=False)  # "month" | "quarter" | "opening" | "closing"
    state: Mapped[str] = mapped_column(String(20), default="open", nullable=False, index=True)  # "open" | "closing" | "locked"

    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_fiscal_period_company_code"),
    )

    fiscal_year: Mapped["FiscalYear"] = relationship(
        "FiscalYear",
        back_populates="periods",
    )
