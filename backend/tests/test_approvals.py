"""Comprehensive unit and integration tests for Multi-Level Governance & Approval Engine."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company, User
from modules.base.settings.service import SettingsService


@pytest.mark.asyncio
async def test_approval_rule_crud(db_session: AsyncSession):
    """Verify approval rule registration, retrieval, updating, and deletion."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Approval Test Co", code=f"AP_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"ap_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Approval Admin", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 1. Create Approval Rule
        rule_payload = {
            "name": "High Credit Limit Gate",
            "code": "rule_high_credit",
            "res_model": "party",
            "tier": 1,
            "condition": {
                "field": "credit_limit",
                "operator": "gt",
                "value": 50000.0,
            },
            "is_active": True,
        }
        res_create = await client.post("/api/v1/approvals/rules", json=rule_payload, headers=headers)
        assert res_create.status_code == 201, res_create.text
        rule_data = res_create.json()
        rule_id = rule_data["id"]
        assert rule_data["code"] == "rule_high_credit"
        assert rule_data["tier"] == 1

        # 2. Get Approval Rule
        res_get = await client.get(f"/api/v1/approvals/rules/{rule_id}", headers=headers)
        assert res_get.status_code == 200
        assert res_get.json()["name"] == "High Credit Limit Gate"

        # 3. List Rules
        res_list = await client.get("/api/v1/approvals/rules?res_model=party", headers=headers)
        assert res_list.status_code == 200
        assert len(res_list.json()) == 1

        # 4. Update Rule
        res_up = await client.put(
            f"/api/v1/approvals/rules/{rule_id}",
            json={"tier": 2, "name": "Executive Credit Limit Gate"},
            headers=headers,
        )
        assert res_up.status_code == 200
        assert res_up.json()["tier"] == 2

        # 5. Delete Rule
        res_del = await client.delete(f"/api/v1/approvals/rules/{rule_id}", headers=headers)
        assert res_del.status_code == 200
        assert res_del.json()["status"] == "success"


@pytest.mark.asyncio
async def test_approval_request_submission_and_inbox(db_session: AsyncSession):
    """Verify submitting approval requests and routing to the designated approver's inbox."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Inbox Test Co", code=f"IB_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        # Register Approver User
        approver_name = f"approver_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{approver_name}@test.com", "username": approver_name, "password": "Password123!", "full_name": "Chief Approver", "company_id": str(comp_id)},
        )
        appr_login = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": approver_name, "password": "Password123!"})
        appr_headers = {"Authorization": f"Bearer {appr_login.json()['access_token']}"}

        # Query approver user ID
        from sqlalchemy import select
        appr_user = (await db_session.execute(select(User).where(User.username == approver_name))).scalar_one()

        # Register Requester User
        req_name = f"requester_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{req_name}@test.com", "username": req_name, "password": "Password123!", "full_name": "Sales Rep", "company_id": str(comp_id)},
        )
        req_login = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": req_name, "password": "Password123!"})
        req_headers = {"Authorization": f"Bearer {req_login.json()['access_token']}"}

        # 1. Create Approval Rule assigned specifically to Chief Approver
        rule_payload = {
            "name": "Partner Credit Approval",
            "code": "rule_party_credit",
            "res_model": "party",
            "tier": 1,
            "approver_user_id": str(appr_user.id),
            "condition": {
                "field": "credit_limit",
                "operator": "gt",
                "value": 20000.0,
            },
            "is_active": True,
        }
        await client.post("/api/v1/approvals/rules", json=rule_payload, headers=req_headers)

        # 2. Create Party
        party_res = await client.post(
            "/api/v1/parties/",
            json={"name": "Big Enterprise Client", "credit_limit": 75000.0, "is_customer": True},
            headers=req_headers,
        )
        party_id = party_res.json()["id"]

        # 3. Requester submits Approval Request
        req_res = await client.post(
            "/api/v1/approvals/requests",
            json={"res_model": "party", "res_id": party_id, "summary": "Requesting 75k credit facility"},
            headers=req_headers,
        )
        assert req_res.status_code == 201, req_res.text
        req_id = req_res.json()["id"]
        assert req_res.json()["state"] == "pending"
        assert req_res.json()["approver_user_id"] == str(appr_user.id)

        # 4. Requester views inbox: should be empty (not the assigned approver)
        req_inbox = await client.get("/api/v1/approvals/inbox", headers=req_headers)
        assert req_inbox.status_code == 200
        assert len(req_inbox.json()) == 0

        # 5. Chief Approver views inbox: should see the ticket!
        appr_inbox = await client.get("/api/v1/approvals/inbox", headers=appr_headers)
        assert appr_inbox.status_code == 200
        inbox_items = appr_inbox.json()
        assert len(inbox_items) == 1
        assert inbox_items[0]["id"] == req_id


@pytest.mark.asyncio
async def test_approval_decision_approve_and_audit_action(db_session: AsyncSession):
    """Verify approval sign-off, state update, and action history trail."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Decision Test Co", code=f"DC_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"dc_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Decision Maker", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # Make user superuser so they can act as company-wide approver
        from sqlalchemy import select
        u = (await db_session.execute(select(User).where(User.username == username))).scalar_one()
        u.is_superuser = True
        await db_session.commit()

        # 1. Create Party
        party_res = await client.post("/api/v1/parties/", json={"name": "Decision Partner"}, headers=headers)
        party_id = party_res.json()["id"]

        # 2. Submit Approval Request
        req_res = await client.post(
            "/api/v1/approvals/requests",
            json={"res_model": "party", "res_id": party_id, "summary": "Standard verification"},
            headers=headers,
        )
        req_id = req_res.json()["id"]

        # 3. Approve Request
        decision_payload = {"comments": "Credit verification passed with flying colors."}
        appr_res = await client.post(
            f"/api/v1/approvals/requests/{req_id}/approve",
            json=decision_payload,
            headers=headers,
        )
        assert appr_res.status_code == 200
        dec_data = appr_res.json()
        assert dec_data["state"] == "approved"
        assert dec_data["action"] == "approve"
        assert dec_data["comments"] == "Credit verification passed with flying colors."

        # 4. Retrieve Request with populated action audit trail
        get_res = await client.get(f"/api/v1/approvals/requests/{req_id}", headers=headers)
        assert get_res.status_code == 200
        req_data = get_res.json()
        assert req_data["state"] == "approved"
        assert len(req_data["actions"]) == 1
        assert req_data["actions"][0]["action"] == "approve"
        assert req_data["actions"][0]["comments"] == "Credit verification passed with flying colors."

        # 5. Query Entity Approval History
        entity_res = await client.get(f"/api/v1/approvals/entity/party/{party_id}", headers=headers)
        assert entity_res.status_code == 200
        assert len(entity_res.json()) == 1


