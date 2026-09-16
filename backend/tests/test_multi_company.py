"""Comprehensive tests for Enterprise Multi-Company Architecture, Aggregated Querying, and Security Isolation."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from core.context import (
    get_active_company_id,
    get_active_company_ids,
    set_active_company_id,
    set_active_company_ids,
)
from modules.base.identity_rbac.models import User, Company, UserCompanyLink
from modules.base.identity_rbac.security import hash_password, create_access_token
from modules.base.lookups.models import Tag


@pytest.mark.asyncio
async def test_context_engine_dual_mode_headers():
    """Verify MultiTenancyContextMiddleware parses single and comma-delimited multi-company headers."""
    comp1 = uuid.uuid4()
    comp2 = uuid.uuid4()

    @app.get("/test/multi-comp-context")
    async def get_multi_comp_context():
        return {
            "primary": str(get_active_company_id()) if get_active_company_id() else None,
            "all": [str(c) for c in (get_active_company_ids() or [])],
        }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Single header
        resp1 = await client.get("/test/multi-comp-context", headers={"X-Company-ID": str(comp1)})
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["primary"] == str(comp1)
        assert data1["all"] == [str(comp1)]

        # 2. Multi header
        resp2 = await client.get(
            "/test/multi-comp-context",
            headers={"X-Company-IDs": f"{comp1},{comp2}"},
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["primary"] == str(comp1)
        assert data2["all"] == [str(comp1), str(comp2)]

        # 3. Explicit primary + multi list
        resp3 = await client.get(
            "/test/multi-comp-context",
            headers={"X-Company-ID": str(comp2), "X-Company-IDs": f"{comp1},{comp2}"},
        )
        assert resp3.status_code == 200
        data3 = resp3.json()
        assert data3["primary"] == str(comp2)
        assert data3["all"] == [str(comp1), str(comp2)]


@pytest.mark.asyncio
async def test_multi_company_orm_query_filtration(db_session: AsyncSession):
    """Verify ORM automatic query filter seamlessly switches between == single and IN multiple."""
    c1_id = uuid.uuid4()
    c2_id = uuid.uuid4()
    c3_id = uuid.uuid4()

    # Create dummy tags belonging to 3 distinct companies
    t1 = Tag(name=f"Tag1-{uuid.uuid4().hex[:6]}", company_id=c1_id)
    t2 = Tag(name=f"Tag2-{uuid.uuid4().hex[:6]}", company_id=c2_id)
    t3 = Tag(name=f"Tag3-{uuid.uuid4().hex[:6]}", company_id=c3_id)
    db_session.add_all([t1, t2, t3])
    await db_session.commit()

    # Scenario A: Filter single company (c1)
    set_active_company_id(c1_id)
    set_active_company_ids([c1_id])
    stmt1 = select(Tag).where(Tag.id.in_([t1.id, t2.id, t3.id]))
    res1 = (await db_session.execute(stmt1)).scalars().all()
    assert len(res1) == 1
    assert res1[0].company_id == c1_id

    # Scenario B: Filter multiple companies (c1 + c2)
    set_active_company_id(c1_id)
    set_active_company_ids([c1_id, c2_id])
    stmt2 = select(Tag).where(Tag.id.in_([t1.id, t2.id, t3.id]))
    res2 = (await db_session.execute(stmt2)).scalars().all()
    assert len(res2) == 2
    comp_ids = {r.company_id for r in res2}
    assert comp_ids == {c1_id, c2_id}

    # Reset
    set_active_company_id(None)
    set_active_company_ids(None)


@pytest.mark.asyncio
async def test_multi_company_security_guard_and_switching(db_session: AsyncSession):
    """Verify 403 authorization guard against unauthorized tenants and company context switching."""
    # 1. Create 3 companies
    comp_a = Company(name=f"Comp A {uuid.uuid4().hex[:4]}", code=f"CA-{uuid.uuid4().hex[:4]}", is_active=True)
    comp_b = Company(name=f"Comp B {uuid.uuid4().hex[:4]}", code=f"CB-{uuid.uuid4().hex[:4]}", is_active=True)
    comp_c = Company(name=f"Comp C {uuid.uuid4().hex[:4]}", code=f"CC-{uuid.uuid4().hex[:4]}", is_active=True)
    db_session.add_all([comp_a, comp_b, comp_c])
    await db_session.commit()

    # 2. Create regular user assigned only to Company A
    user = User(
        email=f"multitest_{uuid.uuid4().hex[:6]}@example.com",
        username=f"user_{uuid.uuid4().hex[:6]}",
        full_name="Multi-Company Tester",
        hashed_password=hash_password("Password123!"),
        company_id=comp_a.id,
        is_superuser=False,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    link_a = UserCompanyLink(
        company_id=comp_a.id,
        user_id=user.id,
        target_company_id=comp_a.id,
        is_default=True,
    )
    db_session.add(link_a)
    await db_session.commit()

    # Create superuser
    superuser = User(
        email=f"super_{uuid.uuid4().hex[:6]}@example.com",
        username=f"super_{uuid.uuid4().hex[:6]}",
        full_name="Super Admin",
        hashed_password=hash_password("Password123!"),
        company_id=comp_a.id,
        is_superuser=True,
        is_active=True,
    )
    db_session.add(superuser)
    await db_session.commit()

    token_user = create_access_token(
        user_id=user.id,
        company_id=comp_a.id,
        user_type="human",
        extra_claims={"allowed_company_ids": [str(comp_a.id)]},
    )
    token_super = create_access_token(
        user_id=superuser.id,
        company_id=comp_a.id,
        user_type="human",
        extra_claims={"allowed_company_ids": [str(comp_a.id)]},
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # A. User accesses Company A -> 200 OK
        resp_a = await client.get(
            "/api/v1/identity_rbac/auth/me",
            headers={"Authorization": f"Bearer {token_user}", "X-Company-ID": str(comp_a.id)},
        )
        assert resp_a.status_code == 200

        # B. User attempts to access Company B (unauthorized) -> 403 Forbidden
        resp_b = await client.get(
            "/api/v1/identity_rbac/auth/me",
            headers={"Authorization": f"Bearer {token_user}", "X-Company-ID": str(comp_b.id)},
        )
        assert resp_b.status_code == 403
        assert "not authorized" in resp_b.json()["detail"].lower()

        # C. User attempts to aggregate with Company C (unauthorized) -> 403 Forbidden
        resp_agg = await client.get(
            "/api/v1/identity_rbac/auth/me",
            headers={"Authorization": f"Bearer {token_user}", "X-Company-IDs": f"{comp_a.id},{comp_c.id}"},
        )
        assert resp_agg.status_code == 403

        # D. Superuser accesses Company B -> 200 OK (Universal Superuser Bypass)
        resp_super = await client.get(
            "/api/v1/identity_rbac/auth/me",
            headers={"Authorization": f"Bearer {token_super}", "X-Company-ID": str(comp_b.id)},
        )
        assert resp_super.status_code == 200

        # E. Assign Company B to User
        assign_resp = await client.post(
            f"/api/v1/identity_rbac/users/{user.id}/companies",
            json={"company_id": str(comp_b.id), "is_default": False},
            headers={"Authorization": f"Bearer {token_super}", "X-Company-ID": str(comp_a.id)},
        )
        assert assign_resp.status_code == 200

        # F. Verify /users/me/companies lists both A and B
        my_comps_resp = await client.get(
            "/api/v1/identity_rbac/users/me/companies",
            headers={"Authorization": f"Bearer {token_user}", "X-Company-ID": str(comp_a.id)},
        )
        assert my_comps_resp.status_code == 200
        my_comps = my_comps_resp.json()
        assert len(my_comps) == 2
        comp_ids_returned = {c["id"] for c in my_comps}
        assert comp_ids_returned == {str(comp_a.id), str(comp_b.id)}

        # G. User switches company context to Company B
        switch_resp = await client.post(
            "/api/v1/identity_rbac/auth/switch-company",
            json={"company_id": str(comp_b.id)},
            headers={"Authorization": f"Bearer {token_user}", "X-Company-ID": str(comp_a.id)},
        )
        assert switch_resp.status_code == 200
        switch_data = switch_resp.json()
        assert switch_data["active_company_id"] == str(comp_b.id)
        new_token = switch_data["access_token"]

        # H. Using new token with Company B succeeds
        resp_b_auth = await client.get(
            "/api/v1/identity_rbac/auth/me",
            headers={"Authorization": f"Bearer {new_token}", "X-Company-ID": str(comp_b.id)},
        )
        assert resp_b_auth.status_code == 200

        # I. User attempts to switch to unauthorized Company C -> 403 Forbidden
        switch_fail = await client.post(
            "/api/v1/identity_rbac/auth/switch-company",
            json={"company_id": str(comp_c.id)},
            headers={"Authorization": f"Bearer {token_user}", "X-Company-ID": str(comp_a.id)},
        )
        assert switch_fail.status_code == 403

        # J. Revoke Company B access
        revoke_resp = await client.delete(
            f"/api/v1/identity_rbac/users/{user.id}/companies/{comp_b.id}",
            headers={"Authorization": f"Bearer {token_super}", "X-Company-ID": str(comp_a.id)},
        )
        assert revoke_resp.status_code == 200

        # K. Guard against revoking sole remaining company
        revoke_sole = await client.delete(
            f"/api/v1/identity_rbac/users/{user.id}/companies/{comp_a.id}",
            headers={"Authorization": f"Bearer {token_super}", "X-Company-ID": str(comp_a.id)},
        )
        assert revoke_sole.status_code == 400
        assert "sole company membership" in revoke_sole.json()["detail"].lower()


@pytest.mark.asyncio
async def test_multi_company_user_listing_and_auto_link_creation(db_session: AsyncSession):
    """Verify aggregated user listing across active companies and auto-creation of UserCompanyLink on registration."""
    # 1. Create two active companies
    c_alpha = Company(name=f"Alpha {uuid.uuid4().hex[:4]}", code=f"AL-{uuid.uuid4().hex[:4]}", is_active=True)
    c_beta = Company(name=f"Beta {uuid.uuid4().hex[:4]}", code=f"BE-{uuid.uuid4().hex[:4]}", is_active=True)
    db_session.add_all([c_alpha, c_beta])
    await db_session.commit()

    # 2. Create users in each company
    u_alpha = User(
        email=f"alpha_{uuid.uuid4().hex[:6]}@example.com",
        username=f"alpha_{uuid.uuid4().hex[:6]}",
        full_name="Alpha Employee",
        hashed_password=hash_password("Password123!"),
        company_id=c_alpha.id,
        is_superuser=False,
        is_active=True,
    )
    u_beta = User(
        email=f"beta_{uuid.uuid4().hex[:6]}@example.com",
        username=f"beta_{uuid.uuid4().hex[:6]}",
        full_name="Beta Employee",
        hashed_password=hash_password("Password123!"),
        company_id=c_beta.id,
        is_superuser=False,
        is_active=True,
    )
    # Admin linked to both companies
    admin = User(
        email=f"admin_{uuid.uuid4().hex[:6]}@example.com",
        username=f"admin_{uuid.uuid4().hex[:6]}",
        full_name="Multi-Company Admin",
        hashed_password=hash_password("Password123!"),
        company_id=c_alpha.id,
        is_superuser=False,
        is_active=True,
    )
    db_session.add_all([u_alpha, u_beta, admin])
    await db_session.commit()

    link_adm_a = UserCompanyLink(company_id=c_alpha.id, user_id=admin.id, target_company_id=c_alpha.id, is_default=True)
    link_adm_b = UserCompanyLink(company_id=c_beta.id, user_id=admin.id, target_company_id=c_beta.id, is_default=False)
    db_session.add_all([link_adm_a, link_adm_b])
    await db_session.commit()

    token_admin = create_access_token(
        user_id=admin.id,
        company_id=c_alpha.id,
        user_type="human",
        extra_claims={"allowed_company_ids": [str(c_alpha.id), str(c_beta.id)]},
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Scenario 1: Single company view (Alpha only)
        resp_single = await client.get(
            "/api/v1/identity_rbac/users",
            headers={"Authorization": f"Bearer {token_admin}", "X-Company-ID": str(c_alpha.id)},
        )
        assert resp_single.status_code == 200
        single_users = resp_single.json()
        single_ids = {u["id"] for u in single_users}
        assert str(u_alpha.id) in single_ids
        assert str(u_beta.id) not in single_ids

        # Scenario 2: Aggregated multi-company view (Alpha + Beta)
        resp_multi = await client.get(
            "/api/v1/identity_rbac/users",
            headers={
                "Authorization": f"Bearer {token_admin}",
                "X-Company-ID": str(c_alpha.id),
                "X-Company-IDs": f"{c_alpha.id},{c_beta.id}",
            },
        )
        assert resp_multi.status_code == 200
        multi_users = resp_multi.json()
        multi_ids = {u["id"] for u in multi_users}
        assert str(u_alpha.id) in multi_ids
        assert str(u_beta.id) in multi_ids

        # Scenario 3: Admin provisioning new user automatically generates UserCompanyLink
        new_email = f"provisioned_{uuid.uuid4().hex[:6]}@example.com"
        new_username = f"prov_{uuid.uuid4().hex[:6]}"
        create_user_resp = await client.post(
            "/api/v1/identity_rbac/users",
            json={
                "email": new_email,
                "username": new_username,
                "full_name": "Provisioned Member",
                "password": "StrongPassword2026!",
                "user_type": "human",
                "preferred_language": "en",
            },
            headers={"Authorization": f"Bearer {token_admin}", "X-Company-ID": str(c_alpha.id)},
        )
        assert create_user_resp.status_code == 201
        created_user = create_user_resp.json()
        created_user_id = uuid.UUID(created_user["id"])

        # Check in DB that UserCompanyLink was created with is_default=True
        stmt_chk = select(UserCompanyLink).where(UserCompanyLink.user_id == created_user_id)
        created_links = (await db_session.execute(stmt_chk)).scalars().all()
        assert len(created_links) == 1
        assert created_links[0].target_company_id == c_alpha.id
        assert created_links[0].is_default is True

