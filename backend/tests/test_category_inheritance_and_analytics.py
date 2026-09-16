"""Comprehensive tests for Category Default Inheritance and Analytic Account Auto-Cascading."""

import uuid
import pytest
from decimal import Decimal
from datetime import date
from sqlalchemy import select
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company, User
from modules.base.settings.service import SettingsService
from modules.base.uom.models import UOMCategory, UOMUnit
from modules.base.parties.models import Party
from modules.base.lookups.models import Currency, Category
from modules.base.products.models import Product
from modules.base.products.service import ProductService
from modules.apps.accounting.models import (
    Account,
    AccountJournal,
    AnalyticPlan,
    AnalyticAccount,
    AccountMove,
)
from modules.apps.accounting.service import AccountingService
from modules.apps.accounting.schemas import AccountMoveCreate, AccountMoveLineCreate


@pytest.mark.asyncio
async def test_product_category_hierarchy_defaults_and_override(db_session: AsyncSession):
    """Verify recursive Category accounts & taxes inheritance and product-level overrides."""
    company_id = uuid.uuid4()
    db_session.add(Company(id=company_id, name="Hierarchy Corp", code=f"HC_{company_id.hex[:4]}"))
    await db_session.commit()

    # Create Accounts
    income_acc = Account(
        company_id=company_id,
        code="400001",
        name="Category Income Account",
        account_type="income",
    )
    expense_acc = Account(
        company_id=company_id,
        code="500001",
        name="Category Expense Account",
        account_type="expense",
    )
    override_income_acc = Account(
        company_id=company_id,
        code="400099",
        name="Product Custom Income",
        account_type="income",
    )
    db_session.add_all([income_acc, expense_acc, override_income_acc])

    # UoM Unit
    uom_cat = UOMCategory(company_id=company_id, name="Units")
    db_session.add(uom_cat)
    await db_session.flush()
    uom = UOMUnit(
        company_id=company_id,
        category_id=uom_cat.id,
        name="Unit",
        code="UNT",
        symbol="u",
        uom_type="reference",
        ratio=Decimal("1.0000"),
    )
    db_session.add(uom)
    await db_session.commit()

    sale_tax_uuid = uuid.uuid4()
    purch_tax_uuid = uuid.uuid4()

    # 1. Root Category: defines income_account_id and sale_tax_ids
    root_cat = Category(
        company_id=company_id,
        name="Electronics",
        code="ELEC",
        res_model="product",
        custom_fields={
            "income_account_id": str(income_acc.id),
            "sale_tax_ids": [str(sale_tax_uuid)],
        },
    )
    db_session.add(root_cat)
    await db_session.flush()

    # 2. Sub Category (child of Root): defines expense_account_id and purchase_tax_ids
    sub_cat = Category(
        company_id=company_id,
        name="Smartphones",
        code="SMART",
        res_model="product",
        parent_id=root_cat.id,
        custom_fields={
            "expense_account_id": str(expense_acc.id),
            "purchase_tax_ids": [str(purch_tax_uuid)],
        },
    )
    db_session.add(sub_cat)
    await db_session.commit()

    # 3. Product A: Assigned to sub_cat, leaves accounts and taxes blank
    prod_a = Product(
        company_id=company_id,
        name="Flagship Phone A",
        code="PHONE-A",
        uom_id=uom.id,
        category_id=sub_cat.id,
        sale_price=Decimal("999.00"),
        cost_price=Decimal("600.00"),
    )
    # 4. Product B: Assigned to sub_cat, overrides income_account_id
    prod_b = Product(
        company_id=company_id,
        name="Custom Phone B",
        code="PHONE-B",
        uom_id=uom.id,
        category_id=sub_cat.id,
        sale_price=Decimal("1200.00"),
        cost_price=Decimal("700.00"),
        income_account_id=override_income_acc.id,
    )
    db_session.add_all([prod_a, prod_b])
    await db_session.commit()

    # Test Product A (full inheritance across tree)
    sale_defaults_a = await ProductService.resolve_product_defaults(db_session, company_id, prod_a.id, for_operation="sale")
    # Inherits income_account_id and sale_tax_ids from root ancestor!
    assert sale_defaults_a["account_id"] == str(income_acc.id)
    assert sale_defaults_a["tax_ids"] == [str(sale_tax_uuid)]

    purch_defaults_a = await ProductService.resolve_product_defaults(db_session, company_id, prod_a.id, for_operation="purchase")
    # Inherits expense_account_id and purchase_tax_ids from direct category!
    assert purch_defaults_a["account_id"] == str(expense_acc.id)
    assert purch_defaults_a["tax_ids"] == [str(purch_tax_uuid)]

    # Test Product B (override income account, inherit taxes from category tree)
    sale_defaults_b = await ProductService.resolve_product_defaults(db_session, company_id, prod_b.id, for_operation="sale")
    assert sale_defaults_b["account_id"] == str(override_income_acc.id)
    assert sale_defaults_b["tax_ids"] == [str(sale_tax_uuid)]


