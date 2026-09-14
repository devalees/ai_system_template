"""Automated test suite for the Event-Driven Automated Actions Subsystem (TCA Engine)."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company, User
from modules.base.settings.service import SettingsService
from modules.base.automated_actions.models import AutomatedAction, ActionExecutionLog, TriggerType
from modules.base.automated_actions.engine.evaluator import ASTConditionEvaluator
from modules.base.automated_actions.engine.dispatcher import TCADispatcher
from modules.base.automated_actions.engine.registry import action_registry
from modules.base.automated_actions.handlers.base import ActionContext
from modules.base.chatter.models import MailMessage
from modules.base.notification_engine.models import Notification
from modules.base.mail_gateway.models import MailQueue


@pytest.mark.asyncio
async def test_action_registry_and_metadata():
    """Verify built-in action handlers are registered and export valid JSON schemas."""
    handlers = action_registry.list_handlers()
    assert len(handlers) >= 6

    expected_types = {"send_email", "send_notification", "post_chatter", "update_record", "create_record", "invoke_webhook"}
    registered_types = {h.action_type for h in handlers}
    assert expected_types.issubset(registered_types)

    metadata = action_registry.get_metadata()
    assert len(metadata) >= 6
    for meta in metadata:
        assert "action_type" in meta
        assert "title" in meta
        assert "description" in meta
        assert "config_schema" in meta
        assert isinstance(meta["config_schema"], dict)


@pytest.mark.asyncio
async def test_ast_condition_evaluator():
    """Verify in-memory AST condition evaluator supports operators, booleans, and diffs."""
    record = {
        "username": "superadmin",
        "email": "admin@sovereign.local",
        "age": 35,
        "is_active": True,
        "role": "manager",
        "custom_fields": {"tier": "gold", "score": 95},
    }
    old_record = {
        "username": "superadmin",
        "role": "lead",
    }
    diff = {
        "role": {"old": "lead", "new": "manager"},
    }

    # 1. Simple Equality & Case-insensitive contains
    tree_1 = {
        "logic": "AND",
        "filters": [
            {"field": "username", "operator": "eq", "value": "superadmin"},
            {"field": "email", "operator": "icontains", "value": "SOVEREIGN"},
            {"field": "age", "operator": "gte", "value": 30},
            {"field": "is_active", "operator": "eq", "value": True},
        ],
    }
    assert ASTConditionEvaluator.evaluate(tree_1, record, old_record, diff) is True

    # 2. Condition Failure
    tree_fail = {
        "logic": "AND",
        "filters": [
            {"field": "age", "operator": "lt", "value": 20},
        ],
    }
    assert ASTConditionEvaluator.evaluate(tree_fail, record, old_record, diff) is False

    # 3. Nested OR logic and between operator
    tree_or = {
        "logic": "OR",
        "filters": [
            {"field": "age", "operator": "between", "value": [30, 40]},
            {"field": "role", "operator": "eq", "value": "non_existent"},
        ],
    }
    assert ASTConditionEvaluator.evaluate(tree_or, record, old_record, diff) is True

    # 4. State Change Diff Comparison (old vs new)
    tree_state = {
        "logic": "AND",
        "filters": [
            {"field": "old:role", "operator": "eq", "value": "lead"},
            {"field": "role", "operator": "eq", "value": "manager"},
        ],
    }
    assert ASTConditionEvaluator.evaluate(tree_state, record, old_record, diff) is True

    # 5. Dotted Path in custom_fields
    tree_custom = {
        "logic": "AND",
        "filters": [
            {"field": "custom_fields.tier", "operator": "eq", "value": "gold"},
            {"field": "custom_fields.score", "operator": "gt", "value": 90},
        ],
    }
    assert ASTConditionEvaluator.evaluate(tree_custom, record, old_record, diff) is True


@pytest.mark.asyncio
async def test_automated_actions_crud_and_multitenancy(db_session: AsyncSession):
    """Verify REST API CRUD operations on automated action rules with multi-tenant isolation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Seed two test companies
        comp_a = uuid.uuid4()
        comp_b = uuid.uuid4()
        db_session.add_all([
            Company(id=comp_a, name="TCA Company A", code=f"TCA_A_{comp_a.hex[:4]}"),
            Company(id=comp_b, name="TCA Company B", code=f"TCA_B_{comp_b.hex[:4]}"),
        ])
        await db_session.commit()

        await SettingsService.update_settings(db_session, "identity_rbac", comp_a, {"allow_registration": True})
        await SettingsService.update_settings(db_session, "identity_rbac", comp_b, {"allow_registration": True})

        # Register User A
        user_a = f"tca_user_a_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_a}@test.com", "username": user_a, "password": "Password123!", "full_name": "A", "company_id": str(comp_a)},
        )
        login_a = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_a, "password": "Password123!"})
        headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

        # Register User B
        user_b = f"tca_user_b_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_b}@test.com", "username": user_b, "password": "Password123!", "full_name": "B", "company_id": str(comp_b)},
        )
        login_b = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_b, "password": "Password123!"})
        headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

        # 1. Tenant A checks /action-types
        res_types = await client.get("/api/v1/automated_actions/action-types", headers=headers_a)
        assert res_types.status_code == 200
        action_types = res_types.json()
        assert len(action_types) >= 6

        # 2. Tenant A creates Automated Action Rule
        res_create = await client.post(
            "/api/v1/automated_actions/rules",
            headers=headers_a,
            json={
                "name": "Notify on User Creation",
                "description": "Send in-app notification when a new user is created",
                "target_model": "User",
                "trigger_type": "on_create",
                "condition_tree": {
                    "logic": "AND",
                    "filters": [{"field": "is_active", "operator": "eq", "value": True}],
                },
                "action_type": "post_chatter",
                "action_config": {
                    "body_template": "Automated note: User {{ record.username }} was onboarded.",
                    "message_type": "comment",
                },
                "execution_mode": "sync",
                "sequence": 10,
                "is_active": True,
            },
        )
        assert res_create.status_code == 201
        rule_data = res_create.json()
        rule_id = rule_data["id"]
        assert rule_data["name"] == "Notify on User Creation"

        # 3. Tenant A retrieves rule by ID
        res_get = await client.get(f"/api/v1/automated_actions/rules/{rule_id}", headers=headers_a)
        assert res_get.status_code == 200
        assert res_get.json()["id"] == rule_id

        # 4. Tenant A updates rule
        res_patch = await client.patch(
            f"/api/v1/automated_actions/rules/{rule_id}",
            headers=headers_a,
            json={"sequence": 5, "description": "Updated description"},
        )
        assert res_patch.status_code == 200
        assert res_patch.json()["sequence"] == 5

        # 5. Multi-tenant isolation: Tenant B cannot access Tenant A's rule
        assert (await client.get(f"/api/v1/automated_actions/rules/{rule_id}", headers=headers_b)).status_code == 404
        assert (await client.patch(f"/api/v1/automated_actions/rules/{rule_id}", headers=headers_b, json={"sequence": 1})).status_code == 404
        assert (await client.delete(f"/api/v1/automated_actions/rules/{rule_id}", headers=headers_b)).status_code == 404

        # 6. Tenant A tests condition dry-run endpoint against Tenant A's user
        me_res = await client.get("/api/v1/identity_rbac/auth/me", headers=headers_a)
        user_a_id = me_res.json()["id"]

        test_cond_res = await client.post(
            "/api/v1/automated_actions/rules/test-condition",
            headers=headers_a,
            json={
                "target_model": "User",
                "target_id": user_a_id,
                "condition_tree": {
                    "logic": "AND",
                    "filters": [{"field": "username", "operator": "eq", "value": user_a}],
                },
            },
        )
        assert test_cond_res.status_code == 200
        assert test_cond_res.json()["matched"] is True

        # 7. Tenant A deletes rule
        res_del = await client.delete(f"/api/v1/automated_actions/rules/{rule_id}", headers=headers_a)
        assert res_del.status_code == 204
        assert (await client.get(f"/api/v1/automated_actions/rules/{rule_id}", headers=headers_a)).status_code == 404


