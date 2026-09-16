"""SQLAlchemy model for foreign exchange rates."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Numeric, Date, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_models import BaseModel
from modules.base.lookups.models import Currency


class ExchangeRate(BaseModel):
    """Historical or daily exchange rate between two ISO-4217 currencies."""
    __tablename__ = "fx_exchange_rates"

    from_currency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lookup_currencies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_currency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lookup_currencies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    inverse_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)  # "manual" | "central_bank" | "ecb" | "cbe"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "from_currency_id",
            "to_currency_id",
            "effective_date",
            name="uq_fx_rate_pair_date",
        ),
    )

    from_currency: Mapped[Currency] = relationship("Currency", foreign_keys=[from_currency_id], lazy="selectin")
    to_currency: Mapped[Currency] = relationship("Currency", foreign_keys=[to_currency_id], lazy="selectin")
