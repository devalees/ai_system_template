"""Comprehensive automated test suite for Enterprise Financial Suite (accounting, sales, purchases)."""

import uuid
import pytest
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
import sqlalchemy as sa

from modules.base.identity_rbac.models import Company, User
from modules.base.lookups.models import Currency
from modules.base.parties.models import Party
from modules.apps.accounting.models import (
    Account,
    AccountJournal,
    AccountMove,
    AnalyticPlan,
    AnalyticAccount,
    AnalyticLine,
    AssetCategory,
    Asset,
    AssetDepreciationLine,
    BudgetaryPosition,
    Budget,
)
from modules.apps.accounting.schemas import (
    AccountCreate,
    AccountJournalCreate,
    AccountMoveCreate,
    AccountMoveLineCreate,
    AnalyticPlanCreate,
    AnalyticAccountCreate,
    AssetCategoryCreate,
    AssetCreate,
    BudgetaryPositionCreate,
    BudgetCreate,
    BudgetLineCreate,
)
from modules.apps.accounting.service import AccountingService
from modules.apps.sales.models import SaleOrder
from modules.apps.sales.schemas import SaleOrderCreate, SaleOrderLineCreate
from modules.apps.sales.service import SaleService
from modules.apps.purchases.models import PurchaseOrder
from modules.apps.purchases.schemas import PurchaseOrderCreate, PurchaseOrderLineCreate
from modules.apps.purchases.service import PurchaseService
from core.exceptions import ValidationException


@pytest.mark.asyncio
async def test_chart_of_accounts_and_journals(db_session: AsyncSession):
    """Verify creation and query of Chart of Accounts and Journals."""
    comp_id = uuid.uuid4()
    company = Company(id=comp_id, name="Fin Co", code=f"FIN_{comp_id.hex[:4]}")
    db_session.add(company)
    await db_session.commit()

    # Create Cash Account
    cash_acc = await AccountingService.create_account(
        db_session,
        AccountCreate(
            code="101000",
            name="Main Cash Account",
            account_type="asset_current",
            reconcilable=True,
        ),
        comp_id,
    )
    assert cash_acc.id is not None
    assert cash_acc.code == "101000"

    # Create Sales Journal
    sale_journal = await AccountingService.create_journal(
        db_session,
        AccountJournalCreate(
            code="SAL",
            name="Customer Invoices Journal",
            type="sale",
            sequence_code="account.sale",
        ),
        comp_id,
    )
    assert sale_journal.id is not None
    assert sale_journal.type == "sale"


@pytest.mark.asyncio
async def test_double_entry_balance_enforcement(db_session: AsyncSession):
    """Verify strict double-entry balance check: unbalanced entries are rejected."""
    comp_id = uuid.uuid4()
    company = Company(id=comp_id, name="DoubleEntry Co", code=f"DE_{comp_id.hex[:4]}")
    curr = Currency(company_id=comp_id, code="USD", name="US Dollar", symbol="$", decimal_places=2)
    db_session.add_all([company, curr])
    await db_session.commit()

    # Setup fiscal period
    today = date.today()

    # Setup accounts and journal
    acc1 = await AccountingService.create_account(
        db_session, AccountCreate(code="101000", name="Cash", account_type="asset_current"), comp_id
    )
    acc2 = await AccountingService.create_account(
        db_session, AccountCreate(code="401000", name="Sales", account_type="income"), comp_id
    )
    journal = await AccountingService.create_journal(
        db_session, AccountJournalCreate(code="GEN", name="General", type="general"), comp_id
    )

    # 1. Unbalanced Move (Debit 100 != Credit 80)
    unbalanced_payload = AccountMoveCreate(
        move_type="entry",
        date=today,
        journal_id=journal.id,
        currency_id=curr.id,
        lines=[
            AccountMoveLineCreate(account_id=acc1.id, name="Cash in", debit=Decimal("100.00"), credit=Decimal("0.00")),
            AccountMoveLineCreate(account_id=acc2.id, name="Revenue", debit=Decimal("0.00"), credit=Decimal("80.00")),
        ],
    )
    unbalanced_move = await AccountingService.create_move(db_session, unbalanced_payload, comp_id)

    # Posting must fail with ValidationException
    with pytest.raises(ValidationException) as exc:
        await AccountingService.post_move(db_session, unbalanced_move.id, comp_id)
    assert "Double-entry imbalance" in str(exc.value)

    # 2. Balanced Move (Debit 100 == Credit 100)
    balanced_payload = AccountMoveCreate(
        move_type="entry",
        date=today,
        journal_id=journal.id,
        currency_id=curr.id,
        lines=[
            AccountMoveLineCreate(account_id=acc1.id, name="Cash in", debit=Decimal("100.00"), credit=Decimal("0.00")),
            AccountMoveLineCreate(account_id=acc2.id, name="Revenue", debit=Decimal("0.00"), credit=Decimal("100.00")),
        ],
    )
    balanced_move = await AccountingService.create_move(db_session, balanced_payload, comp_id)
    posted = await AccountingService.post_move(db_session, balanced_move.id, comp_id)
    assert posted.state == "posted"
    assert posted.name != "Draft"
    assert posted.amount_total == Decimal("100.00")


