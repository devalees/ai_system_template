"""Automated test suite for Identity, Tenant Company Gating & Contextual RBAC module."""

import uuid
import pytest
import pyotp
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from core.app import create_app
from core.database import get_db
from modules.base.identity_rbac.models import (
    Company,
    User,
    Group,
    Permission,
    UserGroupLink,
    GroupPermissionLink,
)
from modules.base.mail_gateway.models import MailQueue
from modules.base.identity_rbac.security import (
    hash_password,
    create_password_reset_token,
    create_email_verification_token,
)
from modules.base.identity_rbac.dependencies import require_permission
from modules.base.identity_rbac.harvester import harvest_model_permissions

from main import app

# Test route protected by granular permission
@app.get("/test/protected-capability")
async def protected_endpoint(current_user: User = Depends(require_permission("orders.invoice.approve"))):
    return {"status": "approved", "approver": current_user.username}


@pytest.mark.asyncio
async def test_user_registration_allowed_when_company_permits(db_session: AsyncSession):
    """Verify registration succeeds when target company has allow_registration=True."""
    # 1. Seed company with allow_registration=True
    open_company = Company(
        name="Open Registration Corp",
        code=f"OPEN_{uuid.uuid4().hex[:4]}",
        allow_registration=True,
    )
    db_session.add(open_company)
    await db_session.commit()
    await db_session.refresh(open_company)

    unique_user = f"user_{uuid.uuid4().hex[:6]}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register User with open company
        reg_payload = {
            "email": f"{unique_user}@example.com",
            "username": unique_user,
            "password": "SecurePassword2026!",
            "full_name": "Open User",
            "user_type": "human",
            "company_id": str(open_company.id),
        }
        res_reg = await client.post("/api/v1/identity_rbac/auth/register", json=reg_payload)
        assert res_reg.status_code == 201
        reg_data = res_reg.json()
        assert reg_data["username"] == unique_user
        assert reg_data["company_id"] == str(open_company.id)

        # Login with valid credentials
        login_payload = {
            "identifier": unique_user,
            "password": "SecurePassword2026!",
        }
        res_login = await client.post("/api/v1/identity_rbac/auth/login", json=login_payload)
        assert res_login.status_code == 200
        token_data = res_login.json()
        assert "access_token" in token_data
        token = token_data["access_token"]

        # Access /auth/me
        res_me = await client.get(
            "/api/v1/identity_rbac/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_me.status_code == 200
        assert res_me.json()["username"] == unique_user


@pytest.mark.asyncio
async def test_user_registration_blocked_when_company_disallows(db_session: AsyncSession):
    """Verify registration is rejected with 403 Forbidden when target company has allow_registration=False."""
    # Seed closed company
    closed_company = Company(
        name="Closed Enterprise Ltd",
        code=f"CLOSED_{uuid.uuid4().hex[:4]}",
        allow_registration=False,
    )
    db_session.add(closed_company)
    await db_session.commit()
    await db_session.refresh(closed_company)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        reg_payload = {
            "email": f"blocked_{uuid.uuid4().hex[:6]}@example.com",
            "username": f"blocked_{uuid.uuid4().hex[:6]}",
            "password": "SecurePassword2026!",
            "full_name": "Blocked Candidate",
            "user_type": "human",
            "company_id": str(closed_company.id),
        }
        res_reg = await client.post("/api/v1/identity_rbac/auth/register", json=reg_payload)
        assert res_reg.status_code == 403
        assert "disabled" in res_reg.json()["detail"].lower()


@pytest.mark.asyncio
async def test_user_registration_nonexistent_company(db_session: AsyncSession):
    """Verify registration fails with 404 Not Found when company_id does not exist."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        reg_payload = {
            "email": f"ghost_{uuid.uuid4().hex[:6]}@example.com",
            "username": f"ghost_{uuid.uuid4().hex[:6]}",
            "password": "SecurePassword2026!",
            "full_name": "Ghost User",
            "user_type": "human",
            "company_id": str(uuid.uuid4()),
        }
        res_reg = await client.post("/api/v1/identity_rbac/auth/register", json=reg_payload)
        assert res_reg.status_code == 404
        assert "not found" in res_reg.json()["detail"].lower()


@pytest.mark.asyncio
async def test_internal_user_creation_bypasses_registration_flag(db_session: AsyncSession):
    """Verify admin can provision users via POST /users even when company has allow_registration=False."""
    company_id = uuid.uuid4()
    company = Company(
        id=company_id,
        name="Strict Enterprise Corp",
        code=f"STRICT_{uuid.uuid4().hex[:4]}",
        allow_registration=False,
    )
    admin_user = User(
        email=f"admin_{uuid.uuid4().hex[:6]}@strict.com",
        username=f"admin_{uuid.uuid4().hex[:6]}",
        hashed_password=hash_password("AdminPass123!"),
        full_name="Strict Company Admin",
        is_superuser=True,
        company_id=company.id,
    )
    db_session.add_all([company, admin_user])
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Login admin
        res_login = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": admin_user.username, "password": "AdminPass123!"},
        )
        token = res_login.json()["access_token"]

        # Provision internal user
        emp_user = f"emp_{uuid.uuid4().hex[:6]}"
        internal_payload = {
            "email": f"{emp_user}@strict.com",
            "username": emp_user,
            "password": "EmpPassword2026!",
            "full_name": "Internal Employee",
            "user_type": "human",
            "company_id": str(company.id),
        }
        res_user = await client.post(
            "/api/v1/identity_rbac/users",
            json=internal_payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_user.status_code == 201
        data = res_user.json()
        assert data["username"] == emp_user
        assert data["company_id"] == str(company.id)


@pytest.mark.asyncio
async def test_company_management_endpoints(db_session: AsyncSession):
    """Verify superuser can create, list, and patch company allow_registration status."""
    super_admin = User(
        email=f"root_{uuid.uuid4().hex[:6]}@platform.local",
        username=f"root_{uuid.uuid4().hex[:6]}",
        hashed_password=hash_password("RootPass123!"),
        full_name="Platform Root Admin",
        is_superuser=True,
        company_id=uuid.uuid4(),
    )
    db_session.add(super_admin)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_login = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": super_admin.username, "password": "RootPass123!"},
        )
        token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create company with allow_registration=False
        comp_code = f"TENANT_{uuid.uuid4().hex[:4]}"
        create_res = await client.post(
            "/api/v1/identity_rbac/companies",
            json={"name": "New Tenant Ltd", "code": comp_code, "allow_registration": False},
            headers=headers,
        )
        assert create_res.status_code == 201
        comp_data = create_res.json()
        comp_id = comp_data["id"]
        assert comp_data["allow_registration"] is False

        # 2. Patch company to allow registration
        patch_res = await client.patch(
            f"/api/v1/identity_rbac/companies/{comp_id}",
            json={"allow_registration": True},
            headers=headers,
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["allow_registration"] is True

        # 3. Retrieve company details
        get_res = await client.get(f"/api/v1/identity_rbac/companies/{comp_id}", headers=headers)
        assert get_res.status_code == 200
        assert get_res.json()["name"] == "New Tenant Ltd"


@pytest.mark.asyncio
async def test_first_class_ai_agent_identity(db_session: AsyncSession):
    """Verify first-class AI Agent registration and symmetric auth on open company."""
    company = Company(
        name="AI Hub Corp",
        code=f"AI_{uuid.uuid4().hex[:4]}",
        allow_registration=True,
    )
    db_session.add(company)
    await db_session.commit()

    agent_id = f"bot_agent_{uuid.uuid4().hex[:6]}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "email": f"{agent_id}@hermes.internal",
            "username": agent_id,
            "password": "AgentSecretToken2026!",
            "full_name": "Autonomous QA Auditor",
            "user_type": "ai_agent",
            "company_id": str(company.id),
        }
        res = await client.post("/api/v1/identity_rbac/auth/register", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["user_type"] == "ai_agent"

        # Login agent
        res_login = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": agent_id, "password": "AgentSecretToken2026!"},
        )
        assert res_login.status_code == 200
        assert res_login.json()["user"]["user_type"] == "ai_agent"


@pytest.mark.asyncio
async def test_rbac_permission_gating_and_superusers(db_session: AsyncSession):
    """Verify require_permission blocks unauthorized users and admits permitted actors."""
    company_id = uuid.uuid4()

    # 1. Create a regular user with NO permissions
    reg_user = User(
        email=f"regular_{uuid.uuid4().hex[:6]}@test.com",
        username=f"reg_{uuid.uuid4().hex[:6]}",
        hashed_password=hash_password("Pass123!"),
        full_name="Regular User",
        is_superuser=False,
        company_id=company_id,
    )
    # 2. Create a superuser
    admin_user = User(
        email=f"admin_{uuid.uuid4().hex[:6]}@test.com",
        username=f"admin_{uuid.uuid4().hex[:6]}",
        hashed_password=hash_password("Pass123!"),
        full_name="Super Admin",
        is_superuser=True,
        company_id=company_id,
    )
    db_session.add_all([reg_user, admin_user])
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Login regular user
        res_reg = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": reg_user.username, "password": "Pass123!"},
        )
        reg_token = res_reg.json()["access_token"]

        # Regular user accessing protected endpoint should be FORBIDDEN
        res_denied = await client.get(
            "/test/protected-capability",
            headers={"Authorization": f"Bearer {reg_token}"},
        )
        assert res_denied.status_code == 403
        assert res_denied.json()["error"]["code"] == "PERMISSION_DENIED"

        # Login admin user
        res_adm = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": admin_user.username, "password": "Pass123!"},
        )
        adm_token = res_adm.json()["access_token"]

        # Superuser accessing protected endpoint should PASS
        res_allowed = await client.get(
            "/test/protected-capability",
            headers={"Authorization": f"Bearer {adm_token}"},
        )
        assert res_allowed.status_code == 200
        assert res_allowed.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_permission_canonical_code_and_patch(db_session: AsyncSession):
    """Verify permission canonical code derivation and PATCH update capabilities."""
    comp_id = uuid.uuid4()
    company = Company(
        id=comp_id,
        name="Perm Corp",
        code=f"PERM_{uuid.uuid4().hex[:4]}",
        allow_registration=True,
    )
    super_admin = User(
        email=f"perm_admin_{uuid.uuid4().hex[:6]}@test.com",
        username=f"perm_admin_{uuid.uuid4().hex[:6]}",
        hashed_password=hash_password("Pass123!"),
        full_name="Permission Admin",
        is_superuser=True,
        company_id=comp_id,
    )
    db_session.add_all([company, super_admin])
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_login = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": super_admin.username, "password": "Pass123!"},
        )
        token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create permission without explicit code (canonical generation)
        res_suffix = uuid.uuid4().hex[:4]
        perm_payload = {
            "name": "Read Accounting Invoices",
            "module_name": "accounting",
            "resource": f"invoice_{res_suffix}",
            "action": "read",
            "ownership_scope": "GLOBAL",
        }
        res_create = await client.post(
            "/api/v1/identity_rbac/permissions",
            json=perm_payload,
            headers=headers,
        )
        assert res_create.status_code == 201
        perm_data = res_create.json()
        assert perm_data["code"] == f"accounting.invoice_{res_suffix}.read"
        assert perm_data["resource"] == f"invoice_{res_suffix}"
        assert perm_data["action"] == "read"
        assert perm_data["ownership_scope"] == "GLOBAL"
        perm_id = perm_data["id"]

        # 2. Patch permission ownership scope
        res_patch = await client.patch(
            f"/api/v1/identity_rbac/permissions/{perm_id}",
            json={"ownership_scope": "OWN", "name": "Own Invoices Read"},
            headers=headers,
        )
        assert res_patch.status_code == 200
        patched_data = res_patch.json()
        assert patched_data["ownership_scope"] == "OWN"
        assert patched_data["name"] == "Own Invoices Read"

        # 3. Retrieve permission detail
        res_get = await client.get(
            f"/api/v1/identity_rbac/permissions/{perm_id}",
            headers=headers,
        )
        assert res_get.status_code == 200
        assert res_get.json()["ownership_scope"] == "OWN"
        assert res_get.json()["name"] == "Own Invoices Read"


@pytest.mark.asyncio
async def test_group_crud_and_permission_linking(db_session: AsyncSession):
    """Verify group creation with permission assignment, patch resync, and detail inspection."""
    comp_id = uuid.uuid4()
    company = Company(
        id=comp_id,
        name="Group Corp",
        code=f"GRP_{uuid.uuid4().hex[:4]}",
        allow_registration=True,
    )
    super_admin = User(
        email=f"group_admin_{uuid.uuid4().hex[:6]}@test.com",
        username=f"group_admin_{uuid.uuid4().hex[:6]}",
        hashed_password=hash_password("Pass123!"),
        full_name="Group Admin",
        is_superuser=True,
        company_id=comp_id,
    )
    db_session.add_all([company, super_admin])
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_login = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": super_admin.username, "password": "Pass123!"},
        )
        token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Seed two permissions with unique resource
        res_suffix = uuid.uuid4().hex[:4]
        p1 = await client.post(
            "/api/v1/identity_rbac/permissions",
            json={
                "name": "Audit Read",
                "module_name": "audit",
                "resource": f"log_{res_suffix}",
                "action": "read",
            },
            headers=headers,
        )
        p2 = await client.post(
            "/api/v1/identity_rbac/permissions",
            json={
                "name": "Audit Export",
                "module_name": "audit",
                "resource": f"log_{res_suffix}",
                "action": "export",
            },
            headers=headers,
        )
        p1_id = p1.json()["id"]
        p2_id = p2.json()["id"]

        # 1. Create group with both permissions
        group_payload = {
            "name": f"Auditors_{uuid.uuid4().hex[:4]}",
            "description": "Internal audit group",
            "permission_ids": [p1_id, p2_id],
        }
        res_grp = await client.post(
            "/api/v1/identity_rbac/groups",
            json=group_payload,
            headers=headers,
        )
        assert res_grp.status_code == 201
        grp_data = res_grp.json()
        assert grp_data["permissions_count"] == 2
        grp_id = grp_data["id"]

        # 2. Patch group: remove p2, keep only p1
        res_patch_grp = await client.patch(
            f"/api/v1/identity_rbac/groups/{grp_id}",
            json={"description": "Restricted audit group", "permission_ids": [p1_id]},
            headers=headers,
        )
        assert res_patch_grp.status_code == 200
        patched_grp = res_patch_grp.json()
        assert patched_grp["description"] == "Restricted audit group"
        assert len(patched_grp["permissions"]) == 1
        assert patched_grp["permissions"][0]["id"] == p1_id

        # 3. Get group detail
        res_get_grp = await client.get(
            f"/api/v1/identity_rbac/groups/{grp_id}",
            headers=headers,
        )
        assert res_get_grp.status_code == 200
        assert len(res_get_grp.json()["permissions"]) == 1


@pytest.mark.asyncio
async def test_user_patch_and_group_linking(db_session: AsyncSession):
    """Verify user update patch updates user profile and manages group memberships."""
    comp_id = uuid.uuid4()
    company = Company(
        id=comp_id,
        name="Update Tenant",
        code=f"UPD_{uuid.uuid4().hex[:4]}",
        allow_registration=True,
    )
    super_admin = User(
        email=f"user_admin_{uuid.uuid4().hex[:6]}@test.com",
        username=f"user_admin_{uuid.uuid4().hex[:6]}",
        hashed_password=hash_password("Pass123!"),
        full_name="User Admin",
        is_superuser=True,
        company_id=comp_id,
    )
    db_session.add_all([company, super_admin])
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_login = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": super_admin.username, "password": "Pass123!"},
        )
        token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create target group
        res_g = await client.post(
            "/api/v1/identity_rbac/groups",
            json={"name": f"Support_{uuid.uuid4().hex[:4]}", "description": "Support Team"},
            headers=headers,
        )
        group_id = res_g.json()["id"]

        # Create target user
        target_username = f"agent_bob_{uuid.uuid4().hex[:4]}"
        res_u = await client.post(
            "/api/v1/identity_rbac/users",
            json={
                "email": f"{target_username}@test.com",
                "username": target_username,
                "password": "InitialPass123!",
                "full_name": "Bob Original",
                "company_id": str(company.id),
            },
            headers=headers,
        )
        assert res_u.status_code == 201
        user_id = res_u.json()["id"]

        # Patch user: full_name, preferred_language, group_ids
        res_patch_u = await client.patch(
            f"/api/v1/identity_rbac/users/{user_id}",
            json={
                "full_name": "Bob Senior Specialist",
                "preferred_language": "ar",
                "group_ids": [group_id],
            },
            headers=headers,
        )
        assert res_patch_u.status_code == 200
        patched_user = res_patch_u.json()
        assert patched_user["full_name"] == "Bob Senior Specialist"
        assert patched_user["preferred_language"] == "ar"
        assert len(patched_user["groups"]) == 1
        assert patched_user["groups"][0]["id"] == group_id

        # Verify via GET /users/{id}
        res_detail = await client.get(
            f"/api/v1/identity_rbac/users/{user_id}",
            headers=headers,
        )
        assert res_detail.status_code == 200
        detail_data = res_detail.json()
        assert detail_data["full_name"] == "Bob Senior Specialist"
        assert len(detail_data["groups"]) == 1


@pytest.mark.asyncio
async def test_soft_delete_and_guards(db_session: AsyncSession):
    """Verify soft-delete for Company, User, Group, Permission, and self-delete safety guard."""
    comp_id = uuid.uuid4()
    company = Company(
        id=comp_id,
        name="Deletable Corp",
        code=f"DEL_{uuid.uuid4().hex[:4]}",
        allow_registration=True,
    )
    admin_user = User(
        email=f"del_admin_{uuid.uuid4().hex[:6]}@del.com",
        username=f"del_admin_{uuid.uuid4().hex[:6]}",
        hashed_password=hash_password("Pass123!"),
        full_name="Delete Admin",
        is_superuser=True,
        company_id=comp_id,
    )
    db_session.add_all([company, admin_user])
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_login = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": admin_user.username, "password": "Pass123!"},
        )
        token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Guard check: Admin cannot delete their own active user
        res_self_del = await client.delete(
            f"/api/v1/identity_rbac/users/{admin_user.id}",
            headers=headers,
        )
        assert res_self_del.status_code == 400
        assert "own active session" in res_self_del.json()["detail"].lower()

        # 2. Create another user and soft-delete them
        target_name = f"victim_{uuid.uuid4().hex[:4]}"
        res_target = await client.post(
            "/api/v1/identity_rbac/users",
            json={
                "email": f"{target_name}@del.com",
                "username": target_name,
                "password": "VictimPass123!",
                "full_name": "Victim User",
                "company_id": str(company.id),
            },
            headers=headers,
        )
        assert res_target.status_code == 201
        target_user_id = res_target.json()["id"]

        del_u_res = await client.delete(
            f"/api/v1/identity_rbac/users/{target_user_id}",
            headers=headers,
        )
        assert del_u_res.status_code == 200
        assert del_u_res.json()["status"] == "deleted"

        # Verify soft-deleted user is not found in detail endpoint
        get_u_res = await client.get(
            f"/api/v1/identity_rbac/users/{target_user_id}",
            headers=headers,
        )
        assert get_u_res.status_code == 404

        # 3. Soft-delete Group
        res_grp = await client.post(
            "/api/v1/identity_rbac/groups",
            json={"name": f"DelGroup_{uuid.uuid4().hex[:4]}"},
            headers=headers,
        )
        grp_id = res_grp.json()["id"]

        del_g_res = await client.delete(
            f"/api/v1/identity_rbac/groups/{grp_id}",
            headers=headers,
        )
        assert del_g_res.status_code == 200
        assert del_g_res.json()["status"] == "deleted"

        get_g_res = await client.get(
            f"/api/v1/identity_rbac/groups/{grp_id}",
            headers=headers,
        )
        assert get_g_res.status_code == 404

        # 4. Soft-delete Permission
        perm_res_suffix = uuid.uuid4().hex[:4]
        res_p = await client.post(
            "/api/v1/identity_rbac/permissions",
            json={
                "name": "Del Perm",
                "module_name": "temp",
                "resource": f"item_{perm_res_suffix}",
                "action": "delete",
            },
            headers=headers,
        )
        p_id = res_p.json()["id"]

        del_p_res = await client.delete(
            f"/api/v1/identity_rbac/permissions/{p_id}",
            headers=headers,
        )
        assert del_p_res.status_code == 200
        assert del_p_res.json()["status"] == "deleted"

        get_p_res = await client.get(
            f"/api/v1/identity_rbac/permissions/{p_id}",
            headers=headers,
        )
        assert get_p_res.status_code == 404

        # 5. Soft-delete Company
        res_c = await client.post(
            "/api/v1/identity_rbac/companies",
            json={"name": "Temp Corp", "code": f"TC_{uuid.uuid4().hex[:4]}"},
            headers=headers,
        )
        c_id = res_c.json()["id"]

        del_c_res = await client.delete(
            f"/api/v1/identity_rbac/companies/{c_id}",
            headers=headers,
        )
        assert del_c_res.status_code == 200
        assert del_c_res.json()["status"] == "deleted"

        get_c_res = await client.get(
            f"/api/v1/identity_rbac/companies/{c_id}",
            headers=headers,
        )
        assert get_c_res.status_code == 404


@pytest.mark.asyncio
async def test_automated_permission_harvester(db_session: AsyncSession):
    """Verify automated model-level permission harvester generates CRUD rows across all models idempotently."""
    comp_id = uuid.uuid4()
    company = Company(
        id=comp_id,
        name="Harvester Test Corp",
        code=f"HARV_{uuid.uuid4().hex[:4]}",
        allow_registration=False,
    )
    admin_group = Group(
        name="Super Administrators",
        description="Universal administration authority",
        company_id=comp_id,
    )
    db_session.add_all([company, admin_group])
    await db_session.commit()

    # 1. First run: Harvest permissions
    res1 = await harvest_model_permissions(db_session, company_id=comp_id, auto_link_super_admin_group=True)
    assert res1["models_inspected"] >= 20
    assert res1["total_active_permissions"] >= 80

    # 2. Verify specific canonical codes exist
    sample_codes = [
        "identity_rbac.user.create",
        "identity_rbac.user.read",
        "identity_rbac.user.update",
        "identity_rbac.user.delete",
        "lookups.country.read",
        "audit.audit_log.read",
        "documents.document_attachment.create",
    ]
    for sc in sample_codes:
        query_perm = (await db_session.execute(
            select(Permission).where(Permission.code == sc)
        )).scalar_one_or_none()
        assert query_perm is not None, f"Expected canonical permission '{sc}' was not harvested!"

    # 3. Idempotency check: second run should create 0 new permissions
    res2 = await harvest_model_permissions(db_session, company_id=comp_id, auto_link_super_admin_group=True)
    assert res2["new_permissions_created"] == 0


@pytest.mark.asyncio
async def test_bidirectional_group_user_management(db_session: AsyncSession):
    """Verify assigning users during group creation/update and via dedicated membership endpoints."""
    comp_id = uuid.uuid4()
    company = Company(
        id=comp_id,
        name="Membership Corp",
        code=f"MEM_{uuid.uuid4().hex[:4]}",
        allow_registration=True,
    )
    super_admin = User(
        email=f"mem_admin_{uuid.uuid4().hex[:6]}@mem.com",
        username=f"mem_admin_{uuid.uuid4().hex[:6]}",
        hashed_password=hash_password("Pass123!"),
        full_name="Membership Admin",
        is_superuser=True,
        company_id=comp_id,
    )
    target_user = User(
        email=f"member_bob_{uuid.uuid4().hex[:6]}@mem.com",
        username=f"member_bob_{uuid.uuid4().hex[:6]}",
        hashed_password=hash_password("Pass123!"),
        full_name="Bob Member",
        company_id=comp_id,
    )
    db_session.add_all([company, super_admin, target_user])
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_login = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": super_admin.username, "password": "Pass123!"},
        )
        token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create group with user_ids=[target_user.id]
        res_g = await client.post(
            "/api/v1/identity_rbac/groups",
            json={
                "name": f"Finance_{uuid.uuid4().hex[:4]}",
                "description": "Finance Department",
                "user_ids": [str(target_user.id)],
            },
            headers=headers,
        )
        assert res_g.status_code == 201
        group_data = res_g.json()
        assert group_data["users_count"] == 1
        group_id = group_data["id"]

        # 2. Get group detail and verify users list contains target_user
        res_get_g = await client.get(
            f"/api/v1/identity_rbac/groups/{group_id}",
            headers=headers,
        )
        assert res_get_g.status_code == 200
        detail = res_get_g.json()
        assert len(detail["users"]) == 1
        assert detail["users"][0]["id"] == str(target_user.id)
        assert detail["users"][0]["username"] == target_user.username

        # 3. List members via GET /groups/{id}/users
        res_list_u = await client.get(
            f"/api/v1/identity_rbac/groups/{group_id}/users",
            headers=headers,
        )
        assert res_list_u.status_code == 200
        members = res_list_u.json()
        assert len(members) == 1
        assert members[0]["id"] == str(target_user.id)

        # 4. Remove user via DELETE /groups/{id}/users/{user_id}
        res_del_u = await client.delete(
            f"/api/v1/identity_rbac/groups/{group_id}/users/{target_user.id}",
            headers=headers,
        )
        assert res_del_u.status_code == 200

        # Verify group now has 0 members
        res_list_empty = await client.get(
            f"/api/v1/identity_rbac/groups/{group_id}/users",
            headers=headers,
        )
        assert res_list_empty.status_code == 200
        assert len(res_list_empty.json()) == 0

        # 5. Add user back via POST /groups/{id}/users/{user_id}
        res_add_u = await client.post(
            f"/api/v1/identity_rbac/groups/{group_id}/users/{target_user.id}",
            headers=headers,
        )
        assert res_add_u.status_code == 200

        # Verify membership restored
        res_list_restored = await client.get(
            f"/api/v1/identity_rbac/groups/{group_id}/users",
            headers=headers,
        )
        assert res_list_restored.status_code == 200
        assert len(res_list_restored.json()) == 1


@pytest.mark.asyncio
async def test_primary_root_admin_immunity_and_hierarchy(db_session: AsyncSession):
    """Verify primary root admin immunity, undeletability, and superuser governance hierarchy."""
    comp_id = uuid.uuid4()
    company = Company(
        id=comp_id,
        name="Hierarchy Enterprise",
        code=f"HIER_{uuid.uuid4().hex[:4]}",
        allow_registration=True,
    )
    # 1. Primary Root Admin (seeded by setup_database)
    root_admin = User(
        email=f"root_{uuid.uuid4().hex[:6]}@hier.com",
        username=f"root_{uuid.uuid4().hex[:6]}",
        hashed_password=hash_password("RootPass2026!"),
        full_name="Root Primary Admin",
        is_superuser=True,
        is_primary_admin=True,
        company_id=comp_id,
    )
    db_session.add_all([company, root_admin])
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Login as Root Primary Admin
        res_root_login = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": root_admin.username, "password": "RootPass2026!"},
        )
        assert res_root_login.status_code == 200
        root_token = res_root_login.json()["access_token"]
        assert res_root_login.json()["user"]["is_primary_admin"] is True
        assert res_root_login.json()["user"]["is_superuser"] is True
        root_headers = {"Authorization": f"Bearer {root_token}"}

        # 2. Root Admin provisions a Secondary Superuser
        sec_su_name = f"sec_su_{uuid.uuid4().hex[:4]}"
        res_sec_su = await client.post(
            "/api/v1/identity_rbac/users",
            json={
                "email": f"{sec_su_name}@hier.com",
                "username": sec_su_name,
                "password": "SecPass2026!",
                "full_name": "Secondary Superuser",
                "is_superuser": True,
                "company_id": str(company.id),
            },
            headers=root_headers,
        )
        assert res_sec_su.status_code == 201
        sec_su_id = res_sec_su.json()["id"]

        # Login as Secondary Superuser
        res_sec_login = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": sec_su_name, "password": "SecPass2026!"},
        )
        assert res_sec_login.status_code == 200
        sec_token = res_sec_login.json()["access_token"]
        assert res_sec_login.json()["user"]["is_primary_admin"] is False
        assert res_sec_login.json()["user"]["is_superuser"] is True
        sec_headers = {"Authorization": f"Bearer {sec_token}"}

        # 3. Secondary Superuser CANNOT provision another superuser (403)
        res_deny_su = await client.post(
            "/api/v1/identity_rbac/users",
            json={
                "email": f"deny_{uuid.uuid4().hex[:4]}@hier.com",
                "username": f"deny_{uuid.uuid4().hex[:4]}",
                "password": "DenyPass2026!",
                "full_name": "Denied Superuser",
                "is_superuser": True,
                "company_id": str(company.id),
            },
            headers=sec_headers,
        )
        assert res_deny_su.status_code == 403
        assert "only the primary system administrator" in res_deny_su.json()["detail"].lower()

        # But secondary superuser CAN provision normal user (201)
        res_norm = await client.post(
            "/api/v1/identity_rbac/users",
            json={
                "email": f"norm_{uuid.uuid4().hex[:4]}@hier.com",
                "username": f"norm_{uuid.uuid4().hex[:4]}",
                "password": "NormPass2026!",
                "full_name": "Normal User",
                "is_superuser": False,
                "company_id": str(company.id),
            },
            headers=sec_headers,
        )
        assert res_norm.status_code == 201
        norm_user_id = res_norm.json()["id"]

        # 4. Secondary Superuser CANNOT delete Root Primary Admin (403)
        res_del_root = await client.delete(
            f"/api/v1/identity_rbac/users/{root_admin.id}",
            headers=sec_headers,
        )
        assert res_del_root.status_code == 403
        assert "permanent and cannot be deleted" in res_del_root.json()["detail"].lower()

        # 5. Secondary Superuser CANNOT modify Root Primary Admin (403)
        res_patch_root = await client.patch(
            f"/api/v1/identity_rbac/users/{root_admin.id}",
            json={"full_name": "Compromised Admin", "is_active": False},
            headers=sec_headers,
        )
        assert res_patch_root.status_code == 403
        assert "cannot be modified by other users" in res_patch_root.json()["detail"].lower()

        # 6. Root Primary Admin CANNOT demote or deactivate own account (400)
        res_self_demote = await client.patch(
            f"/api/v1/identity_rbac/users/{root_admin.id}",
            json={"is_superuser": False},
            headers=root_headers,
        )
        assert res_self_demote.status_code == 400
        assert "cannot revoke their own superuser status" in res_self_demote.json()["detail"].lower()

        res_self_deact = await client.patch(
            f"/api/v1/identity_rbac/users/{root_admin.id}",
            json={"is_active": False},
            headers=root_headers,
        )
        assert res_self_deact.status_code == 400
        assert "cannot deactivate their own root account" in res_self_deact.json()["detail"].lower()

        # 7. Root Primary Admin CANNOT delete self (400)
        res_self_del = await client.delete(
            f"/api/v1/identity_rbac/users/{root_admin.id}",
            headers=root_headers,
        )
        assert res_self_del.status_code == 400
        assert "cannot delete your own active session account" in res_self_del.json()["detail"].lower()

        # 8. Create another secondary superuser via Root Admin
        sec_su2_name = f"sec_su2_{uuid.uuid4().hex[:4]}"
        res_sec_su2 = await client.post(
            "/api/v1/identity_rbac/users",
            json={
                "email": f"{sec_su2_name}@hier.com",
                "username": sec_su2_name,
                "password": "SecPass2026!",
                "full_name": "Secondary Superuser 2",
                "is_superuser": True,
                "company_id": str(company.id),
            },
            headers=root_headers,
        )
        assert res_sec_su2.status_code == 201
        sec_su2_id = res_sec_su2.json()["id"]

        # 9. Secondary Superuser 1 CANNOT modify or delete Secondary Superuser 2 (403)
        res_peer_mod = await client.patch(
            f"/api/v1/identity_rbac/users/{sec_su2_id}",
            json={"full_name": "Peer Modified"},
            headers=sec_headers,
        )
        assert res_peer_mod.status_code == 403
        assert "only the primary system administrator can modify another superuser" in res_peer_mod.json()["detail"].lower()

        res_peer_del = await client.delete(
            f"/api/v1/identity_rbac/users/{sec_su2_id}",
            headers=sec_headers,
        )
        assert res_peer_del.status_code == 403
        assert "only the primary system administrator can delete a superuser" in res_peer_del.json()["detail"].lower()

        # 10. Root Primary Admin CAN modify and delete Secondary Superusers
        res_root_mod_su = await client.patch(
            f"/api/v1/identity_rbac/users/{sec_su2_id}",
            json={"full_name": "Demoted by Root", "is_superuser": False},
            headers=root_headers,
        )
        assert res_root_mod_su.status_code == 200
        assert res_root_mod_su.json()["is_superuser"] is False

        res_root_del_su = await client.delete(
            f"/api/v1/identity_rbac/users/{sec_su_id}",
            headers=root_headers,
        )
        assert res_root_del_su.status_code == 200
        assert res_root_del_su.json()["status"] == "deleted"


@pytest.mark.asyncio
async def test_authenticated_change_password_and_decoupling(db_session: AsyncSession):
    """Verify password cannot be updated via PATCH /users/{id} and can only be updated via POST /auth/change-password."""
    comp_id = uuid.uuid4()
    company = Company(
        id=comp_id,
        name="Security Audit Corp",
        code=f"SEC_{uuid.uuid4().hex[:4]}",
        allow_registration=True,
    )
    user = User(
        email=f"employee_{uuid.uuid4().hex[:6]}@test.com",
        username=f"emp_{uuid.uuid4().hex[:6]}",
        hashed_password=hash_password("OriginalSecret2026!"),
        full_name="Employee One",
        is_superuser=False,
        company_id=comp_id,
    )
    db_session.add_all([company, user])
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Login with original password
        res_login = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user.username, "password": "OriginalSecret2026!"},
        )
        assert res_login.status_code == 200
        token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Attempting to change password via PATCH /users/{id} does NOT change password
        res_patch = await client.patch(
            f"/api/v1/identity_rbac/users/{user.id}",
            json={"full_name": "Employee One Renamed", "password": "IgnoredPassword2026!"},
            headers=headers,
        )
        assert res_patch.status_code == 200
        assert res_patch.json()["full_name"] == "Employee One Renamed"

        # Verify old password still works and patched password does NOT work
        res_check_old = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user.username, "password": "OriginalSecret2026!"},
        )
        assert res_check_old.status_code == 200

        res_check_fake = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user.username, "password": "IgnoredPassword2026!"},
        )
        assert res_check_fake.status_code == 401

        # 3. Validation: change password with wrong current_password (400)
        res_bad_curr = await client.post(
            "/api/v1/identity_rbac/auth/change-password",
            json={
                "current_password": "WrongPassword123!",
                "new_password": "NewSecretPass2026!",
                "confirm_password": "NewSecretPass2026!",
            },
            headers=headers,
        )
        assert res_bad_curr.status_code == 400
        assert "current password verification failed" in res_bad_curr.json()["detail"].lower()

        # 4. Validation: new_password != confirm_password (400)
        res_mismatch = await client.post(
            "/api/v1/identity_rbac/auth/change-password",
            json={
                "current_password": "OriginalSecret2026!",
                "new_password": "NewSecretPass2026!",
                "confirm_password": "DifferentPass2026!",
            },
            headers=headers,
        )
        assert res_mismatch.status_code == 400
        assert "do not match" in res_mismatch.json()["detail"].lower()

        # 5. Validation: new_password == current_password (400)
        res_identical = await client.post(
            "/api/v1/identity_rbac/auth/change-password",
            json={
                "current_password": "OriginalSecret2026!",
                "new_password": "OriginalSecret2026!",
                "confirm_password": "OriginalSecret2026!",
            },
            headers=headers,
        )
        assert res_identical.status_code == 400
        assert "cannot be identical" in res_identical.json()["detail"].lower()

        # 6. Valid password change (200)
        res_success = await client.post(
            "/api/v1/identity_rbac/auth/change-password",
            json={
                "current_password": "OriginalSecret2026!",
                "new_password": "BrandNewSecret2026!",
                "confirm_password": "BrandNewSecret2026!",
            },
            headers=headers,
        )
        assert res_success.status_code == 200
        assert res_success.json()["success"] is True

        # 7. Verify login: old password now fails, new password succeeds
        res_login_old = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user.username, "password": "OriginalSecret2026!"},
        )
        assert res_login_old.status_code == 401

        res_login_new = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user.username, "password": "BrandNewSecret2026!"},
        )
        assert res_login_new.status_code == 200
        assert "access_token" in res_login_new.json()


@pytest.mark.asyncio
async def test_forgot_and_reset_password_flow(db_session: AsyncSession):
    """Verify forgot-password token generation, Mail Gateway enqueue, single-use reset, and replay protection."""
    comp_id = uuid.uuid4()
    company = Company(
        id=comp_id,
        name="Reset Test Corp",
        code=f"RST_{uuid.uuid4().hex[:4]}",
        allow_registration=True,
    )
    user = User(
        email=f"alice_{uuid.uuid4().hex[:6]}@test.com",
        username=f"alice_{uuid.uuid4().hex[:6]}",
        hashed_password=hash_password("OldPassword123!"),
        full_name="Alice Specialist",
        is_superuser=False,
        email_verified=True,
        company_id=comp_id,
    )
    db_session.add_all([company, user])
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Non-existent email returns constant 200 OK (timing-attack safe)
        res_fake = await client.post(
            "/api/v1/identity_rbac/auth/forgot-password",
            json={"email": "nonexistent@fakecorp.com"},
        )
        assert res_fake.status_code == 200
        assert res_fake.json()["success"] is True

        # 2. Registered email requests password reset
        res_forgot = await client.post(
            "/api/v1/identity_rbac/auth/forgot-password",
            json={"email": user.email},
        )
        assert res_forgot.status_code == 200
        assert res_forgot.json()["success"] is True

        # Verify email was enqueued in MailQueue
        stmt_mail = select(MailQueue).where(MailQueue.recipient_email == user.email).order_by(MailQueue.created_at.desc())
        mail_item = (await db_session.execute(stmt_mail)).scalar_one_or_none()
        assert mail_item is not None
        assert "Password Reset Request" in mail_item.subject

        # 3. Create a deterministic token for reset verification
        token = await create_password_reset_token(user.id, user.company_id, ttl_seconds=900)

        # 4. Password mismatch rejection (400)
        res_mismatch = await client.post(
            "/api/v1/identity_rbac/auth/reset-password",
            json={
                "token": token,
                "new_password": "NewResetPass2026!",
                "confirm_password": "WrongConfirmPass2026!",
            },
        )
        assert res_mismatch.status_code == 400
        assert "do not match" in res_mismatch.json()["detail"].lower()

        # 5. Invalid token rejection (400)
        res_bad_tok = await client.post(
            "/api/v1/identity_rbac/auth/reset-password",
            json={
                "token": "pr_invalid_token_12345",
                "new_password": "NewResetPass2026!",
                "confirm_password": "NewResetPass2026!",
            },
        )
        assert res_bad_tok.status_code == 400
        assert "invalid or expired" in res_bad_tok.json()["detail"].lower()

        # 6. Valid reset password execution (200)
        res_reset = await client.post(
            "/api/v1/identity_rbac/auth/reset-password",
            json={
                "token": token,
                "new_password": "NewResetPass2026!",
                "confirm_password": "NewResetPass2026!",
            },
        )
        assert res_reset.status_code == 200
        assert res_reset.json()["success"] is True

        # 7. Token replay rejection (single-use burned token) (400)
        res_replay = await client.post(
            "/api/v1/identity_rbac/auth/reset-password",
            json={
                "token": token,
                "new_password": "AnotherPass2026!",
                "confirm_password": "AnotherPass2026!",
            },
        )
        assert res_replay.status_code == 400
        assert "invalid or expired" in res_replay.json()["detail"].lower()

        # 8. Verify login: old password fails, new reset password succeeds
        res_log_old = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user.username, "password": "OldPassword123!"},
        )
        assert res_log_old.status_code == 401

        res_log_new = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user.username, "password": "NewResetPass2026!"},
        )
        assert res_log_new.status_code == 200
        assert "access_token" in res_log_new.json()


@pytest.mark.asyncio
async def test_email_verification_lifecycle(db_session: AsyncSession):
    """Verify registration defaults email_verified=False, enqueues verification email, and verifies via token."""
    comp_id = uuid.uuid4()
    company = Company(
        id=comp_id,
        name="Verification Tenant",
        code=f"VER_{uuid.uuid4().hex[:4]}",
        allow_registration=True,
    )
    db_session.add(company)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Register a new user
        reg_username = f"new_signup_{uuid.uuid4().hex[:6]}"
        reg_email = f"{reg_username}@verifycorp.com"
        res_reg = await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={
                "company_id": str(company.id),
                "email": reg_email,
                "username": reg_username,
                "password": "SecurePassword2026!",
                "full_name": "New Signup User",
            },
        )
        assert res_reg.status_code == 201
        user_data = res_reg.json()
        assert user_data["email_verified"] is False
        user_id = uuid.UUID(user_data["id"])

        # Verify welcome verification email was enqueued in MailQueue
        stmt_mail = select(MailQueue).where(MailQueue.recipient_email == reg_email).order_by(MailQueue.created_at.desc())
        mail_item = (await db_session.execute(stmt_mail)).scalar_one_or_none()
        assert mail_item is not None
        assert "Verify Your Email" in mail_item.subject

        # 2. Invalid token rejection (400)
        res_bad_tok = await client.post(
            "/api/v1/identity_rbac/auth/verify-email",
            json={"token": "em_invalid_nonexistent_token"},
        )
        assert res_bad_tok.status_code == 400
        assert "invalid or expired" in res_bad_tok.json()["detail"].lower()

        # 3. Create valid verification token
        token = await create_email_verification_token(user_id)

        # 4. Valid email verification (200)
        res_verify = await client.post(
            "/api/v1/identity_rbac/auth/verify-email",
            json={"token": token},
        )
        assert res_verify.status_code == 200
        assert res_verify.json()["success"] is True

        # 5. Verify user model in DB has email_verified=True
        stmt_u = select(User).where(User.id == user_id)
        verified_user = (await db_session.execute(stmt_u)).scalar_one()
        assert verified_user.email_verified is True

        # 6. Replay protection: consuming same token again fails (400)
        res_replay = await client.post(
            "/api/v1/identity_rbac/auth/verify-email",
            json={"token": token},
        )
        assert res_replay.status_code == 400
        assert "invalid or expired" in res_replay.json()["detail"].lower()


@pytest.mark.asyncio
async def test_two_factor_authentication_lifecycle(db_session: AsyncSession):
    """Verify complete 2FA lifecycle: setup, enablement, login challenge, verify, recovery codes, and disable."""
    # 1. Seed company & user
    comp_id = uuid.uuid4()
    comp_code = f"2FA_{uuid.uuid4().hex[:6]}"
    company = Company(id=comp_id, name="2FA Secure Org", code=comp_code, allow_registration=True)
    user_name = f"totp_user_{uuid.uuid4().hex[:6]}"
    raw_password = "StrongPassword2026!"
    user = User(
        email=f"{user_name}@2fa.org",
        username=user_name,
        hashed_password=hash_password(raw_password),
        full_name="TOTP Test User",
        email_verified=True,
        two_factor_enabled=False,
        company_id=comp_id,
    )
    db_session.add_all([company, user])
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Initial login before 2FA enabled
        res_initial_login = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user.username, "password": raw_password},
        )
        assert res_initial_login.status_code == 200
        data_login = res_initial_login.json()
        assert data_login["mfa_required"] is False
        assert data_login["access_token"] is not None
        auth_token = data_login["access_token"]
        auth_headers = {"Authorization": f"Bearer {auth_token}"}

        # 2. Setup 2FA
        res_setup = await client.post("/api/v1/identity_rbac/auth/2fa/setup", headers=auth_headers)
        assert res_setup.status_code == 200
        setup_data = res_setup.json()
        assert "secret" in setup_data
        assert "otpauth_url" in setup_data
        secret = setup_data["secret"]
        assert "otpauth://totp/Sovereign:" in setup_data["otpauth_url"]

        # 3. Enable 2FA with bad code (400)
        res_bad_enable = await client.post(
            "/api/v1/identity_rbac/auth/2fa/enable",
            json={"code": "000000"},
            headers=auth_headers,
        )
        assert res_bad_enable.status_code == 400
        assert "verification failed" in res_bad_enable.json()["detail"].lower()

        # 4. Enable 2FA with valid TOTP code
        valid_code = pyotp.TOTP(secret).now()
        res_enable = await client.post(
            "/api/v1/identity_rbac/auth/2fa/enable",
            json={"code": valid_code},
            headers=auth_headers,
        )
        assert res_enable.status_code == 200
        enable_data = res_enable.json()
        assert enable_data["enabled"] is True
        recovery_codes = enable_data["recovery_codes"]
        assert len(recovery_codes) == 8

        # Verify enabling again fails (400)
        res_re_enable = await client.post(
            "/api/v1/identity_rbac/auth/2fa/enable",
            json={"code": valid_code},
            headers=auth_headers,
        )
        assert res_re_enable.status_code == 400

        # 5. Login with 2FA active -> expect MFA challenge
        res_login_2fa = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user.username, "password": raw_password},
        )
        assert res_login_2fa.status_code == 200
        challenge_data = res_login_2fa.json()
        assert challenge_data["mfa_required"] is True
        assert challenge_data["mfa_token"] is not None
        assert challenge_data["access_token"] is None
        mfa_token = challenge_data["mfa_token"]

        # 6. Verify 2FA with invalid code (401)
        res_verify_bad = await client.post(
            "/api/v1/identity_rbac/auth/2fa/verify",
            json={"mfa_token": mfa_token, "code": "999999"},
        )
        assert res_verify_bad.status_code == 401

        # 7. Verify 2FA with valid TOTP code
        totp_code = pyotp.TOTP(secret).now()
        res_verify_good = await client.post(
            "/api/v1/identity_rbac/auth/2fa/verify",
            json={"mfa_token": mfa_token, "code": totp_code},
        )
        assert res_verify_good.status_code == 200
        verified_token_data = res_verify_good.json()
        assert verified_token_data["mfa_required"] is False
        assert verified_token_data["access_token"] is not None
        assert verified_token_data["user"]["two_factor_enabled"] is True

        # 8. Test emergency recovery code during login
        res_login_rc = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user.username, "password": raw_password},
        )
        rc_mfa_token = res_login_rc.json()["mfa_token"]
        target_rc = recovery_codes[0]

        res_verify_rc = await client.post(
            "/api/v1/identity_rbac/auth/2fa/verify",
            json={"mfa_token": rc_mfa_token, "code": target_rc},
        )
        assert res_verify_rc.status_code == 200
        assert res_verify_rc.json()["access_token"] is not None

        # Try to use the same recovery code again -> fails (single-use burned!)
        res_login_rc_reuse = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user.username, "password": raw_password},
        )
        rc_reuse_mfa_token = res_login_rc_reuse.json()["mfa_token"]
        res_verify_rc_reuse = await client.post(
            "/api/v1/identity_rbac/auth/2fa/verify",
            json={"mfa_token": rc_reuse_mfa_token, "code": target_rc},
        )
        assert res_verify_rc_reuse.status_code == 401

        # 9. Disable 2FA: test wrong password (401)
        res_bad_pw_dis = await client.post(
            "/api/v1/identity_rbac/auth/2fa/disable",
            json={"password": "WrongPassword123!", "code": pyotp.TOTP(secret).now()},
            headers=auth_headers,
        )
        assert res_bad_pw_dis.status_code == 401

        # Disable 2FA: test wrong code (400)
        res_bad_code_dis = await client.post(
            "/api/v1/identity_rbac/auth/2fa/disable",
            json={"password": raw_password, "code": "000000"},
            headers=auth_headers,
        )
        assert res_bad_code_dis.status_code == 400

        # Disable 2FA: correct password & valid TOTP code (200)
        res_disable = await client.post(
            "/api/v1/identity_rbac/auth/2fa/disable",
            json={"password": raw_password, "code": pyotp.TOTP(secret).now()},
            headers=auth_headers,
        )
        assert res_disable.status_code == 200
        assert res_disable.json()["success"] is True

        # 10. Login after 2FA disabled -> standard direct login (no challenge)
        res_login_after = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user.username, "password": raw_password},
        )
        assert res_login_after.status_code == 200
        assert res_login_after.json()["mfa_required"] is False
        assert res_login_after.json()["access_token"] is not None
        assert res_login_after.json()["user"]["two_factor_enabled"] is False





