"""Automated test suite for Identity, Tenant Company Gating & Contextual RBAC module."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
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
from modules.base.identity_rbac.security import hash_password
from modules.base.identity_rbac.dependencies import require_permission

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