@pytest.mark.asyncio
async def test_sales_analytic_cascading_and_invoice_line_forwarding(db_session: AsyncSession):
    """Verify SO header analytic cascading to lines, line override, and invoice line propagation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        company_id = uuid.uuid4()
        db_session.add(Company(id=company_id, name="Sales Analytic Corp", code=f"SAC_{company_id.hex[:4]}"))
        await db_session.commit()

        await SettingsService.update_settings(db_session, "identity_rbac", company_id, {"allow_registration": True})

        # Register User
        username = f"sa_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Sales Analyst", "company_id": str(company_id)},
        )
        user = (await db_session.execute(select(User).where(User.username == username))).scalar_one()
        user.is_superuser = True
        await db_session.commit()

        login = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        # Seed Currency, Party, Accounts, Journal, Analytic Plan & Accounts
        curr = Currency(company_id=company_id, code="USD", name="US Dollar", symbol="$", decimal_places=2, is_base=True)
        party = Party(company_id=company_id, name="Customer Mega Corp", is_customer=True)
        db_session.add_all([curr, party])

        recv_acc = Account(company_id=company_id, code="120000", name="Accounts Receivable", account_type="receivable")
        rev_acc = Account(company_id=company_id, code="400000", name="General Sales Revenue", account_type="income")
        journal = AccountJournal(company_id=company_id, name="Customer Invoices", code="INV", type="sale", default_account_id=rev_acc.id)
        db_session.add_all([recv_acc, rev_acc, journal])

        plan = AnalyticPlan(company_id=company_id, name="Department Plan", code="DEP")
        db_session.add(plan)
        await db_session.flush()

        analytic_hdr = AnalyticAccount(company_id=company_id, plan_id=plan.id, code="CORP-SALES", name="Corporate Sales")
        analytic_line2 = AnalyticAccount(company_id=company_id, plan_id=plan.id, code="RND-SPEC", name="R&D Projects")
        db_session.add_all([analytic_hdr, analytic_line2])

        # UOM and Products
        uom_cat = UOMCategory(company_id=company_id, name="Units")
        db_session.add(uom_cat)
        await db_session.flush()
        uom = UOMUnit(company_id=company_id, category_id=uom_cat.id, name="Unit", code="UNT", symbol="u", uom_type="reference", ratio=Decimal("1.0000"))
        db_session.add(uom)
        await db_session.flush()

        prod1 = Product(company_id=company_id, name="Widget Alpha", code="WID-A", uom_id=uom.id, sale_price=Decimal("100.00"), cost_price=Decimal("50.00"))
        prod2 = Product(company_id=company_id, name="Widget Beta", code="WID-B", uom_id=uom.id, sale_price=Decimal("200.00"), cost_price=Decimal("80.00"))
        db_session.add_all([prod1, prod2])
        await db_session.commit()

        # Create Sales Order with header analytic_account_id
        # Line 1: leaves analytic_account_id and analytic_distribution empty -> should inherit header!
        # Line 2: sets analytic_account_id to analytic_line2 -> line-level override!
        so_resp = await client.post(
            "/api/v1/sales/orders",
            json={
                "party_id": str(party.id),
                "order_date": str(date.today()),
                "currency_id": str(curr.id),
                "analytic_account_id": str(analytic_hdr.id),
                "lines": [
                    {
                        "product_id": str(prod1.id),
                        "quantity": 2.0,
                        "unit_price": 100.0,
                    },
                    {
                        "product_id": str(prod2.id),
                        "quantity": 1.0,
                        "unit_price": 200.0,
                        "analytic_account_id": str(analytic_line2.id),
                    },
                ],
            },
            headers=headers,
        )
        assert so_resp.status_code == 201, so_resp.text
        so_data = so_resp.json()
        assert so_data["analytic_account_id"] == str(analytic_hdr.id)
        assert len(so_data["lines"]) == 2

        line1 = so_data["lines"][0]
        line2 = so_data["lines"][1]
        # Line 1 auto-cascaded header analytic
        assert line1["analytic_distribution"] == {str(analytic_hdr.id): 100.0}
        assert line1["analytic_account_id"] == str(analytic_hdr.id)
        # Line 2 used line override
        assert line2["analytic_distribution"] == {str(analytic_line2.id): 100.0}
        assert line2["analytic_account_id"] == str(analytic_line2.id)

        # Confirm SO
        conf_resp = await client.post(f"/api/v1/sales/orders/{so_data['id']}/confirm", headers=headers)
        assert conf_resp.status_code == 200

        # Trigger 1-click Invoice creation
        inv_resp = await client.post(f"/api/v1/sales/orders/{so_data['id']}/create-invoice", headers=headers)
        assert inv_resp.status_code == 200, inv_resp.text
        inv_data = inv_resp.json()

        # Check invoice header has analytic_account_id
        assert inv_data["analytic_account_id"] == str(analytic_hdr.id)
        assert inv_data["move_type"] == "out_invoice"

        # Check invoice lines: 1 AR line + 2 Revenue lines mirroring the SO lines
        inv_lines = inv_data["lines"]
        assert len(inv_lines) == 3
        # Debit line (AR)
        ar_line = next(l for l in inv_lines if float(l["debit"]) > 0)
        assert float(ar_line["debit"]) == 400.0

        # Credit lines (Revenue)
        rev_lines = [l for l in inv_lines if float(l["credit"]) > 0]
        assert len(rev_lines) == 2

        # First rev line matches product 1 and has header analytic distribution
        r1 = next(l for l in rev_lines if l["product_id"] == str(prod1.id))
        assert float(r1["credit"]) == 200.0
        assert r1["analytic_distribution"] == {str(analytic_hdr.id): 100.0}
        assert r1["analytic_account_id"] == str(analytic_hdr.id)

        # Second rev line matches product 2 and has line override analytic distribution
        r2 = next(l for l in rev_lines if l["product_id"] == str(prod2.id))
        assert float(r2["credit"]) == 200.0
        assert r2["analytic_distribution"] == {str(analytic_line2.id): 100.0}
        assert r2["analytic_account_id"] == str(analytic_line2.id)


@pytest.mark.asyncio
async def test_purchases_analytic_cascading_and_bill_line_forwarding(db_session: AsyncSession):
    """Verify PO header analytic cascading to lines, line override, and vendor bill line propagation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        company_id = uuid.uuid4()
        db_session.add(Company(id=company_id, name="Purch Analytic Corp", code=f"PAC_{company_id.hex[:4]}"))
        await db_session.commit()

        await SettingsService.update_settings(db_session, "identity_rbac", company_id, {"allow_registration": True})

        # Register User
        username = f"po_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Purch Analyst", "company_id": str(company_id)},
        )
        user = (await db_session.execute(select(User).where(User.username == username))).scalar_one()
        user.is_superuser = True
        await db_session.commit()

        login = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        # Seed Currency, Party, Accounts, Journal, Analytic Plan & Accounts
        curr = Currency(company_id=company_id, code="USD", name="US Dollar", symbol="$", decimal_places=2, is_base=True)
        party = Party(company_id=company_id, name="Vendor Supplier Global", is_vendor=True)
        db_session.add_all([curr, party])

        pay_acc = Account(company_id=company_id, code="220000", name="Accounts Payable", account_type="payable")
        exp_acc = Account(company_id=company_id, code="500000", name="Cost of Goods Sold", account_type="expense")
        journal = AccountJournal(company_id=company_id, name="Vendor Bills", code="BILL", type="purchase", default_account_id=exp_acc.id)
        db_session.add_all([pay_acc, exp_acc, journal])

        plan = AnalyticPlan(company_id=company_id, name="Cost Center Plan", code="CC")
        db_session.add(plan)
        await db_session.flush()

        analytic_po_hdr = AnalyticAccount(company_id=company_id, plan_id=plan.id, code="PO-OPS", name="Operations Cost")
        analytic_po_line2 = AnalyticAccount(company_id=company_id, plan_id=plan.id, code="PO-IT", name="IT Equipment")
        db_session.add_all([analytic_po_hdr, analytic_po_line2])

        # UOM and Products
        uom_cat = UOMCategory(company_id=company_id, name="Units")
        db_session.add(uom_cat)
        await db_session.flush()
        uom = UOMUnit(company_id=company_id, category_id=uom_cat.id, name="Unit", code="UNT", symbol="u", uom_type="reference", ratio=Decimal("1.0000"))
        db_session.add(uom)
        await db_session.flush()

        prod1 = Product(company_id=company_id, name="Hardware A", code="HW-A", uom_id=uom.id, cost_price=Decimal("150.00"))
        prod2 = Product(company_id=company_id, name="Hardware B", code="HW-B", uom_id=uom.id, cost_price=Decimal("300.00"))
        db_session.add_all([prod1, prod2])
        await db_session.commit()

        # Create Purchase Order with header analytic_account_id
        # Line 1: leaves analytic_account_id and analytic_distribution empty -> should inherit header!
        # Line 2: sets analytic_account_id to analytic_po_line2 -> line-level override!
        po_resp = await client.post(
            "/api/v1/purchases/orders",
            json={
                "party_id": str(party.id),
                "order_date": str(date.today()),
                "currency_id": str(curr.id),
                "analytic_account_id": str(analytic_po_hdr.id),
                "lines": [
                    {
                        "product_id": str(prod1.id),
                        "quantity": 2.0,
                        "unit_price": 150.0,
                    },
                    {
                        "product_id": str(prod2.id),
                        "quantity": 1.0,
                        "unit_price": 300.0,
                        "analytic_account_id": str(analytic_po_line2.id),
                    },
                ],
            },
            headers=headers,
        )
        assert po_resp.status_code == 201, po_resp.text
        po_data = po_resp.json()
        assert po_data["analytic_account_id"] == str(analytic_po_hdr.id)
        assert len(po_data["lines"]) == 2

        line1 = po_data["lines"][0]
        line2 = po_data["lines"][1]
        # Line 1 auto-cascaded header analytic
        assert line1["analytic_distribution"] == {str(analytic_po_hdr.id): 100.0}
        assert line1["analytic_account_id"] == str(analytic_po_hdr.id)
        # Line 2 used line override
        assert line2["analytic_distribution"] == {str(analytic_po_line2.id): 100.0}
        assert line2["analytic_account_id"] == str(analytic_po_line2.id)

        # Confirm PO
        conf_resp = await client.post(f"/api/v1/purchases/orders/{po_data['id']}/confirm", headers=headers)
        assert conf_resp.status_code == 200

        # Trigger 1-click Bill creation
        bill_resp = await client.post(f"/api/v1/purchases/orders/{po_data['id']}/create-bill", headers=headers)
        assert bill_resp.status_code == 200, bill_resp.text
        bill_data = bill_resp.json()

        # Check bill header has analytic_account_id
        assert bill_data["analytic_account_id"] == str(analytic_po_hdr.id)
        assert bill_data["move_type"] == "in_invoice"

        # Check bill lines: 2 Expense lines + 1 AP line
        bill_lines = bill_data["lines"]
        assert len(bill_lines) == 3

        # Credit line (AP)
        ap_line = next(l for l in bill_lines if float(l["credit"]) > 0)
        assert float(ap_line["credit"]) == 600.0

        # Debit lines (Expense)
        exp_lines = [l for l in bill_lines if float(l["debit"]) > 0]
        assert len(exp_lines) == 2

        # First exp line matches product 1 and has header analytic distribution
        e1 = next(l for l in exp_lines if l["product_id"] == str(prod1.id))
        assert float(e1["debit"]) == 300.0
        assert e1["analytic_distribution"] == {str(analytic_po_hdr.id): 100.0}
        assert e1["analytic_account_id"] == str(analytic_po_hdr.id)

        # Second exp line matches product 2 and has line override analytic distribution
        e2 = next(l for l in exp_lines if l["product_id"] == str(prod2.id))
        assert float(e2["debit"]) == 300.0
        assert e2["analytic_distribution"] == {str(analytic_po_line2.id): 100.0}
        assert e2["analytic_account_id"] == str(analytic_po_line2.id)


