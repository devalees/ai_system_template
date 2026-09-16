"""Comprehensive unit and integration tests for Universal Work Items, Tasks & Dependencies."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company
from modules.base.settings.service import SettingsService


@pytest.mark.asyncio
async def test_stages_and_work_items_crud(db_session: AsyncSession):
    """Verify stage and work item CRUD operations with strict tenant isolation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_a = uuid.uuid4()
        comp_b = uuid.uuid4()
        db_session.add(Company(id=comp_a, name="Work Co A", code=f"WA_{comp_a.hex[:4]}"))
        db_session.add(Company(id=comp_b, name="Work Co B", code=f"WB_{comp_b.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_a, {"allow_registration": True})
        await SettingsService.update_settings(db_session, "identity_rbac", comp_b, {"allow_registration": True})

        # Register User A
        user_a = f"work_a_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_a}@test.com", "username": user_a, "password": "Password123!", "full_name": "Work Admin A", "company_id": str(comp_a)},
        )
        login_a = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_a, "password": "Password123!"})
        headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

        # Register User B
        user_b = f"work_b_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_b}@test.com", "username": user_b, "password": "Password123!", "full_name": "Work Admin B", "company_id": str(comp_b)},
        )
        login_b = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_b, "password": "Password123!"})
        headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

        # 1. Company A creates stages
        res_stg1 = await client.post(
            "/api/v1/work_items/stages",
            json={"name": "Backlog", "code": "BACKLOG", "sequence": 10, "is_closed": False, "color": "#94a3b8"},
            headers=headers_a,
        )
        assert res_stg1.status_code == 201, res_stg1.text
        stg1_id = res_stg1.json()["id"]

        res_stg2 = await client.post(
            "/api/v1/work_items/stages",
            json={"name": "Done", "code": "DONE", "sequence": 40, "is_closed": True, "color": "#22c55e"},
            headers=headers_a,
        )
        assert res_stg2.status_code == 201
        stg2_id = res_stg2.json()["id"]

        # 2. Company A creates Work Item
        res_wi = await client.post(
            "/api/v1/work_items",
            json={
                "title": "Design Entity Schema",
                "description": "Create base models and migration script",
                "priority": "high",
                "stage_id": stg1_id,
                "estimated_hours": "8.00",
            },
            headers=headers_a,
        )
        assert res_wi.status_code == 201, res_wi.text
        wi_data = res_wi.json()
        assert wi_data["title"] == "Design Entity Schema"
        assert wi_data["stage_name"] == "Backlog"
        assert wi_data["is_closed"] is False

        # 3. User B cannot see User A's stages or work items
        res_b_stages = await client.get("/api/v1/work_items/stages", headers=headers_b)
        assert res_b_stages.status_code == 200
        assert len(res_b_stages.json()) == 0

        res_b_items = await client.get("/api/v1/work_items", headers=headers_b)
        assert res_b_items.status_code == 200
        assert len(res_b_items.json()) == 0


