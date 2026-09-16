"""Enterprise Financial Accounting & General Ledger REST API Router."""

import uuid
from datetime import date
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.database import get_db
from core.context import get_active_company_id, get_active_company_ids
from modules.base.identity_rbac.dependencies import get_current_user
from modules.base.identity_rbac.models import User
from modules.apps.accounting.models import (
    Account,
    AccountJournal,
    AccountMove,
    AnalyticPlan,
    AnalyticAccount,
    AssetCategory,
    Asset,
    BudgetaryPosition,
    Budget,
)
from modules.apps.accounting.schemas import (
    AccountCreate,
    AccountRead,
    AccountJournalCreate,
    AccountJournalRead,
    AccountMoveCreate,
    AccountMoveRead,
    AnalyticPlanCreate,
    AnalyticPlanRead,
    AnalyticAccountCreate,
    AnalyticAccountRead,
    AssetCategoryCreate,
    AssetCategoryRead,
    AssetCreate,
    AssetRead,
    BudgetaryPositionCreate,
    BudgetaryPositionRead,
    BudgetCreate,
    BudgetRead,
    TrialBalanceItem,
)
from modules.apps.accounting.service import AccountingService

router = APIRouter(tags=["Financial Accounting & General Ledger"])


# ============================================================================
# 1. Accounts & Journals
# ============================================================================

@router.get("/accounts", response_model=List[AccountRead])
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """List all Chart of Accounts entries for the active company."""
    stmt = (
        select(Account)
        .where(Account.company_id == company_id, Account.deleted_at.is_(None))
        .order_by(Account.code)
    )
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/accounts", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
async def create_account(
    payload: AccountCreate,
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """Create a new Chart of Accounts record."""
    return await AccountingService.create_account(db, payload, company_id)


@router.get("/journals", response_model=List[AccountJournalRead])
async def list_journals(
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """List all Accounting Journals for the active company."""
    stmt = (
        select(AccountJournal)
        .where(AccountJournal.company_id == company_id, AccountJournal.deleted_at.is_(None))
        .order_by(AccountJournal.code)
    )
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/journals", response_model=AccountJournalRead, status_code=status.HTTP_201_CREATED)
async def create_journal(
    payload: AccountJournalCreate,
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """Create a new Accounting Journal."""
    return await AccountingService.create_journal(db, payload, company_id)


# ============================================================================
# 2. Journal Moves & Invoices
# ============================================================================

@router.get("/moves", response_model=List[AccountMoveRead])
async def list_moves(
    move_type: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """List Journal Entries, Invoices, and Vendor Bills."""
    active_comps = get_active_company_ids() or [company_id]
    stmt = (
        select(AccountMove)
        .options(selectinload(AccountMove.lines))
        .where(AccountMove.company_id.in_(active_comps), AccountMove.deleted_at.is_(None))
        .order_by(AccountMove.date.desc(), AccountMove.created_at.desc())
    )
    if move_type:
        stmt = stmt.where(AccountMove.move_type == move_type)
    if state:
        stmt = stmt.where(AccountMove.state == state)

    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/moves", response_model=AccountMoveRead, status_code=status.HTTP_201_CREATED)
async def create_move(
    payload: AccountMoveCreate,
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """Create a draft Journal Move, Customer Invoice, or Vendor Bill."""
    return await AccountingService.create_move(db, payload, company_id)


@router.post("/moves/{move_id}/post", response_model=AccountMoveRead)
async def post_move(
    move_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """Post a journal move, validating double-entry balance and stamping legal sequence."""
    return await AccountingService.post_move(db, move_id, company_id)


@router.post("/reconcile")
async def reconcile_lines(
    line_ids: List[uuid.UUID],
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """Perform open-item reconciliation matching debits and credits."""
    matching_hash = await AccountingService.reconcile_lines(db, line_ids, company_id)
    return {"status": "reconciled", "matching_number": matching_hash}


# ============================================================================
# 3. Analytic Accounting & Cost Centers
# ============================================================================

@router.get("/analytic-plans", response_model=List[AnalyticPlanRead])
async def list_analytic_plans(
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """List all Analytic Dimension Plans."""
    stmt = (
        select(AnalyticPlan)
        .where(AnalyticPlan.company_id == company_id, AnalyticPlan.deleted_at.is_(None))
        .order_by(AnalyticPlan.name)
    )
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/analytic-plans", response_model=AnalyticPlanRead, status_code=status.HTTP_201_CREATED)
async def create_analytic_plan(
    payload: AnalyticPlanCreate,
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """Create a new Analytic Plan."""
    plan = AnalyticPlan(**payload.model_dump(), company_id=company_id)
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


@router.post("/analytic-accounts", response_model=AnalyticAccountRead, status_code=status.HTTP_201_CREATED)
async def create_analytic_account(
    payload: AnalyticAccountCreate,
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """Create a new Analytic Cost / Profit Center."""
    acc = AnalyticAccount(**payload.model_dump(), company_id=company_id)
    db.add(acc)
    await db.commit()
    await db.refresh(acc)
    return acc


# ============================================================================
# 4. Fixed Assets & Depreciation
# ============================================================================

@router.post("/asset-categories", response_model=AssetCategoryRead, status_code=status.HTTP_201_CREATED)
async def create_asset_category(
    payload: AssetCategoryCreate,
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """Create a new Asset Category with depreciation parameters."""
    cat = AssetCategory(**payload.model_dump(), company_id=company_id)
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


@router.post("/assets", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
async def create_asset(
    payload: AssetCreate,
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """Register a Fixed Asset and calculate its amortization schedule."""
    return await AccountingService.create_asset(db, payload, company_id)


@router.post("/assets/lines/{line_id}/post", response_model=AccountMoveRead)
async def post_asset_depreciation_line(
    line_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """Post a monthly asset depreciation line as a journal entry."""
    return await AccountingService.post_depreciation_line(db, line_id, company_id)


# ============================================================================
# 5. Budgets
# ============================================================================

@router.post("/budgetary-positions", response_model=BudgetaryPositionRead, status_code=status.HTTP_201_CREATED)
async def create_budgetary_position(
    payload: BudgetaryPositionCreate,
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """Create a budgetary position grouping accounts."""
    pos = BudgetaryPosition(**payload.model_dump(), company_id=company_id)
    db.add(pos)
    await db.commit()
    await db.refresh(pos)
    return pos


@router.post("/budgets", response_model=BudgetRead, status_code=status.HTTP_201_CREATED)
async def create_budget(
    payload: BudgetCreate,
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """Create a new budget plan."""
    return await AccountingService.create_budget(db, payload, company_id)


@router.get("/budgets/{budget_id}/analysis")
async def get_budget_analysis(
    budget_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """Get real-time Planned vs Actual vs Theoretical analysis for budget lines."""
    return await AccountingService.get_budget_analysis(db, budget_id, company_id)


# ============================================================================
# 6. Financial Reports
# ============================================================================

@router.get("/reports/trial-balance", response_model=List[TrialBalanceItem])
async def get_trial_balance(
    date_from: date = Query(date(2026, 1, 1)),
    date_to: date = Query(date(2026, 12, 31)),
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """Generate real-time Trial Balance report."""
    return await AccountingService.get_trial_balance(db, company_id, date_from, date_to)
