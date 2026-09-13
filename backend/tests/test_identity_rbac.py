"""Automated test suite for Identity & Contextual RBAC module."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from core.app import create_app
from core.database import get_db
from modules.base.identity_rbac.models import User, Group, Permission, UserGroupLink, GroupPermissionLink
from modules.base.identity_rbac.security import hash_password
from modules.base.identity_rbac.dependencies import require_permission

from main import app

# Test route protected by granular permission
@app.get("/test/protected-capability")
async def protected_endpoint(current_user: User = Depends(require_permission("orders.invoice.approve"))):
    return {"status": "approved", "approver": current_user.username}


@pytest.mark.asyncio
async def test_user_registration_and_login(db_session: AsyncSession):
    """Verify registration of human user and subsequent JWT login."""
    unique_user = f"user_{uuid.uuid4().hex[:6]}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Register User
        reg_payload = {
            "email": f"{unique_user}@example.com",
            "username": unique_user,
            "password": "SecurePassword2026!",
            "full_name": "Test User",
            "user_type": "human",
        }
        res_reg = await client.post("/api/v1/identity_rbac/auth/register", json=reg_payload)
        assert res_reg.status_code == 201
        reg_data = res_reg.json()
        assert reg_data["username"] == unique_user
        assert reg_data["user_type"] == "human"

        # 2. Login with valid credentials
        login_payload = {
            "identifier": unique_user,
            "password": "SecurePassword2026!",
        }
        res_login = await client.post("/api/v1/identity_rbac/auth/login", json=login_payload)
        assert res_login.status_code == 200
        token_data = res_login.json()
        assert "access_token" in token_data
        token = token_data["access_token"]

        # 3. Access /auth/me
        res_me = await client.get(
            "/api/v1/identity_rbac/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_me.status_code == 200
        assert res_me.json()["username"] == unique_user

        # 4. Login with invalid password fails
        bad_login = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": unique_user, "password": "WrongPassword!"},
        )
        assert bad_login.status_code == 401


@pytest.mark.asyncio
async def test_first_class_ai_agent_identity(db_session: AsyncSession):
    """Verify first-class AI Agent registration, token issuance, and symmetric auth."""
    agent_id = f"bot_agent_{uuid.uuid4().hex[:6]}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "email": f"{agent_id}@hermes.internal",
            "username": agent_id,
            "password": "AgentSecretToken2026!",
            "full_name": "Autonomous QA Auditor",
            "user_type": "ai_agent",
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