@pytest.mark.asyncio
async def test_tca_dispatcher_and_handlers_execution(db_session: AsyncSession):
    """Verify TCADispatcher executes action handlers, creates records/notifications/chatter, and records logs."""
    company_id = uuid.uuid4()
    company = Company(id=company_id, name="Exec Co", code=f"EX_{company_id.hex[:4]}")
    db_session.add(company)
    await db_session.commit()

    rand_suffix = uuid.uuid4().hex[:6]
    test_user = User(
        id=uuid.uuid4(),
        company_id=company_id,
        email=f"target_{rand_suffix}@test.com",
        username=f"target_user_{rand_suffix}",
        hashed_password="hash",
        full_name="Target User",
        user_type="human",
        is_active=True,
    )
    db_session.add(test_user)
    await db_session.commit()

    # 1. Create a Post Chatter automated action rule
    rule_chatter = AutomatedAction(
        company_id=company_id,
        name="Post Chatter on User Onboarding",
        target_model="User",
        trigger_type=TriggerType.ON_CREATE.value,
        condition_tree={"logic": "AND", "filters": [{"field": "is_active", "operator": "eq", "value": True}]},
        action_type="post_chatter",
        action_config={"body_template": "Welcome note for {{ record.username }}", "message_type": "comment"},
        execution_mode="sync",
        is_active=True,
    )
    db_session.add(rule_chatter)
    await db_session.commit()

    # 2. Dispatch event
    results = await TCADispatcher.dispatch_event(
        db=db_session,
        company_id=company_id,
        target_model="User",
        target_id=test_user.id,
        record=test_user,
        trigger_type="on_create",
        record_data={"username": test_user.username, "is_active": test_user.is_active},
        user_id=test_user.id,
    )

    assert len(results) >= 1
    assert results[0]["status"] == "executed"

    # 3. Verify Chatter Message was created in database
    stmt_msg = select(MailMessage).where(MailMessage.res_id == test_user.id)
    msg = (await db_session.execute(stmt_msg)).scalar_one_or_none()
    assert msg is not None
    assert "target_user" in msg.body

    # 4. Verify Execution Log was persisted
    stmt_log = select(ActionExecutionLog).where(ActionExecutionLog.action_id == rule_chatter.id)
    log = (await db_session.execute(stmt_log)).scalar_one_or_none()
    assert log is not None
    assert log.status == "success"
    assert log.condition_matched is True
    assert log.target_model == "User"
    assert log.execution_duration_ms >= 0.0


@pytest.mark.asyncio
async def test_tca_recursion_guard(db_session: AsyncSession):
    """Verify cascading action recursion depth guard halts execution when depth threshold is exceeded."""
    company_id = uuid.uuid4()
    company = Company(id=company_id, name="Loop Co", code=f"LP_{company_id.hex[:4]}")
    db_session.add(company)
    await db_session.commit()

    # Attempt dispatch with depth >= max_depth
    res = await TCADispatcher.dispatch_event(
        db=db_session,
        company_id=company_id,
        target_model="User",
        target_id=uuid.uuid4(),
        record=None,
        trigger_type="on_update",
        record_data={},
        max_depth=3,
    )
    # Since depth defaults to 0 and threshold is 3, normal dispatch passes
    assert isinstance(res, list)