@pytest.mark.asyncio
async def test_analytic_accounting_and_distribution(db_session: AsyncSession):
    """Verify analytic account creation and automatic analytic line extraction on posting."""
    comp_id = uuid.uuid4()
    company = Company(id=comp_id, name="Analytic Co", code=f"AN_{comp_id.hex[:4]}")
    curr = Currency(company_id=comp_id, code="USD", name="US Dollar", symbol="$", decimal_places=2)
    db_session.add_all([company, curr])
    await db_session.commit()

    today = date.today()

    # Create Analytic Plan and Account
    plan = AnalyticPlan(name="Cost Centers", code="CC", company_id=comp_id)
    db_session.add(plan)
    await db_session.flush()

    analytic_acc = AnalyticAccount(name="Marketing Dept", code="MKT", plan_id=plan.id, company_id=comp_id)
    db_session.add(analytic_acc)
    await db_session.commit()

    # Accounts & Journal
    acc1 = await AccountingService.create_account(
        db_session, AccountCreate(code="101000", name="Cash", account_type="asset_current"), comp_id
    )
    acc2 = await AccountingService.create_account(
        db_session, AccountCreate(code="601000", name="Ad Expense", account_type="expense"), comp_id
    )
    journal = await AccountingService.create_journal(
        db_session, AccountJournalCreate(code="GEN", name="General", type="general"), comp_id
    )

    # Move with analytic distribution
    move_payload = AccountMoveCreate(
        move_type="entry",
        date=today,
        journal_id=journal.id,
        currency_id=curr.id,
        lines=[
            AccountMoveLineCreate(
                account_id=acc2.id,
                name="Google Ads Expense",
                debit=Decimal("500.00"),
                credit=Decimal("0.00"),
                analytic_distribution={str(analytic_acc.id): 100.0},
            ),
            AccountMoveLineCreate(
                account_id=acc1.id,
                name="Bank Payment",
                debit=Decimal("0.00"),
                credit=Decimal("500.00"),
            ),
        ],
    )
    move = await AccountingService.create_move(db_session, move_payload, comp_id)
    await AccountingService.post_move(db_session, move.id, comp_id)

    # Verify AnalyticLine was auto-generated
    stmt = sa.select(AnalyticLine).where(
        AnalyticLine.analytic_account_id == analytic_acc.id,
        AnalyticLine.company_id == comp_id,
    )
    res = await db_session.execute(stmt)
    lines = list(res.scalars().all())
    assert len(lines) == 1
    assert lines[0].amount == Decimal("-500.0000")  # Debit expense is negative in analytic ledger


