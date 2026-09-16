"""Enterprise Sales Order Management Declarative Models."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional, List, Dict
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from core.base_models import BaseModel


class SaleOrder(BaseModel):
    """Customer Quotation and Confirmed Sales Order header."""

    __tablename__ = "sales_orders"

    order_number: Mapped[str] = mapped_column(
        sa.String(64),
        default="Draft",
        nullable=False,
        index=True,
        doc="e.g. SO/2026/00001 or 'Draft'",
    )
    party_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("parties.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        doc="Customer party",
    )
    order_date: Mapped[date] = mapped_column(sa.Date, nullable=False, index=True)
    currency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("lookup_currencies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    payment_term_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("payment_terms.id", ondelete="SET NULL"),
        nullable=True,
    )
    state: Mapped[str] = mapped_column(
        sa.String(16),
        default="draft",
        nullable=False,
        index=True,
        doc="State: draft, sent, sale, done, cancelled",
    )
    invoice_status: Mapped[str] = mapped_column(
        sa.String(16),
        default="to_invoice",
        nullable=False,
        index=True,
        doc="Status: no, to_invoice, invoiced",
    )
    amount_untaxed: Mapped[Decimal] = mapped_column(
        sa.Numeric(18, 4), default=Decimal("0.0000"), nullable=False
    )
    amount_tax: Mapped[Decimal] = mapped_column(
        sa.Numeric(18, 4), default=Decimal("0.0000"), nullable=False
    )
    amount_total: Mapped[Decimal] = mapped_column(
        sa.Numeric(18, 4), default=Decimal("0.0000"), nullable=False
    )
    analytic_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("accounting_analytic_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("accounting_moves.id", ondelete="SET NULL"),
        nullable=True,
    )

    lines: Mapped[List["SaleOrderLine"]] = relationship(
        "SaleOrderLine",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="SaleOrderLine.created_at",
    )


class SaleOrderLine(BaseModel):
    """Line item in a customer Sales Order."""

    __tablename__ = "sales_order_lines"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("sales_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        sa.Numeric(18, 4), default=Decimal("1.0000"), nullable=False
    )
    uom_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("uom_units.id", ondelete="SET NULL"),
        nullable=True,
    )
    unit_price: Mapped[Decimal] = mapped_column(
        sa.Numeric(18, 4), default=Decimal("0.0000"), nullable=False
    )
    discount_percent: Mapped[float] = mapped_column(sa.Float, default=0.0, nullable=False)
    tax_ids: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
        server_default=sa.text("'[]'::jsonb"),
        nullable=False,
    )
    price_subtotal: Mapped[Decimal] = mapped_column(
        sa.Numeric(18, 4), default=Decimal("0.0000"), nullable=False
    )
    price_total: Mapped[Decimal] = mapped_column(
        sa.Numeric(18, 4), default=Decimal("0.0000"), nullable=False
    )
    analytic_distribution: Mapped[Dict[str, float]] = mapped_column(
        JSONB,
        default=dict,
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
    )

    order: Mapped["SaleOrder"] = relationship("SaleOrder", back_populates="lines")
