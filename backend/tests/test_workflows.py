"""Comprehensive unit and integration tests for Declarative Workflow State Machine & Record Freeze."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company
from modules.base.settings.service import SettingsService
from modules.base.parties.models import Party


@pytest.mark.asyncio
async def test_workflow_definition_crud_and_transitions(db_session: AsyncSession):
    """Verify workflow definition registration, state list declaration, and transitions addition."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Workflow Test Co", code=f"WF_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"wf_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "WF Admin", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 1. Create Workflow Definition for Party
        def_payload = {
            "name": "Party Lifecycle Governance",
            "code": "wf_party_governance",
            "res_model": "party",
            "state_field": "state",
            "initial_state": "draft",
            "states": [
                {"code": "draft", "label": "Draft", "is_frozen": False, "sequence": 10},
                {"code": "verified", "label": "Verified", "is_frozen": False, "sequence": 20},
                {"code": "active", "label": "Active & Approved", "is_frozen": True, "sequence": 30},
                {"code": "suspended", "label": "Suspended", "is_frozen": True, "sequence": 40},
            ],
            "is_active": True,
            "transitions": [
                {
                    "trigger_name": "verify",
                    "from_state": "draft",
                    "to_state": "verified",
                    "freeze_record": False,
                    "sequence": 10,
                },
                {
                    "trigger_name": "activate",
                    "from_state": "verified",
                    "to_state": "active",
                    "freeze_record": True,
                    "sequence": 20,
                },
            ],
        }

        res = await client.post("/api/v1/workflows/definitions", json=def_payload, headers=headers)
        assert res.status_code == 201, res.text
        wf_data = res.json()
        wf_id = wf_data["id"]
        assert wf_data["code"] == "wf_party_governance"
        assert len(wf_data["transitions"]) == 2

        # 2. Add another transition dynamically
        trans_payload = {
            "trigger_name": "suspend",
            "from_state": "*",
            "to_state": "suspended",
            "freeze_record": True,
            "sequence": 30,
        }
        res_t = await client.post(f"/api/v1/workflows/definitions/{wf_id}/transitions", json=trans_payload, headers=headers)
        assert res_t.status_code == 201
        assert res_t.json()["trigger_name"] == "suspend"

        # 3. Retrieve definition with all 3 transitions
        res_get = await client.get(f"/api/v1/workflows/definitions/{wf_id}", headers=headers)
        assert res_get.status_code == 200
        assert len(res_get.json()["transitions"]) == 3

        # 4. List definitions filtered by res_model
        res_list = await client.get("/api/v1/workflows/definitions?res_model=party", headers=headers)
        assert res_list.status_code == 200
        assert len(res_list.json()) == 1