@pytest.mark.asyncio
async def test_direct_journal_move_analytic_cascading(db_session: AsyncSession):
    """Verify AccountMove header analytic cascades to lines on direct creation."""
    company_id = uuid.uuid4()
    db_session.add(Company(id=company_id, name="Direct Move Corp", code=f"DMC_{company_id.hex[:4]}"))
    await db_session.commit()

    curr = Currency(company_id=company_id, code="USD", name="US Dollar", symbol="$", decimal_places=2, is_base=True)
    acc1 = Account(company_id=company_id, code="101000", name="Bank", account_type="asset_cash")
    acc2 = Account(company_id=company_id, code="601000", name="Consulting Expense", account_type="expense")
    journal = AccountJournal(company_id=company_id, name="General Journal", code="GEN", type="general", default_account_id=acc1.id)
    plan = AnalyticPlan(company_id=company_id, name="Plan General", code="PL-GEN")
    db_session.add_all([curr, acc1, acc2, journal, plan])
    await db_session.flush()

    analytic_hdr = AnalyticAccount(company_id=company_id, plan_id=plan.id, code="AN-HDR", name="Header Cost Center")
    analytic_override = AnalyticAccount(company_id=company_id, plan_id=plan.id, code="AN-OVR", name="Override Center")
    db_session.add_all([analytic_hdr, analytic_override])
    await db_session.commit()

    payload = AccountMoveCreate(
        move_type="entry",
        date=date.today(),
        journal_id=journal.id,
        currency_id=curr.id,
        analytic_account_id=analytic_hdr.id,
        lines=[
            # Line 1: debit, no analytic info -> should inherit analytic_hdr
            AccountMoveLineCreate(
                account_id=acc2.id,
                name="Consulting Service",
                debit=Decimal("500.00"),
                credit=Decimal("0.00"),
            ),
            # Line 2: credit, explicit analytic_account_id -> should get analytic_override
            AccountMoveLineCreate(
                account_id=acc1.id,
                name="Bank Payment",
                debit=Decimal("0.00"),
                credit=Decimal("500.00"),
                analytic_account_id=analytic_override.id,
            ),
        ],
    )

    move = await AccountingService.create_move(db_session, payload, company_id)
    assert move.analytic_account_id == analytic_hdr.id
    assert len(move.lines) == 2

    # Verify line 1 cascaded header analytic
    line1 = move.lines[0]
    assert line1.analytic_distribution == {str(analytic_hdr.id): 100.0}
    assert line1.analytic_account_id == analytic_hdr.id

    # Verify line 2 has override
    line2 = move.lines[1]
    assert line2.analytic_distribution == {str(analytic_override.id): 100.0}
    assert line2.analytic_account_id == analytic_override.id
