"""SQLAlchemy models for Universal Product & Item Master Data."""

import uuid
from decimal import Decimal
from typing import Optional, List
import sqlalchemy as sa
from sqlalchemy import (
    String,
    Text,
    Boolean,
    Numeric,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_models import BaseModel, CategorizableMixin


from modules.base.lookups.models import Category


class Product(BaseModel, CategorizableMixin):
    """Universal enterprise catalog item and inventory product definition."""

    __tablename__ = "products"

    code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        doc="Internal SKU, item reference, or barcode (e.g. PROD-00001)",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        doc="Display name of the product or service",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Detailed specification, marketing description, or procurement notes",
    )
    product_type: Mapped[str] = mapped_column(
        String(32),
        default="storable",
        nullable=False,
        index=True,
        doc="Product classification: 'storable', 'consumable', 'service'",
    )
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lookup_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Hierarchical product category",
    )
    uom_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uom_units.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        doc="Default unit of measure for inventory and sales",
    )
    purchase_uom_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uom_units.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Default unit of measure for procurement and vendor bills",
    )
    sale_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        default=Decimal("0.0000"),
        nullable=False,
        doc="Standard list sales price in company base currency",
    )
    cost_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        default=Decimal("0.0000"),
        nullable=False,
        doc="Standard purchase / inventory cost in company base currency",
    )
    sale_tax_ids: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
        server_default=sa.text("'[]'::jsonb"),
        nullable=False,
        doc="List of default customer sales tax UUID strings",
    )
    purchase_tax_ids: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
        server_default=sa.text("'[]'::jsonb"),
        nullable=False,
        doc="List of default vendor purchase tax UUID strings",
    )
    income_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        doc="Default General Ledger revenue account UUID",
    )
    expense_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        doc="Default General Ledger expense / COGS account UUID",
    )
    is_saleable: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        doc="Flag indicating if item can be sold on customer quotations and sales orders",
    )
    is_purchasable: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        doc="Flag indicating if item can be purchased on RFQs and purchase orders",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        doc="Operational visibility toggle",
    )

    # Relationships
    category: Mapped[Optional["Category"]] = relationship(
        "Category",
        foreign_keys=[category_id],
        lazy="selectin",
    )
    uom: Mapped["UOMUnit"] = relationship(
        "UOMUnit",
        foreign_keys=[uom_id],
        lazy="selectin",
    )
    purchase_uom: Mapped[Optional["UOMUnit"]] = relationship(
        "UOMUnit",
        foreign_keys=[purchase_uom_id],
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_products_company_code"),
    )
