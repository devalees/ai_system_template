"""SQLAlchemy models for Unit of Measure & Conversion Matrix."""

import uuid
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import (
    String,
    Text,
    Boolean,
    Numeric,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_models import BaseModel


class UOMCategory(BaseModel):
    """Categorical classification of measurement units (e.g. Weight, Volume, Length, Unit, Time)."""

    __tablename__ = "uom_categories"

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None, nullable=True)

    units: Mapped[List["UOMUnit"]] = relationship(
        "UOMUnit",
        back_populates="category",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_uom_category_company_name"),
    )


class UOMUnit(BaseModel):
    """Standardized measurement unit with type and ratio relative to its category reference unit."""

    __tablename__ = "uom_units"

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uom_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    symbol: Mapped[Optional[str]] = mapped_column(String(20), default=None, nullable=True)

    # uom_type: reference (base anchor, ratio=1.0), bigger (>1.0 of ref), smaller (<1.0 of ref, stored as ratio>1 e.g. 1000g=1kg)
    uom_type: Mapped[str] = mapped_column(String(20), default="reference", nullable=False)
    ratio: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("1.00000000"), nullable=False)
    rounding_precision: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0.010000"), nullable=False)

    category: Mapped["UOMCategory"] = relationship("UOMCategory", back_populates="units")

    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_uom_unit_company_code"),
        Index("ix_uom_unit_company_category", "company_id", "category_id"),
    )


class UOMConversionRule(BaseModel):
    """Explicit or cross-category conversion rule (e.g. density-based 1L Olive Oil = 0.92 kg)."""

    __tablename__ = "uom_conversion_rules"

    from_uom_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uom_units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_uom_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uom_units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ratio: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)  # 1 from_uom = ratio * to_uom

    # Optional item/product specificity
    res_model: Mapped[Optional[str]] = mapped_column(String(100), default=None, nullable=True, index=True)
    res_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), default=None, nullable=True, index=True
    )

    from_uom: Mapped["UOMUnit"] = relationship("UOMUnit", foreign_keys=[from_uom_id], lazy="selectin")
    to_uom: Mapped["UOMUnit"] = relationship("UOMUnit", foreign_keys=[to_uom_id], lazy="selectin")

    __table_args__ = (
        Index("ix_uom_conversion_pair", "company_id", "from_uom_id", "to_uom_id"),
        Index("ix_uom_conversion_item", "company_id", "res_model", "res_id"),
    )
