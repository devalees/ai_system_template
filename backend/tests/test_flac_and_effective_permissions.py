"""Automated test suite for Field-Level Access Control (FLAC) and Effective Permissions Engine."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from main import app
from core.exceptions import PermissionDeniedException
from modules.base.identity_rbac.models import (
    Company,
    User,
    Group,
    Permission,
    UserGroupLink,
    GroupPermissionLink,
    UserPermissionLink,
)
from modules.base.identity_rbac.security import hash_password, create_access_token
from modules.base.identity_rbac.dependencies import require_permission, require_field_permission
from modules.base.identity_rbac.flac_service import (
    FLACService,
    register_guarded_fields,
    get_guarded_fields,
)


# Test route protected by an atomic permission
@app.get("/test/flac-protected-action")
async def flac_protected_action(
    current_user: User = Depends(require_permission("accounting.budget.override")),
):
    return {"status": "granted", "actor": current_user.username}


@pytest.mark.asyncio
async def test_direct_user_permission_overrides_without_role_explosion(db_session: AsyncSession):
    """Verify granting a direct permission to a user bypasses group boundaries without creating a new role."""
    # 1. Setup company, group, and user
    company = Company(name="FLAC Corp", code=f"FLAC_{uuid.uuid4().hex[:4]}")
    db_session.add(company)
    await db_session.flush()

    # Standard "Accountant" role with read-only permissions
    role = Group(name="Standard Accountant", description="Basic bookkeeping", group_type="role", company_id=company.id)
    db_session.add(role)
    await db_session.flush()

    # Query or create read_perm
    read_code = f"accounting.invoice.read_{uuid.uuid4().hex[:6]}"
    read_perm = Permission(
        code=read_code,
        name="Read Invoices",
        module_name="accounting",
        resource="invoice",
        action="read",
        ownership_scope="GLOBAL",
        permission_type="model",
        company_id=company.id,
    )
    db_session.add(read_perm)

    # Query or create override_perm for /test/flac-protected-action
    override_perm = (await db_session.execute(select(Permission).where(Permission.code == "accounting.budget.override"))).scalars().first()
    if not override_perm:
        override_perm = Permission(
            code="accounting.budget.override",
            name="Override Budget",
            module_name="accounting",
            resource="budget",
            action="override",
            ownership_scope="GLOBAL",
            permission_type="model",
            company_id=company.id,
        )
        db_session.add(override_perm)

    await db_session.flush()

    # Link only read_perm to role (not override_perm)
    db_session.add(GroupPermissionLink(group_id=role.id, permission_id=read_perm.id, company_id=company.id))

    user = User(
        email=f"ahmed_{uuid.uuid4().hex[:6]}@flac.local",
        username=f"ahmed_{uuid.uuid4().hex[:6]}",
        hashed_password=hash_password("UserPass2026!"),
        full_name="Ahmed Accountant",
        user_type="human",
        is_superuser=False,
        email_verified=True,
        company_id=company.id,
    )
    db_session.add(user)
    await db_session.flush()

    # Assign user to standard role
    db_session.add(UserGroupLink(user_id=user.id, group_id=role.id, company_id=company.id))
    await db_session.commit()

    token = create_access_token(user_id=user.id, company_id=company.id, user_type=user.user_type)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step A: Request protected endpoint without permission -> 403 Forbidden
        res = await client.get(
            "/test/flac-protected-action",
            headers={"Authorization": f"Bearer {token}", "X-Company-ID": str(company.id)},
        )
        assert res.status_code == 403

        # Step B: Add Direct Permission Override directly on user (no role cloning!)
        direct_link = UserPermissionLink(
            user_id=user.id,
            permission_id=override_perm.id,
            is_granted=True,
            company_id=company.id,
        )
        db_session.add(direct_link)
        await db_session.commit()

        # Step C: Request protected endpoint again -> 200 OK (Defeating role explosion!)
        res_after = await client.get(
            "/test/flac-protected-action",
            headers={"Authorization": f"Bearer {token}", "X-Company-ID": str(company.id)},
        )
        assert res_after.status_code == 200
        assert res_after.json()["status"] == "granted"


@pytest.mark.asyncio
async def test_direct_user_explicit_revocation(db_session: AsyncSession):
    """Verify an explicit negative override (is_granted=False) revokes a permission granted by a group."""
    company = Company(name="Revoke Corp", code=f"REV_{uuid.uuid4().hex[:4]}")
    db_session.add(company)
    await db_session.flush()

    role = Group(name="Supervisors", group_type="role", company_id=company.id)
    db_session.add(role)
    await db_session.flush()

    perm_code = f"orders.order.delete_{uuid.uuid4().hex[:6]}"
    perm = Permission(
        code=perm_code,
        name="Delete Orders",
        module_name="orders",
        resource="order",
        action="delete",
        ownership_scope="GLOBAL",
        permission_type="model",
        company_id=company.id,
    )
    db_session.add(perm)
    await db_session.flush()

    db_session.add(GroupPermissionLink(group_id=role.id, permission_id=perm.id, company_id=company.id))

    user = User(
        email=f"sarah_{uuid.uuid4().hex[:6]}@revoke.local",
        username=f"sarah_{uuid.uuid4().hex[:6]}",
        hashed_password=hash_password("UserPass2026!"),
        full_name="Sarah Supervisor",
        user_type="human",
        is_superuser=False,
        email_verified=True,
        company_id=company.id,
    )
    db_session.add(user)
    await db_session.flush()

    db_session.add(UserGroupLink(user_id=user.id, group_id=role.id, company_id=company.id))
    await db_session.commit()

    # Initially has permission from group
    assert await FLACService.has_permission(user, perm_code, db_session) is True

    # Add explicit negative override (revocation)
    revocation_link = UserPermissionLink(
        user_id=user.id,
        permission_id=perm.id,
        is_granted=False,
        company_id=company.id,
    )
    db_session.add(revocation_link)
    await db_session.commit()

    # Now permission is denied even though the group still grants it
    assert await FLACService.has_permission(user, perm_code, db_session) is False


@pytest.mark.asyncio
async def test_effective_permissions_matrix_endpoint(db_session: AsyncSession):
    """Verify GET /auth/me/permissions returns comprehensive roles, direct overrides, and FLAC matrix."""
    company = Company(name="Matrix Corp", code=f"MAT_{uuid.uuid4().hex[:4]}")
    db_session.add(company)
    await db_session.flush()

    role = Group(name="Sales Representatives", group_type="role", company_id=company.id)
    db_session.add(role)
    await db_session.flush()

    m_code = f"crm.lead.read_{uuid.uuid4().hex[:6]}"
    f_field = f"rev_{uuid.uuid4().hex[:4]}"
    f_code = f"crm.lead.{f_field}:read"

    m_perm = Permission(
        code=m_code,
        name="Read Leads",
        module_name="crm",
        resource="lead",
        action="read",
        ownership_scope="GLOBAL",
        permission_type="model",
        company_id=company.id,
    )
    f_perm = Permission(
        code=f_code,
        name="Read Lead Revenue",
        module_name="crm",
        resource="lead",
        action="read",
        ownership_scope="GLOBAL",
        permission_type="field",
        field_name=f_field,
        company_id=company.id,
    )
    db_session.add_all([m_perm, f_perm])
    await db_session.flush()

    db_session.add(GroupPermissionLink(group_id=role.id, permission_id=m_perm.id, company_id=company.id))

    user = User(
        email=f"rep_{uuid.uuid4().hex[:6]}@matrix.local",
        username=f"rep_{uuid.uuid4().hex[:6]}",
        hashed_password=hash_password("UserPass2026!"),
        full_name="Sales Rep",
        user_type="human",
        is_superuser=False,
        email_verified=True,
        company_id=company.id,
    )
    db_session.add(user)
    await db_session.flush()

    db_session.add(UserGroupLink(user_id=user.id, group_id=role.id, company_id=company.id))
    # Direct grant on the field permission
    db_session.add(UserPermissionLink(user_id=user.id, permission_id=f_perm.id, is_granted=True, company_id=company.id))
    await db_session.commit()

    token = create_access_token(user_id=user.id, company_id=company.id, user_type=user.user_type)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(
            "/api/v1/identity_rbac/auth/me/permissions",
            headers={"Authorization": f"Bearer {token}", "X-Company-ID": str(company.id)},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["user_id"] == str(user.id)
        assert data["is_superuser"] is False
        assert len(data["assigned_roles"]) == 1
        assert data["assigned_roles"][0]["name"] == "Sales Representatives"
        assert len(data["direct_overrides"]) == 1
        assert data["direct_overrides"][0]["code"] == f_code
        assert m_code in data["model_permissions"]
        assert f_field in data["field_permissions"]["lead"]["read"]


@pytest.mark.asyncio
async def test_flac_egress_sanitization_read_layer(db_session: AsyncSession):
    """Verify guarded fields are stripped from response payloads when caller lacks field read capability."""
    register_guarded_fields("vendor", ["bank_account", "tax_identifier"])

    raw_vendor = {
        "id": str(uuid.uuid4()),
        "name": "Acme Global Supplies",
        "email": "billing@acme.local",
        "bank_account": "US89370400440532013000",
        "tax_identifier": "TX-998877",
    }

    # Scenario A: User with no field permissions -> guarded fields pruned
    sanitized_a = FLACService.sanitize_read_fields(
        record_dict=raw_vendor,
        resource_name="vendor",
        effective_codes={"vendor.read"},
        is_superuser=False,
    )
    assert "bank_account" not in sanitized_a
    assert "tax_identifier" not in sanitized_a
    assert sanitized_a["name"] == "Acme Global Supplies"

    # Scenario B: User with bank_account:read only -> bank_account preserved, tax_identifier pruned
    sanitized_b = FLACService.sanitize_read_fields(
        record_dict=raw_vendor,
        resource_name="vendor",
        effective_codes={"vendor.read", "vendor.bank_account:read"},
        is_superuser=False,
    )
    assert "bank_account" in sanitized_b
    assert sanitized_b["bank_account"] == "US89370400440532013000"
    assert "tax_identifier" not in sanitized_b

    # Scenario C: Superuser -> everything preserved
    sanitized_c = FLACService.sanitize_read_fields(
        record_dict=raw_vendor,
        resource_name="vendor",
        effective_codes=set(),
        is_superuser=True,
    )
    assert "bank_account" in sanitized_c
    assert "tax_identifier" in sanitized_c


@pytest.mark.asyncio
async def test_flac_write_validation_ingress_guard():
    """Verify ingress validator blocks mutating guarded fields without explicit write capability."""
    register_guarded_fields("invoice", ["discount_rate", "custom_tax_id"])

    # Scenario A: Modifying normal field -> passes
    FLACService.validate_write_fields(
        payload_dict={"notes": "Regular payment terms"},
        resource_name="invoice",
        effective_codes={"invoice.update"},
        is_superuser=False,
    )

    # Scenario B: Modifying guarded field without write capability -> raises PermissionDeniedException
    with pytest.raises(PermissionDeniedException) as exc_info:
        FLACService.validate_write_fields(
            payload_dict={"discount_rate": 25.0},
            resource_name="invoice",
            effective_codes={"invoice.update"},
            is_superuser=False,
        )
    assert "discount_rate" in str(exc_info.value)

    # Scenario C: Modifying guarded field with explicit write capability -> passes
    FLACService.validate_write_fields(
        payload_dict={"discount_rate": 25.0},
        resource_name="invoice",
        effective_codes={"invoice.update", "invoice.discount_rate:write"},
        is_superuser=False,
    )


@pytest.mark.asyncio
async def test_flac_first_class_ai_agent_and_superuser_bypass(db_session: AsyncSession):
    """Verify an AI Agent user (user_type='ai_agent') is governed symmetrically by FLAC."""
    company = Company(name="AI Corp", code=f"AIC_{uuid.uuid4().hex[:4]}")
    db_session.add(company)
    await db_session.flush()

    bot_agent = User(
        email=f"bot_{uuid.uuid4().hex[:6]}@sovereign.local",
        username=f"bot_{uuid.uuid4().hex[:6]}",
        hashed_password=hash_password("AgentPass2026!"),
        full_name="Procurement AI Agent",
        user_type="ai_agent",
        is_superuser=False,
        email_verified=True,
        company_id=company.id,
    )
    super_admin = User(
        email=f"root_{uuid.uuid4().hex[:6]}@sovereign.local",
        username=f"root_{uuid.uuid4().hex[:6]}",
        hashed_password=hash_password("RootPass2026!"),
        full_name="Super Administrator",
        user_type="human",
        is_superuser=True,
        email_verified=True,
        company_id=company.id,
    )
    db_session.add_all([bot_agent, super_admin])
    await db_session.commit()

    register_guarded_fields("contract", ["internal_profit_margin", "risk_score"])

    contract_payload = {
        "title": "Hardware Supply 2026",
        "vendor": "Dell Technologies",
        "internal_profit_margin": "18.5%",
        "risk_score": "LOW",
    }

    # Bot agent has standard contract.read but no guarded field read
    bot_sanitized = FLACService.sanitize_read_fields(
        contract_payload,
        resource_name="contract",
        effective_codes={"contract.read"},
        is_superuser=bot_agent.is_superuser,
    )
    assert "internal_profit_margin" not in bot_sanitized
    assert "risk_score" not in bot_sanitized
    assert bot_sanitized["vendor"] == "Dell Technologies"

    # Superuser has universal bypass
    super_sanitized = FLACService.sanitize_read_fields(
        contract_payload,
        resource_name="contract",
        effective_codes=set(),
        is_superuser=super_admin.is_superuser,
    )
    assert "internal_profit_margin" in super_sanitized
    assert "risk_score" in super_sanitized


@pytest.mark.asyncio
async def test_user_permission_override_rest_api_lifecycle(db_session: AsyncSession):
    """Verify REST API endpoints for direct user permission overrides (POST, GET, DELETE)."""
    company = Company(name="API Corp", code=f"API_{uuid.uuid4().hex[:4]}")
    db_session.add(company)
    await db_session.flush()

    super_user = User(
        email=f"admin_{uuid.uuid4().hex[:6]}@api.local",
        username=f"admin_{uuid.uuid4().hex[:6]}",
        hashed_password=hash_password("AdminPass2026!"),
        full_name="Admin",
        user_type="human",
        is_superuser=True,
        company_id=company.id,
    )
    target_user = User(
        email=f"target_{uuid.uuid4().hex[:6]}@api.local",
        username=f"target_{uuid.uuid4().hex[:6]}",
        hashed_password=hash_password("UserPass2026!"),
        full_name="Target User",
        user_type="human",
        is_superuser=False,
        company_id=company.id,
    )
    perm_code = f"reports.export.csv_{uuid.uuid4().hex[:6]}"
    perm = Permission(
        code=perm_code,
        name="Export CSV Reports",
        module_name="reports",
        resource="export",
        action="export",
        ownership_scope="GLOBAL",
        permission_type="model",
        company_id=company.id,
    )
    db_session.add_all([super_user, target_user, perm])
    await db_session.commit()

    admin_token = create_access_token(user_id=super_user.id, company_id=company.id, user_type="human")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Add direct permission override on target user
        post_res = await client.post(
            f"/api/v1/identity_rbac/users/{target_user.id}/permissions",
            headers={"Authorization": f"Bearer {admin_token}", "X-Company-ID": str(company.id)},
            json={"permission_id": str(perm.id), "is_granted": True},
        )
        assert post_res.status_code == 201
        created_override = post_res.json()
        assert created_override["user_id"] == str(target_user.id)
        assert created_override["is_granted"] is True
        assert created_override["permission"]["code"] == perm_code

        # 2. Query target user's effective permissions
        get_res = await client.get(
            f"/api/v1/identity_rbac/users/{target_user.id}/permissions",
            headers={"Authorization": f"Bearer {admin_token}", "X-Company-ID": str(company.id)},
        )
        assert get_res.status_code == 200
        eff_data = get_res.json()
        assert len(eff_data["direct_overrides"]) == 1
        assert perm_code in eff_data["all_effective_codes"]

        # 3. Delete the direct permission override
        del_res = await client.delete(
            f"/api/v1/identity_rbac/users/{target_user.id}/permissions/{perm.id}",
            headers={"Authorization": f"Bearer {admin_token}", "X-Company-ID": str(company.id)},
        )
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "deleted"

        # 4. Verify effective permissions reverted
        get_res_reverted = await client.get(
            f"/api/v1/identity_rbac/users/{target_user.id}/permissions",
            headers={"Authorization": f"Bearer {admin_token}", "X-Company-ID": str(company.id)},
        )
        assert len(get_res_reverted.json()["direct_overrides"]) == 0
        assert perm_code not in get_res_reverted.json()["all_effective_codes"]