@pytest.mark.asyncio
async def test_workflow_transition_execution_and_guards(db_session: AsyncSession):
    """Verify AST condition guard evaluation and state machine progression."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Guard Test Co", code=f"GD_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"gd_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Guard Tester", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 1. Create Workflow Definition with Guard Condition on credit_limit >= 1000
        def_payload = {
            "name": "Customer Credit Validation Workflow",
            "code": "wf_customer_credit",
            "res_model": "party",
            "state_field": "state",
            "initial_state": "draft",
            "states": [
                {"code": "draft", "label": "Draft", "is_frozen": False, "sequence": 10},
                {"code": "approved", "label": "Credit Approved", "is_frozen": False, "sequence": 20},
            ],
            "is_active": True,
            "transitions": [
                {
                    "trigger_name": "approve_credit",
                    "from_state": "draft",
                    "to_state": "approved",
                    "guard_condition": {
                        "field": "credit_limit",
                        "operator": "gte",
                        "value": 1000.0,
                    },
                    "freeze_record": False,
                    "sequence": 10,
                }
            ],
        }
        res_wf = await client.post("/api/v1/workflows/definitions", json=def_payload, headers=headers)
        assert res_wf.status_code == 201

        # 2. Create Party with credit_limit = 200 (violates guard)
        party_res = await client.post(
            "/api/v1/parties/",
            json={"name": "Low Credit Client", "is_customer": True, "credit_limit": 200.0},
            headers=headers,
        )
        assert party_res.status_code == 201
        party_id = party_res.json()["id"]

        # 3. Available transitions query: should NOT include approve_credit because guard is not satisfied
        res_avail = await client.get(f"/api/v1/workflows/party/{party_id}/transitions", headers=headers)
        assert res_avail.status_code == 200
        avail_triggers = [t["trigger_name"] for t in res_avail.json()]
        assert "approve_credit" not in avail_triggers

        # 4. Attempt to execute approve_credit: should fail with 400 guard failure
        res_exec = await client.post(
            f"/api/v1/workflows/party/{party_id}/execute",
            json={"trigger_name": "approve_credit"},
            headers=headers,
        )
        assert res_exec.status_code == 400
        assert res_exec.json()["error"]["code"] == "WORKFLOW_TRANSITION_ERROR"

        # 5. Update Party credit_limit = 5000 (satisfies guard)
        patch_res = await client.patch(f"/api/v1/parties/{party_id}", json={"credit_limit": 5000.0}, headers=headers)
        assert patch_res.status_code == 200

        # 6. Available transitions query: now includes approve_credit
        res_avail2 = await client.get(f"/api/v1/workflows/party/{party_id}/transitions", headers=headers)
        assert res_avail2.status_code == 200
        avail_triggers2 = [t["trigger_name"] for t in res_avail2.json()]
        assert "approve_credit" in avail_triggers2

        # 7. Execute approve_credit: succeeds!
        res_exec2 = await client.post(
            f"/api/v1/workflows/party/{party_id}/execute",
            json={"trigger_name": "approve_credit"},
            headers=headers,
        )
        assert res_exec2.status_code == 200
        res_json = res_exec2.json()
        assert res_json["from_state"] == "draft"
        assert res_json["to_state"] == "approved"


@pytest.mark.asyncio
async def test_record_freeze_interceptor_immutability_and_unfreeze(db_session: AsyncSession):
    """Verify physical database-level record lock preventing UPDATE/DELETE on frozen entities."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Freeze Test Co", code=f"FZ_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"fz_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Freeze Tester", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 1. Create Workflow Definition where destination state 'posted' is_frozen = True
        def_payload = {
            "name": "Immutable Partner Post Workflow",
            "code": "wf_freeze_partner",
            "res_model": "party",
            "state_field": "state",
            "initial_state": "draft",
            "states": [
                {"code": "draft", "label": "Draft", "is_frozen": False, "sequence": 10},
                {"code": "posted", "label": "Posted & Locked", "is_frozen": True, "sequence": 20},
            ],
            "is_active": True,
            "transitions": [
                {
                    "trigger_name": "post",
                    "from_state": "draft",
                    "to_state": "posted",
                    "freeze_record": True,
                    "sequence": 10,
                }
            ],
        }
        await client.post("/api/v1/workflows/definitions", json=def_payload, headers=headers)

        # 2. Create Party in draft state
        party_res = await client.post(
            "/api/v1/parties/",
            json={"name": "Mutable Partner Inc", "is_vendor": True},
            headers=headers,
        )
        party_id = party_res.json()["id"]

        # Modification in draft state: succeeds
        edit_draft = await client.patch(f"/api/v1/parties/{party_id}", json={"name": "Mutable Partner LLC"}, headers=headers)
        assert edit_draft.status_code == 200

        # 3. Transition to 'posted' (freezing the record)
        post_res = await client.post(
            f"/api/v1/workflows/party/{party_id}/execute",
            json={"trigger_name": "post"},
            headers=headers,
        )
        assert post_res.status_code == 200
        assert post_res.json()["is_frozen"] is True

        # 4. Attempt to modify frozen record: must be rejected with 422 RECORD_FROZEN by interceptor!
        illegal_update = await client.patch(
            f"/api/v1/parties/{party_id}",
            json={"name": "Hacked Immutable Partner"},
            headers=headers,
        )
        assert illegal_update.status_code == 422
        assert illegal_update.json()["error"]["code"] == "RECORD_FROZEN"

        # 5. Attempt to delete frozen record: must be rejected with 422 RECORD_FROZEN!
        illegal_delete = await client.delete(f"/api/v1/parties/{party_id}", headers=headers)
        assert illegal_delete.status_code == 422
        assert illegal_delete.json()["error"]["code"] == "RECORD_FROZEN"

        # Rollback test session to clear rejected mutations from identity map
        await db_session.rollback()

        # 6. Make user superuser to authorize administrative unfreeze
        from modules.base.identity_rbac.models import User
        from sqlalchemy import select
        u = (await db_session.execute(select(User).where(User.username == username))).scalar_one()
        u.is_superuser = True
        await db_session.commit()

        # Execute administrative unfreeze
        unfreeze_res = await client.post(
            f"/api/v1/workflows/party/{party_id}/unfreeze?reason=Audit+correction",
            headers=headers,
        )
        assert unfreeze_res.status_code == 200

        # 7. Modify record after unfreeze: succeeds!
        valid_update = await client.patch(
            f"/api/v1/parties/{party_id}",
            json={"name": "Corrected Partner LLC"},
            headers=headers,
        )
        assert valid_update.status_code == 200
        assert valid_update.json()["name"] == "Corrected Partner LLC"


@pytest.mark.asyncio
async def test_workflow_execution_history_audit(db_session: AsyncSession):
    """Verify chronological audit history logging for all executed transitions."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="History Test Co", code=f"HS_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"hs_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "History Auditor", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 1. Create Workflow Definition
        await client.post(
            "/api/v1/workflows/definitions",
            json={
                "name": "Audit Trail Workflow",
                "code": "wf_audit_history",
                "res_model": "party",
                "initial_state": "draft",
                "states": [
                    {"code": "draft", "label": "Draft", "is_frozen": False},
                    {"code": "step1", "label": "Step 1", "is_frozen": False},
                    {"code": "step2", "label": "Step 2", "is_frozen": False},
                ],
                "transitions": [
                    {"trigger_name": "go_step1", "from_state": "draft", "to_state": "step1"},
                    {"trigger_name": "go_step2", "from_state": "step1", "to_state": "step2"},
                ],
            },
            headers=headers,
        )

        # 2. Create Party
        party_res = await client.post("/api/v1/parties/", json={"name": "History Audit Partner"}, headers=headers)
        party_id = party_res.json()["id"]

        # 3. Execute Step 1
        await client.post(
            f"/api/v1/workflows/party/{party_id}/execute",
            json={"trigger_name": "go_step1", "metadata": {"note": "First movement"}},
            headers=headers,
        )

        # 4. Execute Step 2
        await client.post(
            f"/api/v1/workflows/party/{party_id}/execute",
            json={"trigger_name": "go_step2", "metadata": {"note": "Second movement"}},
            headers=headers,
        )

        # 5. Query workflow history
        hist_res = await client.get(f"/api/v1/workflows/party/{party_id}/history", headers=headers)
        assert hist_res.status_code == 200
        logs = hist_res.json()
        assert len(logs) == 2
        # Chronological desc (latest first)
        assert logs[0]["trigger_name"] == "go_step2"
        assert logs[0]["from_state"] == "step1"
        assert logs[0]["to_state"] == "step2"
        assert logs[1]["trigger_name"] == "go_step1"
        assert logs[1]["from_state"] == "draft"
        assert logs[1]["to_state"] == "step1"
