"""Comprehensive unit and integration tests for Payment Terms, Methods & Transactions."""

import uuid
import pytest
from decimal import Decimal
from datetime import date
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company
from modules.base.settings.service import SettingsService


@pytest.mark.asyncio
async def test_payment_methods_and_terms_crud(db_session: AsyncSession):
    """Verify CRUD for payment methods, terms, and multi-tenant isolation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_a = uuid.uuid4()
        comp_b = uuid.uuid4()
        db_session.add(Company(id=comp_a, name="Pay Co A", code=f"PA_{comp_a.hex[:4]}"))
        db_session.add(Company(id=comp_b, name="Pay Co B", code=f"PB_{comp_b.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_a, {"allow_registration": True})
        await SettingsService.update_settings(db_session, "identity_rbac", comp_b, {"allow_registration": True})

        # Register User A
        user_a = f"pay_a_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_a}@test.com", "username": user_a, "password": "Password123!", "full_name": "Pay Admin A", "company_id": str(comp_a)},
        )
        login_a = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_a, "password": "Password123!"})
        headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

        # Register User B
        user_b = f"pay_b_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_b}@test.com", "username": user_b, "password": "Password123!", "full_name": "Pay Admin B", "company_id": str(comp_b)},
        )
        login_b = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_b, "password": "Password123!"})
        headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

        # 1. Company A creates PaymentMethod
        res_method = await client.post(
            "/api/v1/payments/methods",
            json={"name": "Wire Transfer", "code": "WIRE", "method_type": "bank", "description": "Bank wire"},
            headers=headers_a,
        )
        assert res_method.status_code == 201, res_method.text
        method_id = res_method.json()["id"]

        # 2. Company A creates PaymentTerms
        res_terms = await client.post(
            "/api/v1/payments/terms",
            json={
                "name": "30% Advance, Balance 30 Days",
                "code": "30_ADV_30_NET",
                "lines": [
                    {"sequence": 10, "value_type": "percent", "value": "30.0000", "days": 0, "option": "days_after_invoice"},
                    {"sequence": 20, "value_type": "balance", "value": "0.0000", "days": 30, "option": "days_after_invoice"},
                ],
            },
            headers=headers_a,
        )
        assert res_terms.status_code == 201, res_terms.text
        terms_data = res_terms.json()
        assert len(terms_data["lines"]) == 2
        assert terms_data["lines"][0]["value_type"] == "percent"
        assert terms_data["lines"][1]["value_type"] == "balance"

        # 3. User B cannot see User A's payment methods or terms
        res_b_methods = await client.get("/api/v1/payments/methods", headers=headers_b)
        assert res_b_methods.status_code == 200
        assert len(res_b_methods.json()) == 0

        res_b_terms = await client.get("/api/v1/payments/terms", headers=headers_b)
        assert res_b_terms.status_code == 200
        assert len(res_b_terms.json()) == 0


@pytest.mark.asyncio
async def test_payment_terms_due_dates_calculation(db_session: AsyncSession):
    """Verify due date calculation with End-of-Month and offset days."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Terms Calc Co", code=f"TC_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        user_name = f"terms_u_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_name}@test.com", "username": user_name, "password": "Password123!", "full_name": "Terms User", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_name, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # Create terms: 50% End of Month, 50% 15 Days after End of Month
        res_terms = await client.post(
            "/api/v1/payments/terms",
            json={
                "name": "50% EOM, 50% EOM+15",
                "code": "EOM_SPLIT",
                "lines": [
                    {"sequence": 10, "value_type": "percent", "value": "50.0000", "days": 0, "option": "end_of_month"},
                    {"sequence": 20, "value_type": "balance", "value": "0.0000", "days": 15, "option": "days_after_end_of_month"},
                ],
            },
            headers=headers,
        )
        terms_id = res_terms.json()["id"]

        # Compute schedule on Feb 10, 2026 for amount 2000.00
        res_sched = await client.post(
            "/api/v1/payments/terms/compute-schedule",
            json={
                "total_amount": "2000.00",
                "terms_id": terms_id,
                "invoice_date": "2026-02-10",
                "currency_rounding": "0.01",
            },
            headers=headers,
        )
        assert res_sched.status_code == 200, res_sched.text
        sched = res_sched.json()
        assert sched["total_amount"] == "2000.00"
        assert len(sched["installments"]) == 2

        # Installment 1: due 2026-02-28, amount 1000.00 (50%)
        inst1 = sched["installments"][0]
        assert inst1["installment_number"] == 1
        assert inst1["due_date"] == "2026-02-28"
        assert inst1["amount"] == "1000.00"
        assert inst1["percentage"] == "50.00"

        # Installment 2: due 2026-03-15 (Feb 28 + 15 days), amount 1000.00 (50%)
        inst2 = sched["installments"][1]
        assert inst2["installment_number"] == 2
        assert inst2["due_date"] == "2026-03-15"
        assert inst2["amount"] == "1000.00"
        assert inst2["percentage"] == "50.00"


@pytest.mark.asyncio
async def test_payment_transaction_lifecycle(db_session: AsyncSession):
    """Verify transaction creation, clear, reconcile, and cancel safeguards."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Txn Life Co", code=f"TL_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        user_name = f"txn_u_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_name}@test.com", "username": user_name, "password": "Password123!", "full_name": "Txn User", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_name, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 1. Create Payment Method
        res_m = await client.post(
            "/api/v1/payments/methods",
            json={"name": "Corporate Credit Card", "code": "CC_CORP", "method_type": "electronic"},
            headers=headers,
        )
        method_id = res_m.json()["id"]

        # 2. Create Transaction 1 in Draft
        res_tx1 = await client.post(
            "/api/v1/payments/transactions",
            json={
                "payment_number": "PAY-2026-0001",
                "payment_method_id": method_id,
                "transaction_type": "inbound",
                "amount": "850.50",
                "reference": "STRIPE-CHG-9988",
            },
            headers=headers,
        )
        assert res_tx1.status_code == 201, res_tx1.text
        tx1_id = res_tx1.json()["id"]
        assert res_tx1.json()["status"] == "draft"
        assert res_tx1.json()["payment_method_name"] == "Corporate Credit Card"

        # 3. Transition: Draft -> Cleared
        res_clear = await client.post(f"/api/v1/payments/transactions/{tx1_id}/clear", headers=headers)
        assert res_clear.status_code == 200
        assert res_clear.json()["status"] == "cleared"

        # 4. Transition: Cleared -> Reconciled
        res_rec = await client.post(f"/api/v1/payments/transactions/{tx1_id}/reconcile", headers=headers)
        assert res_rec.status_code == 200
        assert res_rec.json()["status"] == "reconciled"

        # 5. Cannot cancel a reconciled transaction (must fail)
        res_cancel_fail = await client.post(f"/api/v1/payments/transactions/{tx1_id}/cancel", headers=headers)
        assert res_cancel_fail.status_code == 400

        # 6. Create Transaction 2 and Cancel it
        res_tx2 = await client.post(
            "/api/v1/payments/transactions",
            json={
                "payment_number": "PAY-2026-0002",
                "payment_method_id": method_id,
                "transaction_type": "outbound",
                "amount": "120.00",
            },
            headers=headers,
        )
        tx2_id = res_tx2.json()["id"]

        res_cancel = await client.post(f"/api/v1/payments/transactions/{tx2_id}/cancel", headers=headers)
        assert res_cancel.status_code == 200
        assert res_cancel.json()["status"] == "cancelled"
