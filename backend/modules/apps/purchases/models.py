"""Enterprise Purchases & Procurement Declarative Models."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional, List, Dict
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from core.base_models import BaseModel


class PurchaseOrder(BaseModel):
    """Vendor Request for Quotation (RFQ) and Confirmed Purchase Order header."""

    __tablename__ = "purchase_orders"

    order_number: Mapped[str] = mapped_column(
        sa.String(64),
        default="Draft",
        nullable=False,
        index=True,
        doc="e.g. PO/2026/00001 or 'Draft'",
    )
    party_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("parties.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        doc="Vendor party",
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
        doc="State: draft, sent, to_approve, purchase, done, cancelled",
    )
    bill_status: Mapped[str] = mapped_column(
        sa.String(16),
        default="to_bill",
        nullable=False,
        index=True,
        doc="Status: no, to_bill, billed",
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
    bill_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("accounting_moves.id", ondelete="SET NULL"),
        nullable=True,
    )

    lines: Mapped[List["PurchaseOrderLine"]] = relationship(
        "PurchaseOrderLine",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="PurchaseOrderLine.created_at",
    )


class PurchaseOrderLine(BaseModel):
    """Line item in a vendor Purchase Order."""

    __tablename__ = "purchase_order_lines"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Optional catalog product linkage",
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

    order: Mapped["PurchaseOrder"] = relationship("PurchaseOrder", back_populates="lines")
