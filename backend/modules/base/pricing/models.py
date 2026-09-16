"""SQLAlchemy models for Pricing Engine & Multi-Tier Price Lists."""

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
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_models import BaseModel
from modules.base.lookups.models import Currency


class PriceList(BaseModel):
    """Catalog of pricing policies, volume break tiers, and commercial discount schedules."""

    __tablename__ = "pricing_lists"

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None, nullable=True)

    currency_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lookup_currencies.id", ondelete="SET NULL"),
        default=None,
        nullable=True,
    )

    currency: Mapped[Optional[Currency]] = relationship("Currency", lazy="selectin")
    items: Mapped[List["PriceListItem"]] = relationship(
        "PriceListItem",
        back_populates="price_list",
        cascade="all, delete-orphan",
        order_by="PriceListItem.sequence.asc()",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_pricing_list_company_code"),
    )


class PriceListItem(BaseModel):
    """Specific pricing rule, tier, or promotional discount line attached to a PriceList."""

    __tablename__ = "pricing_list_items"

    price_list_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pricing_lists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Scope of applicability: all (global to price list), category, or product
    applied_on: Mapped[str] = mapped_column(String(20), default="all", nullable=False)
    res_model: Mapped[Optional[str]] = mapped_column(String(100), default=None, nullable=True, index=True)
    res_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), default=None, nullable=True, index=True
    )

    # Minimum threshold quantity for tiered volume discounts
    min_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("1.0000"), nullable=False)

    # Pricing calculation mode: fixed, percentage_discount, formula
    pricing_mode: Mapped[str] = mapped_column(String(30), default="percentage_discount", nullable=False)

    # Parameters
    fixed_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), default=None, nullable=True)
    discount_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), default=None, nullable=True)
    formula_markup_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), default=None, nullable=True)
    formula_surcharge: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), default=None, nullable=True)

    # Validity window for seasonal or temporary promotions
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None, nullable=True)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None, nullable=True)

    sequence: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    price_list: Mapped["PriceList"] = relationship("PriceList", back_populates="items")

    __table_args__ = (
        Index("ix_pricing_items_lookup", "company_id", "price_list_id", "applied_on", "res_model", "res_id"),
        Index("ix_pricing_items_dates", "company_id", "valid_from", "valid_to"),
    )
