"""Database models for master data and lookups."""

import uuid
from typing import Optional, List
from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_models import BaseModel


class Country(BaseModel):
    """Normalized master record for sovereign nations and territories."""
    __tablename__ = "lookup_countries"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_company_country_code"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    code_alpha2: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    dialing_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    currency_code: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)


class City(BaseModel):
    """Normalized master record for cities and municipalities."""
    __tablename__ = "lookup_cities"

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    country_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lookup_countries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    state_or_province: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    country: Mapped["Country"] = relationship("Country", backref="cities", lazy="selectin")


class Currency(BaseModel):
    """Master records for ISO-4217 currencies and exchange anchors."""
    __tablename__ = "lookup_currencies"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_company_currency_code"),
    )

    code: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    decimal_places: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    is_base: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class UnitOfMeasure(BaseModel):
    """Standardized measurement units (weight, volume, count, dimension)."""
    __tablename__ = "lookup_uom"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_company_uom_code"),
    )

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), default="unit", nullable=False)
    rounding_precision: Mapped[float] = mapped_column(Float, default=0.01, nullable=False)


class TaxType(BaseModel):
    """Configurable tax definitions (VAT, Sales Tax, Withholding, Zero-rate)."""
    __tablename__ = "lookup_tax_types"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_company_tax_code"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_inclusive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Tag(BaseModel):
    """Categorization tags attached to diverse entity types across the platform."""
    __tablename__ = "lookup_tags"
    __table_args__ = (
        UniqueConstraint("company_id", "name", "model_target", name="uq_company_tag_target"),
    )

    name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    color: Mapped[str] = mapped_column(String(20), default="#3b82f6", nullable=False)
    model_target: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)


class Category(BaseModel):
    """Universal hierarchical category taxonomy supporting nested sub-classifications."""
    __tablename__ = "lookup_categories"
    __table_args__ = (
        UniqueConstraint("company_id", "res_model", "code", name="uq_company_category_scope_code"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    res_model: Mapped[str] = mapped_column(String(100), default="general", nullable=False, index=True)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lookup_categories.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    color: Mapped[str] = mapped_column(String(20), default="#3b82f6", nullable=False)
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, default=10, nullable=False, index=True)

    parent: Mapped[Optional["Category"]] = relationship(
        "Category",
        remote_side="Category.id",
        back_populates="children",
        lazy="selectin",
    )
    children: Mapped[List["Category"]] = relationship(
        "Category",
        back_populates="parent",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Category.sequence",
    )
