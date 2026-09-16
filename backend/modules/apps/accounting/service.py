"""Enterprise Financial Accounting & General Ledger Service Engine."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.event_bus import event_bus
from core.exceptions import NotFoundException, ValidationException
from modules.base.sequences.service import SequenceService
from modules.base.fiscal_calendar.service import FiscalCalendarService, FiscalPeriodNotFoundException
from modules.apps.accounting.models import (
    Account,
    AccountJournal,
    AccountMove,
    AccountMoveLine,
    AnalyticPlan,
    AnalyticAccount,
    AnalyticLine,
    AssetCategory,
    Asset,
    AssetDepreciationLine,
    BudgetaryPosition,
    Budget,
    BudgetLine,
)
from modules.apps.accounting.schemas import (
    AccountCreate,
    AccountUpdate,
    AccountJournalCreate,
    AccountJournalUpdate,
    AccountMoveCreate,
    AssetCategoryCreate,
    AssetCreate,
    BudgetCreate,
    BudgetaryPositionCreate,
    TrialBalanceItem,
    ProfitAndLossResponse,
    BalanceSheetResponse,
)


class AccountingService:
    """Core domain logic for General Ledger, Invoices, Assets, Budgets, and Analytics."""

    # ========================================================================
    # 1. Accounts & Journals
    # ========================================================================

    @staticmethod
    async def create_account(
        db: AsyncSession, payload: AccountCreate, company_id: uuid.UUID
    ) -> Account:
        """Create a new Chart of Accounts record."""
        # Check unique code within company
        stmt = sa.select(Account).where(
            Account.company_id == company_id,
            Account.code == payload.code,
            Account.deleted_at.is_(None),
        )
        res = await db.execute(stmt)
        if res.scalar_one_or_none():
            raise ValidationException(f"Account with code '{payload.code}' already exists.")

        account = Account(**payload.model_dump(), company_id=company_id)
        db.add(account)
        await db.commit()
        await db.refresh(account)
        return account

    @staticmethod
    async def create_journal(
        db: AsyncSession, payload: AccountJournalCreate, company_id: uuid.UUID
    ) -> AccountJournal:
        """Create a new Accounting Journal."""
        stmt = sa.select(AccountJournal).where(
            AccountJournal.company_id == company_id,
            AccountJournal.code == payload.code,
            AccountJournal.deleted_at.is_(None),
        )
        res = await db.execute(stmt)
        if res.scalar_one_or_none():
            raise ValidationException(f"Journal with code '{payload.code}' already exists.")

        journal = AccountJournal(**payload.model_dump(), company_id=company_id)
        db.add(journal)
        await db.commit()
        await db.refresh(journal)
        return journal

    # ========================================================================
    # 2. Journal Entries, Invoices & Double-Entry Posting
    # ========================================================================

    @staticmethod
    async def create_move(
        db: AsyncSession, payload: AccountMoveCreate, company_id: uuid.UUID
    ) -> AccountMove:
        """Create a draft Journal Entry, Invoice, or Vendor Bill."""
        move_data = payload.model_dump(exclude={"lines"})
        lines_data = payload.lines

        # Calculate totals
        total_debit = sum((line.debit for line in lines_data), Decimal("0.0000"))
        total_credit = sum((line.credit for line in lines_data), Decimal("0.0000"))

        move = AccountMove(
            **move_data,
            company_id=company_id,
            state="draft",
            amount_total=total_debit,
            amount_residual=total_debit,
        )
        db.add(move)
        await db.flush()

        for line_dto in lines_data:
            line_dict = line_dto.model_dump()
            line_analytic_id = line_dict.pop("analytic_account_id", None)
            if line_analytic_id and not line_dict.get("analytic_distribution"):
                line_dict["analytic_distribution"] = {str(line_analytic_id): 100.0}
            elif not line_dict.get("analytic_distribution") and move.analytic_account_id:
                line_dict["analytic_distribution"] = {str(move.analytic_account_id): 100.0}

            balance = line_dto.debit - line_dto.credit
            line = AccountMoveLine(
                **line_dict,
                move_id=move.id,
                company_id=company_id,
                balance=balance,
            )
            db.add(line)

        await db.commit()
        stmt = sa.select(AccountMove).options(selectinload(AccountMove.lines)).where(AccountMove.id == move.id)
        return (await db.execute(stmt)).scalar_one()

    @staticmethod
    async def post_move(
        db: AsyncSession, move_id: uuid.UUID, company_id: uuid.UUID
    ) -> AccountMove:
        """Post a journal move enforcing double-entry balance, legal numbering, and period open."""
        stmt = (
            sa.select(AccountMove)
            .options(selectinload(AccountMove.lines), selectinload(AccountMove.journal))
            .where(
                AccountMove.id == move_id,
                AccountMove.company_id == company_id,
                AccountMove.deleted_at.is_(None),
            )
        )
        res = await db.execute(stmt)
        move = res.scalar_one_or_none()
        if not move:
            raise NotFoundException("AccountMove", move_id)

        if move.state == "posted":
            return move

        # 1. Double-entry balance check: sum(debits) must equal sum(credits)
        total_debit = sum((line.debit for line in move.lines), Decimal("0.0000"))
        total_credit = sum((line.credit for line in move.lines), Decimal("0.0000"))

        if abs(total_debit - total_credit) > Decimal("0.001"):
            raise ValidationException(
                f"Double-entry imbalance: total debit ({total_debit}) does not equal total credit ({total_credit})."
            )

        # 2. Check Fiscal Period is open (if configured)
        try:
            await FiscalCalendarService.assert_period_open(db, company_id, move.date)
        except FiscalPeriodNotFoundException:
            pass

        # 3. Legal Gapless Auto-Numbering
        seq_code = move.journal.sequence_code if (move.journal and move.journal.sequence_code) else "account.general"
        try:
            legal_name, _ = await SequenceService.get_next_number(db, company_id, seq_code)
        except Exception:
            prefix = "INV" if move.move_type == "out_invoice" else ("BILL" if move.move_type == "in_invoice" else "MISC")
            legal_name = f"{prefix}/{move.date.year}/{uuid.uuid4().hex[:6].upper()}"
        move.name = legal_name
        move.state = "posted"
        move.amount_total = total_debit

        # 4. Process Analytic Distribution Lines
        for line in move.lines:
            if line.analytic_distribution:
                for analytic_acc_id_str, pct in line.analytic_distribution.items():
                    try:
                        analytic_acc_id = uuid.UUID(analytic_acc_id_str)
                        # Compute split amount: positive for credit (revenue), negative for debit (cost)
                        line_amount = (line.credit - line.debit) * (Decimal(str(pct)) / Decimal("100.0"))
                        analytic_line = AnalyticLine(
                            company_id=company_id,
                            analytic_account_id=analytic_acc_id,
                            move_line_id=line.id,
                            date=move.date,
                            name=line.name,
                            amount=line_amount,
                            party_id=line.party_id,
                        )
                        db.add(analytic_line)
                    except Exception:
                        pass

        await db.commit()
        await db.refresh(move)

        # 5. Publish Event
        await event_bus.publish(
            "accounting.move.posted",
            {
                "move_id": str(move.id),
                "name": move.name,
                "move_type": move.move_type,
                "amount_total": float(move.amount_total),
                "party_id": str(move.party_id) if move.party_id else None,
                "company_id": str(company_id),
            },
        )
        return move

    @staticmethod
    async def reconcile_lines(
        db: AsyncSession, line_ids: List[uuid.UUID], company_id: uuid.UUID
    ) -> str:
        """Reconcile multiple move lines (e.g. invoice receivable line + bank payment credit line)."""
        stmt = sa.select(AccountMoveLine).where(
            AccountMoveLine.id.in_(line_ids),
            AccountMoveLine.company_id == company_id,
            AccountMoveLine.deleted_at.is_(None),
        )
        res = await db.execute(stmt)
        lines = list(res.scalars().all())

        if len(lines) < 2:
            raise ValidationException("Reconciliation requires at least two lines.")

        total_balance = sum((l.balance for l in lines), Decimal("0.0000"))
        if abs(total_balance) > Decimal("0.01"):
            raise ValidationException(
                f"Reconciliation balance must sum to 0. Current net balance: {total_balance}"
            )

        matching_hash = f"REC_{uuid.uuid4().hex[:8].upper()}"
        for l in lines:
            l.reconciled = True
            l.matching_number = matching_hash

        # Update parent move residuals
        move_ids = {l.move_id for l in lines}
        for m_id in move_ids:
            move_res = await db.execute(
                sa.select(AccountMove)
                .options(selectinload(AccountMove.lines))
                .where(AccountMove.id == m_id)
            )
            move_obj = move_res.scalar_one_or_none()
            if move_obj and move_obj.move_type in ("out_invoice", "in_invoice"):
                unreconciled_bal = sum(
                    (abs(l.balance) for l in move_obj.lines if not l.reconciled),
                    Decimal("0.0000"),
                )
                move_obj.amount_residual = unreconciled_bal

        await db.commit()
        return matching_hash

    # ========================================================================
    # 3. Fixed Asset Management & Depreciation
    # ========================================================================

    @staticmethod
    async def create_asset(
        db: AsyncSession, payload: AssetCreate, company_id: uuid.UUID
    ) -> Asset:
        """Create a fixed asset and compute its depreciation schedule."""
        cat_res = await db.execute(
            sa.select(AssetCategory).where(
                AssetCategory.id == payload.category_id,
                AssetCategory.company_id == company_id,
            )
        )
        cat = cat_res.scalar_one_or_none()
        if not cat:
            raise NotFoundException("AssetCategory", payload.category_id)

        depreciable = payload.original_value - payload.salvage_value
        asset = Asset(
            **payload.model_dump(),
            company_id=company_id,
            depreciable_value=depreciable,
            book_value=payload.original_value,
            state="draft",
        )
        db.add(asset)
        await db.flush()

        # Compute amortization schedule (straight line monthly)
        duration = cat.duration_months
        monthly_amount = depreciable / Decimal(str(duration))
        remaining = depreciable
        accum = Decimal("0.0000")

        # Generate monthly lines
        for seq in range(1, duration + 1):
            amount = monthly_amount if seq < duration else remaining
            remaining -= amount
            accum += amount
            import datetime as dt
            # Month offset approximation: 30 days per month
            depr_date = payload.purchase_date + dt.timedelta(days=30 * seq)

            line = AssetDepreciationLine(
                company_id=company_id,
                asset_id=asset.id,
                sequence=seq,
                depreciation_date=depr_date,
                amount=amount,
                remaining_value=remaining,
                accumulated_depreciation=accum,
                is_posted=False,
            )
            db.add(line)

        await db.commit()
        stmt = sa.select(Asset).options(selectinload(Asset.depreciation_lines)).where(Asset.id == asset.id)
        return (await db.execute(stmt)).scalar_one()

    @staticmethod
    async def post_depreciation_line(
        db: AsyncSession, line_id: uuid.UUID, company_id: uuid.UUID
    ) -> AccountMove:
        """Post a single depreciation schedule line as a balanced journal entry."""
        stmt = (
            sa.select(AssetDepreciationLine)
            .options(
                selectinload(AssetDepreciationLine.asset).selectinload(Asset.category)
            )
            .where(
                AssetDepreciationLine.id == line_id,
                AssetDepreciationLine.company_id == company_id,
            )
        )
        res = await db.execute(stmt)
        depr_line = res.scalar_one_or_none()
        if not depr_line:
            raise NotFoundException("AssetDepreciationLine", line_id)

        if depr_line.is_posted:
            raise ValidationException("Depreciation line already posted.")

        asset = depr_line.asset
        cat = asset.category

        # Lookup company currency
        acc_res = await db.execute(
            sa.select(Account.currency_id).where(Account.id == cat.asset_account_id)
        )
        curr_id = acc_res.scalar_one_or_none() or uuid.uuid4()

        # Build balanced entry: Debit Depr Expense / Credit Accum Depr
        move = AccountMove(
            company_id=company_id,
            name="Draft",
            move_type="entry",
            date=depr_line.depreciation_date,
            ref=f"Depreciation: {asset.name} (Month {depr_line.sequence})",
            journal_id=cat.journal_id,
            currency_id=curr_id,
            state="draft",
            amount_total=depr_line.amount,
        )
        db.add(move)
        await db.flush()

        # Debit: Depreciation Expense
        db.add(
            AccountMoveLine(
                company_id=company_id,
                move_id=move.id,
                account_id=cat.depr_expense_account_id,
                name=f"Depreciation expense - {asset.name}",
                debit=depr_line.amount,
                credit=Decimal("0.0000"),
                balance=depr_line.amount,
            )
        )
        # Credit: Accumulated Depreciation
        db.add(
            AccountMoveLine(
                company_id=company_id,
                move_id=move.id,
                account_id=cat.accum_depr_account_id,
                name=f"Accumulated depreciation - {asset.name}",
                debit=Decimal("0.0000"),
                credit=depr_line.amount,
                balance=-depr_line.amount,
            )
        )

        depr_line.is_posted = True
        depr_line.move_id = move.id
        asset.book_value -= depr_line.amount
        asset.state = "running" if depr_line.sequence < cat.duration_months else "depreciated"

        await db.commit()
        return await AccountingService.post_move(db, move.id, company_id)

    # ========================================================================
    # 4. Budgeting & Variance Engine
    # ========================================================================

    @staticmethod
    async def create_budget(
        db: AsyncSession, payload: BudgetCreate, company_id: uuid.UUID
    ) -> Budget:
        """Create a financial budget plan with lines."""
        lines_data = payload.lines
        budget = Budget(
            name=payload.name,
            date_from=payload.date_from,
            date_to=payload.date_to,
            responsible_id=payload.responsible_id,
            company_id=company_id,
            state="confirmed",
        )
        db.add(budget)
        await db.flush()

        for l_dto in lines_data:
            line = BudgetLine(
                **l_dto.model_dump(),
                budget_id=budget.id,
                company_id=company_id,
            )
            db.add(line)

        await db.commit()
        stmt = sa.select(Budget).options(selectinload(Budget.lines)).where(Budget.id == budget.id)
        return (await db.execute(stmt)).scalar_one()

    @staticmethod
    async def get_budget_analysis(
        db: AsyncSession, budget_id: uuid.UUID, company_id: uuid.UUID
    ) -> List[Dict[str, Any]]:
        """Calculate real-time Planned vs Actual vs Theoretical variance for all budget lines."""
        stmt = (
            sa.select(BudgetLine)
            .options(
                selectinload(BudgetLine.position),
                selectinload(BudgetLine.analytic_account),
            )
            .where(
                BudgetLine.budget_id == budget_id,
                BudgetLine.company_id == company_id,
            )
        )
        res = await db.execute(stmt)
        lines = list(res.scalars().all())

        today = date.today()
        analysis: List[Dict[str, Any]] = []

        for line in lines:
            # 1. Query posted actual amount from move lines
            q = (
                sa.select(
                    sa.func.coalesce(sa.func.sum(AccountMoveLine.debit - AccountMoveLine.credit), 0)
                )
                .select_from(AccountMoveLine)
                .join(AccountMove, AccountMoveLine.move_id == AccountMove.id)
                .where(
                    AccountMove.state == "posted",
                    AccountMove.company_id == company_id,
                    AccountMove.date >= line.date_from,
                    AccountMove.date <= line.date_to,
                )
            )

            # Filter by GL accounts from BudgetaryPosition if specified
            if line.position and line.position.account_ids:
                acc_uuids = [uuid.UUID(uid) for uid in line.position.account_ids]
                q = q.where(AccountMoveLine.account_id.in_(acc_uuids))

            actual_res = await db.execute(q)
            actual_amount = Decimal(str(actual_res.scalar() or 0))

            # 2. Compute theoretical amount (linear time elapsed)
            total_days = (line.date_to - line.date_from).days or 1
            elapsed_days = max(0, min(total_days, (today - line.date_from).days))
            theo_ratio = Decimal(str(elapsed_days)) / Decimal(str(total_days))
            theoritical_amount = line.planned_amount * theo_ratio

            # 3. Variance & Percentage
            variance = line.planned_amount - actual_amount
            percentage = (
                float(actual_amount / line.planned_amount * 100)
                if line.planned_amount > 0
                else 0.0
            )

            analysis.append({
                "line_id": str(line.id),
                "position_name": line.position.name if line.position else "All Accounts",
                "analytic_account_name": line.analytic_account.name if line.analytic_account else "All Analytic",
                "planned_amount": float(line.planned_amount),
                "practical_amount": float(actual_amount),
                "theoritical_amount": float(theoritical_amount),
                "variance": float(variance),
                "percentage": round(percentage, 2),
            })

        return analysis

    # ========================================================================
    # 5. Financial Reporting (Trial Balance, P&L, Balance Sheet)
    # ========================================================================

    @staticmethod
    async def get_trial_balance(
        db: AsyncSession, company_id: uuid.UUID, date_from: date, date_to: date
    ) -> List[TrialBalanceItem]:
        """Compute real-time Trial Balance aggregated across all accounts."""
        stmt = (
            sa.select(
                Account.id,
                Account.code,
                Account.name,
                Account.account_type,
                sa.func.coalesce(sa.func.sum(AccountMoveLine.debit), 0).label("total_debit"),
                sa.func.coalesce(sa.func.sum(AccountMoveLine.credit), 0).label("total_credit"),
            )
            .select_from(Account)
            .outerjoin(
                AccountMoveLine,
                sa.and_(
                    Account.id == AccountMoveLine.account_id,
                    AccountMoveLine.deleted_at.is_(None),
                ),
            )
            .outerjoin(
                AccountMove,
                sa.and_(
                    AccountMoveLine.move_id == AccountMove.id,
                    AccountMove.state == "posted",
                    AccountMove.date >= date_from,
                    AccountMove.date <= date_to,
                ),
            )
            .where(Account.company_id == company_id, Account.deleted_at.is_(None))
            .group_by(Account.id, Account.code, Account.name, Account.account_type)
            .order_by(Account.code)
        )
        res = await db.execute(stmt)
        rows = res.all()

        items: List[TrialBalanceItem] = []
        for r in rows:
            debit = Decimal(str(r.total_debit))
            credit = Decimal(str(r.total_credit))
            balance = debit - credit
            items.append(
                TrialBalanceItem(
                    account_id=str(r.id),
                    account_code=r.code,
                    account_name=r.name,
                    account_type=r.account_type,
                    initial_debit=Decimal("0.00"),
                    initial_credit=Decimal("0.00"),
                    period_debit=debit,
                    period_credit=credit,
                    ending_debit=debit,
                    ending_credit=credit,
                    ending_balance=balance,
                )
            )
        return items