@pytest.mark.asyncio
async def test_fixed_asset_management_and_depreciation(db_session: AsyncSession):
    """Verify Fixed Asset schedule calculation and automated monthly depreciation posting."""
    comp_id = uuid.uuid4()
    company = Company(id=comp_id, name="Asset Co", code=f"AST_{comp_id.hex[:4]}")
    curr = Currency(company_id=comp_id, code="USD", name="US Dollar", symbol="$", decimal_places=2)
    db_session.add_all([company, curr])
    await db_session.commit()

    today = date.today()

    # Accounts: Asset, Depr Expense, Accum Depr
    asset_acc = await AccountingService.create_account(
        db_session, AccountCreate(code="150000", name="Machinery Asset", account_type="asset_non_current", currency_id=curr.id), comp_id
    )
    expense_acc = await AccountingService.create_account(
        db_session, AccountCreate(code="680000", name="Depreciation Expense", account_type="expense_depreciation", currency_id=curr.id), comp_id
    )
    accum_acc = await AccountingService.create_account(
        db_session, AccountCreate(code="159000", name="Accumulated Depreciation", account_type="asset_non_current", currency_id=curr.id), comp_id
    )
    journal = await AccountingService.create_journal(
        db_session, AccountJournalCreate(code="AST", name="Asset Journal", type="general"), comp_id
    )

    # Asset Category: 12 months straight line
    cat = AssetCategory(
        name="Industrial Equipment",
        journal_id=journal.id,
        asset_account_id=asset_acc.id,
        depr_expense_account_id=expense_acc.id,
        accum_depr_account_id=accum_acc.id,
        method="straight_line",
        duration_months=12,
        company_id=comp_id,
    )
    db_session.add(cat)
    await db_session.commit()

    # Create Asset: $12,000 original value
    asset_payload = AssetCreate(
        name="CNC Milling Machine",
        category_id=cat.id,
        purchase_date=today,
        original_value=Decimal("12000.00"),
        salvage_value=Decimal("0.00"),
    )
    asset = await AccountingService.create_asset(db_session, asset_payload, comp_id)

    assert asset.id is not None
    assert len(asset.depreciation_lines) == 12
    first_line = asset.depreciation_lines[0]
    assert first_line.amount == Decimal("1000.0000")  # 12000 / 12 = 1000

    # Post Month 1 Depreciation Line
    posted_move = await AccountingService.post_depreciation_line(db_session, first_line.id, comp_id)
    assert posted_move.state == "posted"
    assert first_line.is_posted is True
    assert asset.book_value == Decimal("11000.0000")
    assert asset.state == "running"


@pytest.mark.asyncio
async def test_budgeting_planned_vs_actual_variance(db_session: AsyncSession):
    """Verify Budget variance calculation comparing Planned vs Actual from move lines."""
    comp_id = uuid.uuid4()
    company = Company(id=comp_id, name="Budget Co", code=f"BGT_{comp_id.hex[:4]}")
    curr = Currency(company_id=comp_id, code="USD", name="US Dollar", symbol="$", decimal_places=2)
    db_session.add_all([company, curr])
    await db_session.commit()

    today = date.today()

    # Expense Account
    exp_acc = await AccountingService.create_account(
        db_session, AccountCreate(code="610000", name="Software Subscriptions", account_type="expense"), comp_id
    )
    cash_acc = await AccountingService.create_account(
        db_session, AccountCreate(code="101000", name="Cash", account_type="asset_current"), comp_id
    )
    journal = await AccountingService.create_journal(
        db_session, AccountJournalCreate(code="GEN", name="General", type="general"), comp_id
    )

    # Budgetary Position
    pos = BudgetaryPosition(
        name="IT Subscriptions",
        code="IT_SUB",
        account_ids=[str(exp_acc.id)],
        company_id=comp_id,
    )
    db_session.add(pos)
    await db_session.commit()

    # Create Budget for full year: Planned $10,000
    date_from = date(today.year, 1, 1)
    date_to = date(today.year, 12, 31)
    budget = await AccountingService.create_budget(
        db_session,
        BudgetCreate(
            name="FY2026 IT Budget",
            date_from=date_from,
            date_to=date_to,
            lines=[
                BudgetLineCreate(
                    position_id=pos.id,
                    date_from=date_from,
                    date_to=date_to,
                    planned_amount=Decimal("10000.00"),
                )
            ],
        ),
        comp_id,
    )

    # Post an actual expense move of $2,500
    move = await AccountingService.create_move(
        db_session,
        AccountMoveCreate(
            move_type="entry",
            date=today,
            journal_id=journal.id,
            currency_id=curr.id,
            lines=[
                AccountMoveLineCreate(account_id=exp_acc.id, name="Cloud Server", debit=Decimal("2500.00"), credit=Decimal("0.00")),
                AccountMoveLineCreate(account_id=cash_acc.id, name="Paid Cash", debit=Decimal("0.00"), credit=Decimal("2500.00")),
            ],
        ),
        comp_id,
    )
    await AccountingService.post_move(db_session, move.id, comp_id)

    # Query Budget Analysis
    analysis = await AccountingService.get_budget_analysis(db_session, budget.id, comp_id)
    assert len(analysis) == 1
    item = analysis[0]
    assert item["planned_amount"] == 10000.00
    assert item["practical_amount"] == 2500.00
    assert item["variance"] == 7500.00
    assert item["percentage"] == 25.0


