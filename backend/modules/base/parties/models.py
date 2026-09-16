"""SQLAlchemy models for Universal Party (Customer/Vendor/Partner) and Child Contacts."""

import uuid
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import String, Boolean, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_models import BaseModel
from modules.base.lookups.models import Currency
from modules.base.identity_rbac.models import Company


class Party(BaseModel):
    """Unified Partner entity representing Customers, Vendors, and Corporate Hierarchies."""
    __tablename__ = "parties"

    # Identity & Entity Type
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    legal_name: Mapped[Optional[str]] = mapped_column(String(200), default=None, nullable=True)
    is_company: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Corporate Hierarchy (Holding / Subsidiary / Branch)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("parties.id", ondelete="SET NULL"),
        default=None,
        nullable=True,
        index=True,
    )

    # Commercial Roles & Dual Identity (OASIS / Odoo Standard)
    is_customer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_vendor: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_employee: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Regulatory & Fiscal Identifiers
    tax_id: Mapped[Optional[str]] = mapped_column(String(50), default=None, nullable=True, index=True)
    commercial_reg_no: Mapped[Optional[str]] = mapped_column(String(50), default=None, nullable=True)

    # Financial Terms & Credit
    currency_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lookup_currencies.id", ondelete="SET NULL"),
        default=None,
        nullable=True,
    )
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)

    # Inter-Company Linkage (Connecting Party identity in Company A to internal Tenant Company B)
    linked_company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="SET NULL"),
        default=None,
        nullable=True,
        index=True,
    )

    # Primary Direct Contact Info
    email: Mapped[Optional[str]] = mapped_column(String(150), default=None, nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), default=None, nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(200), default=None, nullable=True)

    # Relational Links
    parent: Mapped[Optional["Party"]] = relationship(
        "Party",
        remote_side="Party.id",
        backref="subsidiaries",
        lazy="selectin",
    )
    contacts: Mapped[List["PartyContact"]] = relationship(
        "PartyContact",
        back_populates="party",
        cascade="all, delete-orphan",
        order_by="PartyContact.is_primary.desc()",
        lazy="selectin",
    )
    currency: Mapped[Optional[Currency]] = relationship("Currency", lazy="selectin")
    linked_company: Mapped[Optional[Company]] = relationship(
        "Company", foreign_keys=[linked_company_id], lazy="selectin"
    )


class PartyContact(BaseModel):
    """Individual human representative or contact person associated with a Party."""
    __tablename__ = "party_contacts"

    party_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("parties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    job_title: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(150), default=None, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), default=None, nullable=True)
    mobile: Mapped[Optional[str]] = mapped_column(String(50), default=None, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    party: Mapped["Party"] = relationship("Party", back_populates="contacts")
