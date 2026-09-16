"""SQLAlchemy models for Contracts, Agreements & Subscriptions."""

import uuid
from decimal import Decimal
from datetime import date
from typing import Optional, List
from sqlalchemy import (
    String,
    Text,
    Boolean,
    Numeric,
    Integer,
    Date,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_models import BaseModel
from modules.base.parties.models import Party
from modules.base.lookups.models import Currency


class Contract(BaseModel):
    """Commercial legal agreement, subscription schedule, or master service contract."""

    __tablename__ = "contracts"
    __table_args__ = (
        UniqueConstraint("company_id", "sequence_number", name="uq_contracts_company_sequence"),
    )

    sequence_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    party_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("parties.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    contract_type: Mapped[str] = mapped_column(
        String(30), default="customer", nullable=False, index=True
    )  # customer, vendor, employment, lease, subscription
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, default=None, nullable=True)
    billing_frequency: Mapped[str] = mapped_column(
        String(30), default="monthly", nullable=False
    )  # one_off, monthly, quarterly, semi_annual, annual
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    currency_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lookup_currencies.id", ondelete="SET NULL"),
        default=None,
        nullable=True,
    )
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notice_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    state: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False, index=True
    )  # draft, active, expired, terminated, cancelled
    terms_and_conditions: Mapped[Optional[str]] = mapped_column(Text, default=None, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None, nullable=True)

    party: Mapped["Party"] = relationship(
        "Party",
        lazy="selectin",
    )
    currency: Mapped[Optional["Currency"]] = relationship(
        "Currency",
        lazy="selectin",
    )
    lines: Mapped[List["ContractLine"]] = relationship(
        "ContractLine",
        back_populates="contract",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def party_name(self) -> Optional[str]:
        if "party" in self.__dict__ and self.party:
            return self.party.name
        return None


class ContractLine(BaseModel):
    """Deliverable line item, service scope, or product component within a contract."""

    __tablename__ = "contract_lines"

    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("1.0000"), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0000"), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0000"), nullable=False)

    contract: Mapped["Contract"] = relationship(
        "Contract",
        back_populates="lines",
        lazy="selectin",
    )