@pytest.mark.asyncio
async def test_sales_order_to_customer_invoice_bridge(db_session: AsyncSession):
    """Verify Sales Order creation, confirmation, and 1-click invoice generation in Accounting."""
    comp_id = uuid.uuid4()
    company = Company(id=comp_id, name="Sales Co", code=f"SLS_{comp_id.hex[:4]}")
    curr = Currency(company_id=comp_id, code="USD", name="US Dollar", symbol="$", decimal_places=2)
    customer = Party(company_id=comp_id, name="Acme Customer", is_customer=True)
    db_session.add_all([company, curr, customer])
    await db_session.commit()

    today = date.today()

    # Accounting prerequisites: AR Account, Sales Journal, Income Account
    ar_acc = await AccountingService.create_account(
        db_session, AccountCreate(code="120000", name="Accounts Receivable", account_type="asset_current", reconcilable=True), comp_id
    )
    income_acc = await AccountingService.create_account(
        db_session, AccountCreate(code="400000", name="Product Revenue", account_type="income"), comp_id
    )
    sale_journal = await AccountingService.create_journal(
        db_session, AccountJournalCreate(code="INV", name="Customer Invoices", type="sale", default_account_id=income_acc.id), comp_id
    )

    # 1. Create Sales Quotation
    so = await SaleService.create_order(
        db_session,
        SaleOrderCreate(
            party_id=customer.id,
            order_date=today,
            currency_id=curr.id,
            lines=[
                SaleOrderLineCreate(name="Enterprise Software License", quantity=Decimal("2.00"), unit_price=Decimal("1500.00")),
                SaleOrderLineCreate(name="Implementation Support", quantity=Decimal("10.00"), unit_price=Decimal("100.00")),
            ],
        ),
        comp_id,
    )
    assert so.amount_total == Decimal("4000.0000")  # (2*1500) + (10*100) = 4000
    assert so.state == "draft"

    # 2. Confirm Sales Order
    confirmed_so = await SaleService.confirm_order(db_session, so.id, comp_id)
    assert confirmed_so.state == "sale"
    assert confirmed_so.order_number != "Draft"

    # 3. 1-Click Invoice Generation
    invoice = await SaleService.create_invoice(db_session, confirmed_so.id, comp_id)
    assert invoice.id is not None
    assert invoice.move_type == "out_invoice"
    assert invoice.amount_total == Decimal("4000.0000")
    assert confirmed_so.invoice_status == "invoiced"

    # 4. Post the generated invoice in Accounting
    posted_inv = await AccountingService.post_move(db_session, invoice.id, comp_id)
    assert posted_inv.state == "posted"