@pytest.mark.asyncio
async def test_subtask_hierarchy_tree(db_session: AsyncSession):
    """Verify recursive hierarchical sub-task tree structure."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Tree Co", code=f"TR_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        user_name = f"tree_u_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_name}@test.com", "username": user_name, "password": "Password123!", "full_name": "Tree User", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_name, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 1. Create Root Epic
        res_root = await client.post(
            "/api/v1/work_items",
            json={"title": "Epic: Commercial Architecture", "priority": "urgent"},
            headers=headers,
        )
        root_id = res_root.json()["id"]

        # 2. Create Child 1 and Child 2 under Root
        res_c1 = await client.post(
            "/api/v1/work_items",
            json={"title": "Task: Pricing Matrix", "parent_id": root_id, "priority": "high"},
            headers=headers,
        )
        c1_id = res_c1.json()["id"]

        res_c2 = await client.post(
            "/api/v1/work_items",
            json={"title": "Task: Tax Calculation Engine", "parent_id": root_id, "priority": "high"},
            headers=headers,
        )
        c2_id = res_c2.json()["id"]

        # 3. Create Grandchild under Child 1
        res_gc1 = await client.post(
            "/api/v1/work_items",
            json={"title": "Sub-task: Formula Surcharges", "parent_id": c1_id, "priority": "medium"},
            headers=headers,
        )
        gc1_id = res_gc1.json()["id"]

        # 4. Fetch Tree rooted at Epic
        res_tree = await client.get(f"/api/v1/work_items/{root_id}/tree", headers=headers)
        assert res_tree.status_code == 200, res_tree.text
        tree_data = res_tree.json()
        assert tree_data["id"] == root_id
        assert len(tree_data["children"]) == 2

        # Verify child 1 has 1 child (grandchild)
        c1_node = next(c for c in tree_data["children"] if c["id"] == c1_id)
        assert len(c1_node["children"]) == 1
        assert c1_node["children"][0]["id"] == gc1_id

        # Verify child 2 has 0 children
        c2_node = next(c for c in tree_data["children"] if c["id"] == c2_id)
        assert len(c2_node["children"]) == 0


@pytest.mark.asyncio
async def test_dependency_dag_and_cycle_prevention(db_session: AsyncSession):
    """Verify dependency edge linking and rejection of circular dependencies."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="DAG Co", code=f"DAG_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        user_name = f"dag_u_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_name}@test.com", "username": user_name, "password": "Password123!", "full_name": "DAG User", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_name, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # Create Task A, Task B, Task C
        res_a = await client.post("/api/v1/work_items", json={"title": "Task A"}, headers=headers)
        res_b = await client.post("/api/v1/work_items", json={"title": "Task B"}, headers=headers)
        res_c = await client.post("/api/v1/work_items", json={"title": "Task C"}, headers=headers)
        id_a = res_a.json()["id"]
        id_b = res_b.json()["id"]
        id_c = res_c.json()["id"]

        # 1. Edge 1: A -> B (A is predecessor to B)
        res_dep1 = await client.post(
            f"/api/v1/work_items/{id_b}/dependencies",
            json={"predecessor_id": id_a, "dependency_type": "finish_to_start"},
            headers=headers,
        )
        assert res_dep1.status_code == 201, res_dep1.text

        # 2. Edge 2: B -> C (B is predecessor to C)
        res_dep2 = await client.post(
            f"/api/v1/work_items/{id_c}/dependencies",
            json={"predecessor_id": id_b, "dependency_type": "finish_to_start"},
            headers=headers,
        )
        assert res_dep2.status_code == 201, res_dep2.text

        # 3. Edge 3 (Cycle attempt): C -> A (C is predecessor to A) -> Circular!
        res_cycle = await client.post(
            f"/api/v1/work_items/{id_a}/dependencies",
            json={"predecessor_id": id_c, "dependency_type": "finish_to_start"},
            headers=headers,
        )
        assert res_cycle.status_code == 400
        assert "Circular dependency detected" in res_cycle.text

        # 4. Self-loop attempt: A -> A
        res_self = await client.post(
            f"/api/v1/work_items/{id_a}/dependencies",
            json={"predecessor_id": id_a, "dependency_type": "finish_to_start"},
            headers=headers,
        )
        assert res_self.status_code == 400


@pytest.mark.asyncio
async def test_kanban_stage_transition_and_auto_close(db_session: AsyncSession):
    """Verify stage transitions and automatic closed flag synchronization."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Kanban Co", code=f"KB_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        user_name = f"kb_u_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_name}@test.com", "username": user_name, "password": "Password123!", "full_name": "KB User", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_name, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 1. Create stages
        res_s1 = await client.post(
            "/api/v1/work_items/stages",
            json={"name": "In Progress", "code": "PROGRESS", "sequence": 20, "is_closed": False},
            headers=headers,
        )
        s1_id = res_s1.json()["id"]

        res_s2 = await client.post(
            "/api/v1/work_items/stages",
            json={"name": "Completed", "code": "COMPLETED", "sequence": 50, "is_closed": True},
            headers=headers,
        )
        s2_id = res_s2.json()["id"]

        # 2. Create Task in "In Progress"
        res_item = await client.post(
            "/api/v1/work_items",
            json={"title": "Deliver Sprint Backlog", "stage_id": s1_id},
            headers=headers,
        )
        item_id = res_item.json()["id"]
        assert res_item.json()["is_closed"] is False

        # 3. Transition to "Completed"
        res_trans = await client.post(
            f"/api/v1/work_items/{item_id}/stage",
            json={"stage_id": s2_id},
            headers=headers,
        )
        assert res_trans.status_code == 200
        assert res_trans.json()["stage_name"] == "Completed"
        assert res_trans.json()["is_closed"] is True
