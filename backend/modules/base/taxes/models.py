"""SQLAlchemy models for Tax Engine & Fiscal Positions."""

import uuid
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import (
    String,
    Text,
    Boolean,
    Numeric,
    Integer,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_models import BaseModel
from modules.base.lookups.models import Country


class Tax(BaseModel):
    """Universal tax definition supporting standard, inclusive, compound, and fixed taxes."""

    __tablename__ = "taxes"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_taxes_company_code"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    tax_scope: Mapped[str] = mapped_column(String(20), default="sales", nullable=False)  # 'sales', 'purchase', 'none'
    calculation_type: Mapped[str] = mapped_column(String(20), default="percent", nullable=False)  # 'percent', 'fixed', 'division'
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0000"), nullable=False)
    is_inclusive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    include_base_amount: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=10, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None, nullable=True)


class TaxFiscalPosition(BaseModel):
    """Fiscal position mapping tax rules by jurisdiction, domestic/export status, or partner profile."""

    __tablename__ = "tax_fiscal_positions"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_fiscal_positions_company_code"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    auto_apply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    country_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lookup_countries.id", ondelete="SET NULL"),
        default=None,
        nullable=True,
    )
    vat_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, default=None, nullable=True)

    rules: Mapped[List["TaxFiscalPositionRule"]] = relationship(
        "TaxFiscalPositionRule",
        back_populates="fiscal_position",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class TaxFiscalPositionRule(BaseModel):
    """Tax substitution rule replacing source taxes with destination taxes or tax exemption."""

    __tablename__ = "tax_fiscal_position_rules"

    position_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tax_fiscal_positions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_tax_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("taxes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dest_tax_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("taxes.id", ondelete="SET NULL"),
        default=None,
        nullable=True,
        index=True,
    )

    fiscal_position: Mapped["TaxFiscalPosition"] = relationship(
        "TaxFiscalPosition",
        back_populates="rules",
        lazy="selectin",
    )
    source_tax: Mapped["Tax"] = relationship(
        "Tax",
        foreign_keys=[source_tax_id],
        lazy="selectin",
    )
    dest_tax: Mapped[Optional["Tax"]] = relationship(
        "Tax",
        foreign_keys=[dest_tax_id],
        lazy="selectin",
    )

    @property
    def source_tax_name(self) -> Optional[str]:
        if "source_tax" in self.__dict__ and self.source_tax:
            return self.source_tax.name
        return None

    @property
    def dest_tax_name(self) -> Optional[str]:
        if "dest_tax" in self.__dict__ and self.dest_tax:
            return self.dest_tax.name
        return None

