"""Enterprise Financial Accounting & General Ledger Pydantic Validation Schemas."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# 1. Accounts & Journals
# ============================================================================

class AccountBase(BaseModel):
    code: str = Field(..., max_length=32)
    name: str = Field(..., max_length=255)
    account_type: str = Field(
        ...,
        description="asset_current, asset_non_current, liability_current, liability_non_current, equity, income, expense, expense_depreciation",
    )
    parent_id: Optional[uuid.UUID] = None
    currency_id: Optional[uuid.UUID] = None
    reconcilable: bool = False
    is_deprecated: bool = False


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    account_type: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None
    currency_id: Optional[uuid.UUID] = None
    reconcilable: Optional[bool] = None
    is_deprecated: Optional[bool] = None


class AccountRead(AccountBase):
    id: uuid.UUID
    company_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AccountJournalBase(BaseModel):
    code: str = Field(..., max_length=16)
    name: str = Field(..., max_length=128)
    type: Literal["sale", "purchase", "bank", "cash", "general"]
    default_account_id: Optional[uuid.UUID] = None
    sequence_code: str = Field(default="account.general", max_length=64)


class AccountJournalCreate(AccountJournalBase):
    pass


class AccountJournalUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    type: Optional[Literal["sale", "purchase", "bank", "cash", "general"]] = None
    default_account_id: Optional[uuid.UUID] = None
    sequence_code: Optional[str] = None


class AccountJournalRead(AccountJournalBase):
    id: uuid.UUID
    company_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# 2. Moves & Lines
# ============================================================================

class AccountMoveLineCreate(BaseModel):
    account_id: uuid.UUID
    party_id: Optional[uuid.UUID] = None
    name: str = Field(..., max_length=255)
    debit: Decimal = Field(default=Decimal("0.0000"), ge=0)
    credit: Decimal = Field(default=Decimal("0.0000"), ge=0)
    amount_currency: Optional[Decimal] = None
    currency_id: Optional[uuid.UUID] = None
    tax_id: Optional[uuid.UUID] = None
    analytic_distribution: Dict[str, float] = Field(default_factory=dict)


class AccountMoveLineRead(BaseModel):
    id: uuid.UUID
    move_id: uuid.UUID
    account_id: uuid.UUID
    party_id: Optional[uuid.UUID] = None
    name: str
    debit: Decimal
    credit: Decimal
    balance: Decimal
    amount_currency: Optional[Decimal] = None
    currency_id: Optional[uuid.UUID] = None
    reconciled: bool
    matching_number: Optional[str] = None
    tax_id: Optional[uuid.UUID] = None
    analytic_distribution: Dict[str, float]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AccountMoveCreate(BaseModel):
    move_type: Literal["entry", "out_invoice", "out_refund", "in_invoice", "in_refund"] = "entry"
    date: date
    ref: Optional[str] = None
    journal_id: uuid.UUID
    party_id: Optional[uuid.UUID] = None
    currency_id: uuid.UUID
    payment_term_id: Optional[uuid.UUID] = None
    fiscal_period_id: Optional[uuid.UUID] = None
    invoice_date_due: Optional[date] = None
    lines: List[AccountMoveLineCreate] = Field(..., min_length=2)


class AccountMoveUpdate(BaseModel):
    date: Optional[date] = None
    ref: Optional[str] = None
    party_id: Optional[uuid.UUID] = None
    payment_term_id: Optional[uuid.UUID] = None
    invoice_date_due: Optional[date] = None


class AccountMoveRead(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    move_type: str
    date: date
    ref: Optional[str] = None
    journal_id: uuid.UUID
    party_id: Optional[uuid.UUID] = None
    currency_id: uuid.UUID
    state: str
    amount_total: Decimal
    amount_residual: Decimal
    payment_term_id: Optional[uuid.UUID] = None
    fiscal_period_id: Optional[uuid.UUID] = None
    invoice_date_due: Optional[date] = None
    lines: List[AccountMoveLineRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# 3. Analytic Accounts & Plans
# ============================================================================

class AnalyticPlanCreate(BaseModel):
    name: str = Field(..., max_length=128)
    code: str = Field(..., max_length=32)
    description: Optional[str] = None
    color: Optional[str] = None


class AnalyticPlanRead(AnalyticPlanCreate):
    id: uuid.UUID
    company_id: uuid.UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AnalyticAccountCreate(BaseModel):
    plan_id: uuid.UUID
    name: str = Field(..., max_length=128)
    code: str = Field(..., max_length=32)
    party_id: Optional[uuid.UUID] = None
    parent_id: Optional[uuid.UUID] = None


class AnalyticAccountRead(AnalyticAccountCreate):
    id: uuid.UUID
    company_id: uuid.UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AnalyticLineRead(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    analytic_account_id: uuid.UUID
    move_line_id: Optional[uuid.UUID] = None
    date: date
    name: str
    amount: Decimal
    unit_amount: float
    party_id: Optional[uuid.UUID] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# 4. Fixed Assets & Depreciation
# ============================================================================

class AssetCategoryCreate(BaseModel):
    name: str = Field(..., max_length=128)
    journal_id: uuid.UUID
    asset_account_id: uuid.UUID
    depr_expense_account_id: uuid.UUID
    accum_depr_account_id: uuid.UUID
    method: Literal["straight_line", "declining", "units"] = "straight_line"
    duration_months: int = Field(default=36, gt=0)
    prorata: bool = True


class AssetCategoryRead(AssetCategoryCreate):
    id: uuid.UUID
    company_id: uuid.UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AssetDepreciationLineRead(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    sequence: int
    depreciation_date: date
    amount: Decimal
    remaining_value: Decimal
    accumulated_depreciation: Decimal
    move_id: Optional[uuid.UUID] = None
    is_posted: bool
    model_config = ConfigDict(from_attributes=True)


class AssetCreate(BaseModel):
    name: str = Field(..., max_length=255)
    category_id: uuid.UUID
    purchase_date: date
    original_value: Decimal = Field(..., gt=0)
    salvage_value: Decimal = Field(default=Decimal("0.0000"), ge=0)


class AssetRead(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    category_id: uuid.UUID
    purchase_date: date
    original_value: Decimal
    salvage_value: Decimal
    depreciable_value: Decimal
    book_value: Decimal
    state: str
    depreciation_lines: List[AssetDepreciationLineRead] = Field(default_factory=list)
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# 5. Budgets
# ============================================================================

class BudgetaryPositionCreate(BaseModel):
    name: str = Field(..., max_length=128)
    code: str = Field(..., max_length=32)
    account_ids: List[str] = Field(default_factory=list)


class BudgetaryPositionRead(BudgetaryPositionCreate):
    id: uuid.UUID
    company_id: uuid.UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class BudgetLineCreate(BaseModel):
    position_id: Optional[uuid.UUID] = None
    analytic_account_id: Optional[uuid.UUID] = None
    date_from: date
    date_to: date
    planned_amount: Decimal = Field(..., gt=0)


class BudgetLineRead(BudgetLineCreate):
    id: uuid.UUID
    budget_id: uuid.UUID
    practical_amount: Optional[Decimal] = Decimal("0.0000")
    theoritical_amount: Optional[Decimal] = Decimal("0.0000")
    percentage: Optional[float] = 0.0
    variance: Optional[Decimal] = Decimal("0.0000")
    model_config = ConfigDict(from_attributes=True)


class BudgetCreate(BaseModel):
    name: str = Field(..., max_length=128)
    date_from: date
    date_to: date
    responsible_id: Optional[uuid.UUID] = None
    lines: List[BudgetLineCreate] = Field(default_factory=list)


class BudgetRead(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    date_from: date
    date_to: date
    responsible_id: Optional[uuid.UUID] = None
    state: str
    lines: List[BudgetLineRead] = Field(default_factory=list)
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# 6. Financial Reporting Output Schemas
# ============================================================================

class TrialBalanceItem(BaseModel):
    account_id: str
    account_code: str
    account_name: str
    account_type: str
    initial_debit: Decimal
    initial_credit: Decimal
    period_debit: Decimal
    period_credit: Decimal
    ending_debit: Decimal
    ending_credit: Decimal
    ending_balance: Decimal


class ProfitAndLossResponse(BaseModel):
    date_from: date
    date_to: date
    operating_income: Decimal
    operating_expenses: Decimal
    gross_profit: Decimal
    net_profit: Decimal
    income_breakdown: List[Dict[str, Any]]
    expense_breakdown: List[Dict[str, Any]]


class BalanceSheetResponse(BaseModel):
    as_of_date: date
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal
    balance_check: Decimal
    assets_breakdown: List[Dict[str, Any]]
    liabilities_breakdown: List[Dict[str, Any]]
    equity_breakdown: List[Dict[str, Any]]