@pytest.mark.asyncio
async def test_approval_decision_reject_and_unauthorized_block(db_session: AsyncSession):
    """Verify unauthorized actors cannot approve/reject, and reject action works properly."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Security Test Co", code=f"SC_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        # Approver
        approver_name = f"sec_appr_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{approver_name}@test.com", "username": approver_name, "password": "Password123!", "full_name": "Official Approver", "company_id": str(comp_id)},
        )
        appr_login = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": approver_name, "password": "Password123!"})
        appr_headers = {"Authorization": f"Bearer {appr_login.json()['access_token']}"}

        from sqlalchemy import select
        appr_user = (await db_session.execute(select(User).where(User.username == approver_name))).scalar_one()

        # Unauthorized Intruder
        intruder_name = f"intruder_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{intruder_name}@test.com", "username": intruder_name, "password": "Password123!", "full_name": "Intruder", "company_id": str(comp_id)},
        )
        int_login = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": intruder_name, "password": "Password123!"})
        int_headers = {"Authorization": f"Bearer {int_login.json()['access_token']}"}

        # 1. Create Rule assigned to Official Approver
        await client.post(
            "/api/v1/approvals/rules",
            json={
                "name": "Locked Rule",
                "code": "rule_locked",
                "res_model": "party",
                "tier": 1,
                "approver_user_id": str(appr_user.id),
                "is_active": True,
            },
            headers=appr_headers,
        )

        # 2. Create Party & Submit Request
        party_res = await client.post("/api/v1/parties/", json={"name": "Secure Party"}, headers=appr_headers)
        party_id = party_res.json()["id"]

        req_res = await client.post(
            "/api/v1/approvals/requests",
            json={"res_model": "party", "res_id": party_id, "summary": "Secured check"},
            headers=appr_headers,
        )
        req_id = req_res.json()["id"]

        # 3. Intruder attempts to approve: must fail with 403 Forbidden!
        bad_appr = await client.post(
            f"/api/v1/approvals/requests/{req_id}/approve",
            json={"comments": "I am not authorized"},
            headers=int_headers,
        )
        assert bad_appr.status_code == 403

        # 4. Official Approver rejects: succeeds!
        rej_res = await client.post(
            f"/api/v1/approvals/requests/{req_id}/reject",
            json={"comments": "Credit score too low."},
            headers=appr_headers,
        )
        assert rej_res.status_code == 200
        assert rej_res.json()["state"] == "rejected"
        assert rej_res.json()["action"] == "reject"