@pytest.mark.asyncio
async def test_purchase_order_to_vendor_bill_bridge(db_session: AsyncSession):
    """Verify Purchase Order creation, confirmation, and 1-click bill generation in Accounting."""
    comp_id = uuid.uuid4()
    company = Company(id=comp_id, name="Purchase Co", code=f"PUR_{comp_id.hex[:4]}")
    curr = Currency(company_id=comp_id, code="USD", name="US Dollar", symbol="$", decimal_places=2)
    vendor = Party(company_id=comp_id, name="Global Supplies Ltd", is_vendor=True)
    db_session.add_all([company, curr, vendor])
    await db_session.commit()

    today = date.today()

    # Accounting prerequisites: AP Account, Purchase Journal, Expense Account
    ap_acc = await AccountingService.create_account(
        db_session, AccountCreate(code="210000", name="Accounts Payable", account_type="liability_current", reconcilable=True), comp_id
    )
    exp_acc = await AccountingService.create_account(
        db_session, AccountCreate(code="500000", name="Raw Materials Cost", account_type="expense"), comp_id
    )
    pur_journal = await AccountingService.create_journal(
        db_session, AccountJournalCreate(code="BILL", name="Vendor Bills", type="purchase", default_account_id=exp_acc.id), comp_id
    )

    # 1. Create Purchase Order
    po = await PurchaseService.create_order(
        db_session,
        PurchaseOrderCreate(
            party_id=vendor.id,
            order_date=today,
            currency_id=curr.id,
            lines=[
                PurchaseOrderLineCreate(name="Steel Rods 10mm", quantity=Decimal("50.00"), unit_price=Decimal("40.00")),
            ],
        ),
        comp_id,
    )
    assert po.amount_total == Decimal("2000.0000")

    # 2. Confirm PO (within threshold $5000)
    confirmed_po = await PurchaseService.confirm_order(db_session, po.id, comp_id)
    assert confirmed_po.state == "purchase"
    assert confirmed_po.order_number != "Draft"

    # 3. 1-Click Vendor Bill Generation
    bill = await PurchaseService.create_bill(db_session, confirmed_po.id, comp_id)
    assert bill.id is not None
    assert bill.move_type == "in_invoice"
    assert bill.amount_total == Decimal("2000.0000")
    assert confirmed_po.bill_status == "billed"

    # 4. Post the generated vendor bill in Accounting
    posted_bill = await AccountingService.post_move(db_session, bill.id, comp_id)
    assert posted_bill.state == "posted"


@pytest.mark.asyncio
async def test_trial_balance_financial_report(db_session: AsyncSession):
    """Verify real-time Trial Balance report calculation."""
    comp_id = uuid.uuid4()
    company = Company(id=comp_id, name="Report Co", code=f"REP_{comp_id.hex[:4]}")
    curr = Currency(company_id=comp_id, code="USD", name="US Dollar", symbol="$", decimal_places=2)
    db_session.add_all([company, curr])
    await db_session.commit()

    today = date.today()

    cash = await AccountingService.create_account(
        db_session, AccountCreate(code="101000", name="Cash", account_type="asset_current"), comp_id
    )
    rev = await AccountingService.create_account(
        db_session, AccountCreate(code="400000", name="Sales", account_type="income"), comp_id
    )
    journal = await AccountingService.create_journal(
        db_session, AccountJournalCreate(code="GEN", name="General", type="general"), comp_id
    )

    # Post Move: Debit Cash $3,000 / Credit Sales $3,000
    move = await AccountingService.create_move(
        db_session,
        AccountMoveCreate(
            move_type="entry",
            date=today,
            journal_id=journal.id,
            currency_id=curr.id,
            lines=[
                AccountMoveLineCreate(account_id=cash.id, name="Cash", debit=Decimal("3000.00"), credit=Decimal("0.00")),
                AccountMoveLineCreate(account_id=rev.id, name="Revenue", debit=Decimal("0.00"), credit=Decimal("3000.00")),
            ],
        ),
        comp_id,
    )
    await AccountingService.post_move(db_session, move.id, comp_id)

    # Query Trial Balance
    tb = await AccountingService.get_trial_balance(
        db_session, comp_id, date(today.year, 1, 1), date(today.year, 12, 31)
    )
    assert len(tb) >= 2
    cash_item = next(i for i in tb if i.account_code == "101000")
    rev_item = next(i for i in tb if i.account_code == "400000")

    assert cash_item.ending_debit == Decimal("3000.00")
    assert cash_item.ending_balance == Decimal("3000.00")
    assert rev_item.ending_credit == Decimal("3000.00")
    assert rev_item.ending_balance == Decimal("-3000.00")
