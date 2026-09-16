"""SQLAlchemy models for Payment Terms, Methods & Transactions."""

import uuid
from decimal import Decimal
from datetime import datetime, timezone
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
from modules.base.lookups.models import Currency


class PaymentMethod(BaseModel):
    """Supported payment instruments (Bank Transfer, Credit Card, Cash, Cheque)."""

    __tablename__ = "payment_methods"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_payment_methods_company_code"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    method_type: Mapped[str] = mapped_column(String(30), default="manual", nullable=False)  # manual, electronic, bank, cash
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None, nullable=True)


class PaymentTerms(BaseModel):
    """Configurable payment schedules, installment plans, and due date rules."""

    __tablename__ = "payment_terms"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_payment_terms_company_code"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    lines: Mapped[List["PaymentTermsLine"]] = relationship(
        "PaymentTermsLine",
        back_populates="terms",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PaymentTermsLine.sequence",
    )


class PaymentTermsLine(BaseModel):
    """Installment breakdown calculation rules within a payment term."""

    __tablename__ = "payment_terms_lines"

    terms_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payment_terms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    value_type: Mapped[str] = mapped_column(String(20), default="balance", nullable=False)  # percent, fixed, balance
    value: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0000"), nullable=False)
    days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    option: Mapped[str] = mapped_column(String(30), default="days_after_invoice", nullable=False)  # days_after_invoice, end_of_month, days_after_end_of_month

    terms: Mapped["PaymentTerms"] = relationship(
        "PaymentTerms",
        back_populates="lines",
        lazy="selectin",
    )


class PaymentTransaction(BaseModel):
    """Audited commercial payment record with ledger status lifecycle."""

    __tablename__ = "payment_transactions"
    __table_args__ = (
        UniqueConstraint("company_id", "payment_number", name="uq_payment_transactions_company_number"),
    )

    payment_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    res_model: Mapped[Optional[str]] = mapped_column(String(100), default=None, nullable=True, index=True)
    res_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), default=None, nullable=True, index=True)
    party_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), default=None, nullable=True, index=True)

    payment_method_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payment_methods.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    transaction_type: Mapped[str] = mapped_column(String(20), default="inbound", nullable=False)  # inbound, outbound
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lookup_currencies.id", ondelete="SET NULL"),
        default=None,
        nullable=True,
    )
    payment_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(100), default=None, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)  # draft, cleared, reconciled, cancelled
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None, nullable=True)

    payment_method: Mapped["PaymentMethod"] = relationship(
        "PaymentMethod",
        lazy="selectin",
    )

    @property
    def payment_method_name(self) -> Optional[str]:
        if "payment_method" in self.__dict__ and self.payment_method:
            return self.payment_method.name
        return None

