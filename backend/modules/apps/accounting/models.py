"""Enterprise Financial Accounting & General Ledger Declarative Models."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional, List, Dict, Any
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from core.base_models import BaseModel


# ============================================================================
# 1. Core General Ledger: Accounts & Journals
# ============================================================================

class Account(BaseModel):
    """Hierarchical General Ledger Chart of Accounts."""

    __tablename__ = "accounting_accounts"

    code: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)
    account_type: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        index=True,
        doc="Type: asset_current, asset_non_current, liability_current, liability_non_current, equity, income, expense, expense_depreciation",
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("accounting_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    currency_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("lookup_currencies.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    reconcilable: Mapped[bool] = mapped_column(
        sa.Boolean,
        default=False,
        nullable=False,
        doc="Whether this account allows open-item reconciliation (e.g. AR / AP)",
    )
    is_deprecated: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)

    # Relationships
    parent: Mapped[Optional["Account"]] = relationship(
        "Account", remote_side="Account.id", backref="children"
    )

    __table_args__ = (
        sa.UniqueConstraint("company_id", "code", name="uq_accounting_account_company_code"),
    )


class AccountJournal(BaseModel):
    """Accounting Journals grouping double-entry move transactions."""

    __tablename__ = "accounting_journals"

    code: Mapped[str] = mapped_column(sa.String(16), nullable=False, index=True)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    type: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        index=True,
        doc="Journal type: sale, purchase, bank, cash, general",
    )
    default_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("accounting_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    sequence_code: Mapped[str] = mapped_column(
        sa.String(64),
        default="account.general",
        nullable=False,
        doc="Target sequence code for legal auto-numbering",
    )

    __table_args__ = (
        sa.UniqueConstraint("company_id", "code", name="uq_accounting_journal_company_code"),
    )


# ============================================================================
# 2. Double-Entry Moves, Invoices & Journal Items
# ============================================================================

class AccountMove(BaseModel):
    """Double-entry Journal Move, Customer Invoice, or Vendor Bill header."""

    __tablename__ = "accounting_moves"

    name: Mapped[str] = mapped_column(
        sa.String(64),
        default="Draft",
        nullable=False,
        index=True,
        doc="Legal document number, e.g. INV/2026/00001 or 'Draft'",
    )
    move_type: Mapped[str] = mapped_column(
        sa.String(32),
        default="entry",
        nullable=False,
        index=True,
        doc="Type: entry, out_invoice, out_refund, in_invoice, in_refund",
    )
    date: Mapped[date] = mapped_column(sa.Date, nullable=False, index=True)
    ref: Mapped[Optional[str]] = mapped_column(sa.String(255), nullable=True)
    journal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("accounting_journals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    party_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("parties.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    currency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("lookup_currencies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    state: Mapped[str] = mapped_column(
        sa.String(16),
        default="draft",
        nullable=False,
        index=True,
        doc="State: draft, posted, cancelled",
    )
    amount_total: Mapped[Decimal] = mapped_column(
        sa.Numeric(18, 4),
        default=Decimal("0.0000"),
        nullable=False,
    )
    amount_residual: Mapped[Decimal] = mapped_column(
        sa.Numeric(18, 4),
        default=Decimal("0.0000"),
        nullable=False,
        doc="Remaining unpaid amount",
    )
    payment_term_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("payment_terms.id", ondelete="SET NULL"),
        nullable=True,
    )
    fiscal_period_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("fiscal_periods.id", ondelete="SET NULL"),
        nullable=True,
    )
    invoice_date_due: Mapped[Optional[date]] = mapped_column(sa.Date, nullable=True)

    # Relationships
    journal: Mapped["AccountJournal"] = relationship("AccountJournal")
    lines: Mapped[List["AccountMoveLine"]] = relationship(
        "AccountMoveLine",
        back_populates="move",
        cascade="all, delete-orphan",
        order_by="AccountMoveLine.created_at",
    )


class AccountMoveLine(BaseModel):
    """Balanced Double-Entry Journal Line."""

    __tablename__ = "accounting_move_lines"

    move_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("accounting_moves.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("accounting_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    party_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("parties.id", ondelete="RESTRICT"),
        nullable=True,
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
    debit: Mapped[Decimal] = mapped_column(
        sa.Numeric(18, 4),
        default=Decimal("0.0000"),
        nullable=False,
    )
    credit: Mapped[Decimal] = mapped_column(
        sa.Numeric(18, 4),
        default=Decimal("0.0000"),
        nullable=False,
    )
    balance: Mapped[Decimal] = mapped_column(
        sa.Numeric(18, 4),
        default=Decimal("0.0000"),
        nullable=False,
        doc="Debit minus Credit",
    )
    amount_currency: Mapped[Optional[Decimal]] = mapped_column(
        sa.Numeric(18, 4),
        nullable=True,
    )
    currency_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("lookup_currencies.id", ondelete="RESTRICT"),
        nullable=True,
    )
    reconciled: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False, index=True)
    matching_number: Mapped[Optional[str]] = mapped_column(
        sa.String(64),
        nullable=True,
        index=True,
        doc="Group matching hash linking reconciled lines",
    )
    tax_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("taxes.id", ondelete="SET NULL"),
        nullable=True,
    )
    analytic_distribution: Mapped[Dict[str, float]] = mapped_column(
        JSONB,
        default=dict,
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
        doc="Percentage split across analytic accounts, e.g. {'account_uuid': 100.0}",
    )

    # Relationships
    move: Mapped["AccountMove"] = relationship("AccountMove", back_populates="lines")
    account: Mapped["Account"] = relationship("Account")


# ============================================================================
# 3. Analytic Accounting & Multi-Dimensional Cost Centers
# ============================================================================

class AnalyticPlan(BaseModel):
    """Analytic Dimension Plan (e.g. Department, Project, Cost Center)."""

    __tablename__ = "accounting_analytic_plans"

    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    code: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(sa.String(255), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(sa.String(16), nullable=True)

    __table_args__ = (
        sa.UniqueConstraint("company_id", "code", name="uq_analytic_plan_company_code"),
    )


class AnalyticAccount(BaseModel):
    """Specific Analytic Cost / Profit Center belonging to an Analytic Plan."""

    __tablename__ = "accounting_analytic_accounts"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("accounting_analytic_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    code: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    party_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("parties.id", ondelete="SET NULL"),
        nullable=True,
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("accounting_analytic_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )

    plan: Mapped["AnalyticPlan"] = relationship("AnalyticPlan")

    __table_args__ = (
        sa.UniqueConstraint("company_id", "plan_id", "code", name="uq_analytic_account_company_plan_code"),
    )


class AnalyticLine(BaseModel):
    """Analytic Ledger Entry tracking cost or revenue by cost center."""

    __tablename__ = "accounting_analytic_lines"

    analytic_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("accounting_analytic_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    move_line_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("accounting_move_lines.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    date: Mapped[date] = mapped_column(sa.Date, nullable=False, index=True)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(
        sa.Numeric(18, 4),
        nullable=False,
        doc="Negative for cost/expense, positive for revenue",
    )
    unit_amount: Mapped[float] = mapped_column(sa.Float, default=0.0, nullable=False)
    party_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("parties.id", ondelete="SET NULL"),
        nullable=True,
    )


# ============================================================================
# 4. Fixed Assets Management & Automated Depreciation
# ============================================================================

class AssetCategory(BaseModel):
    """Configuration category defining depreciation rules and GL accounts for assets."""

    __tablename__ = "accounting_asset_categories"

    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    journal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("accounting_journals.id", ondelete="RESTRICT"),
        nullable=False,
    )
    asset_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("accounting_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        doc="Fixed Asset Balance Sheet Account",
    )
    depr_expense_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("accounting_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        doc="Depreciation Expense P&L Account",
    )
    accum_depr_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("accounting_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        doc="Accumulated Depreciation Balance Sheet Contra-Account",
    )
    method: Mapped[str] = mapped_column(
        sa.String(32),
        default="straight_line",
        nullable=False,
        doc="Method: straight_line, declining, units",
    )
    duration_months: Mapped[int] = mapped_column(sa.Integer, default=36, nullable=False)
    prorata: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)


class Asset(BaseModel):
    """Fixed Asset Master Record."""

    __tablename__ = "accounting_assets"

    name: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("accounting_asset_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    purchase_date: Mapped[date] = mapped_column(sa.Date, nullable=False, index=True)
    original_value: Mapped[Decimal] = mapped_column(sa.Numeric(18, 4), nullable=False)
    salvage_value: Mapped[Decimal] = mapped_column(
        sa.Numeric(18, 4), default=Decimal("0.0000"), nullable=False
    )
    depreciable_value: Mapped[Decimal] = mapped_column(sa.Numeric(18, 4), nullable=False)
    book_value: Mapped[Decimal] = mapped_column(sa.Numeric(18, 4), nullable=False)
    state: Mapped[str] = mapped_column(
        sa.String(16),
        default="draft",
        nullable=False,
        index=True,
        doc="State: draft, running, depreciated, disposed",
    )

    category: Mapped["AssetCategory"] = relationship("AssetCategory")
    depreciation_lines: Mapped[List["AssetDepreciationLine"]] = relationship(
        "AssetDepreciationLine",
        back_populates="asset",
        cascade="all, delete-orphan",
        order_by="AssetDepreciationLine.sequence",
    )


class AssetDepreciationLine(BaseModel):
    """Periodic amortization schedule line for a Fixed Asset."""

    __tablename__ = "accounting_asset_depr_lines"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("accounting_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    depreciation_date: Mapped[date] = mapped_column(sa.Date, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(sa.Numeric(18, 4), nullable=False)
    remaining_value: Mapped[Decimal] = mapped_column(sa.Numeric(18, 4), nullable=False)
    accumulated_depreciation: Mapped[Decimal] = mapped_column(sa.Numeric(18, 4), nullable=False)
    move_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("accounting_moves.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_posted: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False, index=True)

    asset: Mapped["Asset"] = relationship("Asset", back_populates="depreciation_lines")


# ============================================================================
# 5. Budgeting & Financial Variance Control
# ============================================================================

class BudgetaryPosition(BaseModel):
    """Group of General Ledger accounts subject to budgetary monitoring."""

    __tablename__ = "accounting_budgetary_positions"

    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    code: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    account_ids: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
        server_default=sa.text("'[]'::jsonb"),
        nullable=False,
        doc="List of GL account UUID strings included in this budgetary position",
    )

    __table_args__ = (
        sa.UniqueConstraint("company_id", "code", name="uq_budget_position_company_code"),
    )


class Budget(BaseModel):
    """Financial Budget Plan."""

    __tablename__ = "accounting_budgets"

    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    date_from: Mapped[date] = mapped_column(sa.Date, nullable=False, index=True)
    date_to: Mapped[date] = mapped_column(sa.Date, nullable=False, index=True)
    responsible_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    state: Mapped[str] = mapped_column(
        sa.String(16),
        default="draft",
        nullable=False,
        index=True,
        doc="State: draft, confirmed, closed",
    )

    lines: Mapped[List["BudgetLine"]] = relationship(
        "BudgetLine",
        back_populates="budget",
        cascade="all, delete-orphan",
    )


class BudgetLine(BaseModel):
    """Individual budget target intersecting GL positions and Analytic Accounts."""

    __tablename__ = "accounting_budget_lines"

    budget_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("accounting_budgets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("accounting_budgetary_positions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    analytic_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("accounting_analytic_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    date_from: Mapped[date] = mapped_column(sa.Date, nullable=False)
    date_to: Mapped[date] = mapped_column(sa.Date, nullable=False)
    planned_amount: Mapped[Decimal] = mapped_column(sa.Numeric(18, 4), nullable=False)

    budget: Mapped["Budget"] = relationship("Budget", back_populates="lines")
    position: Mapped[Optional["BudgetaryPosition"]] = relationship("BudgetaryPosition")
    analytic_account: Mapped[Optional["AnalyticAccount"]] = relationship("AnalyticAccount")
