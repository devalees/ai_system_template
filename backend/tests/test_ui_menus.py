"""Comprehensive automated tests for Hierarchical Navigation Menu Engine (`MenuItem`)."""

import uuid
import pytest
from sqlalchemy import select
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company, User, Permission, UserPermissionLink
from modules.base.settings.service import SettingsService
from modules.base.ui_schema.models import MenuItem
from modules.base.ui_schema.service import UISchemaService
from modules.base.ui_schema.schemas import (
    MenuItemCreate,
    MenuItemUpdate,
    MenuItemNode,
)
from modules.base.ui_schema.fixtures import seed_system_default_menus


@pytest.mark.asyncio
async def test_system_menus_seeding_and_hierarchy(db_session: AsyncSession):
    """Verify built-in system menu seeding and recursive tree structure."""
    comp_id = uuid.uuid4()
    db_session.add(Company(id=comp_id, name="Menu Test Co", code=f"MTC_{comp_id.hex[:4]}"))
    
    admin = User(
        id=uuid.uuid4(),
        username=f"menu_admin_{uuid.uuid4().hex[:6]}",
        email=f"admin_{uuid.uuid4().hex[:6]}@test.com",
        hashed_password="hash",
        full_name="Test User",
        company_id=comp_id,
        is_superuser=True,
    )
    db_session.add(admin)
    await db_session.commit()

    # Seed system menus
    await seed_system_default_menus(db_session)

    # Fetch user menu tree
    roots = await UISchemaService.get_user_menu_tree(user=admin, db=db_session, company_id=comp_id)
    assert len(roots) >= 4

    root_codes = [r.code for r in roots]
    assert "sales.root" in root_codes
    assert "purchases.root" in root_codes
    assert "accounting.root" in root_codes
    assert "settings.root" in root_codes

    # Verify sequence order (Sales=10, Purchases=20, Accounting=30, Settings=100)
    sales_node = next(r for r in roots if r.code == "sales.root")
    purchases_node = next(r for r in roots if r.code == "purchases.root")
    accounting_node = next(r for r in roots if r.code == "accounting.root")
    settings_node = next(r for r in roots if r.code == "settings.root")

    assert sales_node.sequence < purchases_node.sequence
    assert purchases_node.sequence < accounting_node.sequence
    assert accounting_node.sequence < settings_node.sequence

    # Verify Sales child categories
    sales_cat_codes = [c.code for c in sales_node.children]
    assert "sales.orders_cat" in sales_cat_codes
    assert "sales.products_cat" in sales_cat_codes
    assert "sales.reporting_cat" in sales_cat_codes

    # Verify Orders category leaf items
    orders_cat = next(c for c in sales_node.children if c.code == "sales.orders_cat")
    leaf_codes = [l.code for l in orders_cat.children]
    assert "sales.quotations" in leaf_codes
    assert "sales.orders" in leaf_codes
    assert "sales.customers" in leaf_codes

    # Verify Quotations leaf details
    quotations_item = next(l for l in orders_cat.children if l.code == "sales.quotations")
    assert quotations_item.name == "Quotations"
    assert quotations_item.res_model == "SaleOrder"
    assert quotations_item.default_view == "list"
    assert quotations_item.route_path == "/sales/quotations"
    assert quotations_item.domain_filter == {"state": "draft"}


@pytest.mark.asyncio
async def test_menu_domain_filters_and_routing(db_session: AsyncSession):
    """Verify predefined domain filters and route paths across modules."""
    comp_id = uuid.uuid4()
    db_session.add(Company(id=comp_id, name="Domain Filter Co", code=f"DFC_{comp_id.hex[:4]}"))
    admin = User(
        id=uuid.uuid4(),
        username=f"filter_admin_{uuid.uuid4().hex[:6]}",
        email=f"filter_{uuid.uuid4().hex[:6]}@test.com",
        hashed_password="hash",
        full_name="Test User",
        company_id=comp_id,
        is_superuser=True,
    )
    db_session.add(admin)
    await db_session.commit()

    await seed_system_default_menus(db_session)
    roots = await UISchemaService.get_user_menu_tree(user=admin, db=db_session, company_id=comp_id)

    # 1. Sales Orders: state == 'sale'
    sales_root = next(r for r in roots if r.code == "sales.root")
    orders_cat = next(c for c in sales_root.children if c.code == "sales.orders_cat")
    sale_orders_item = next(l for l in orders_cat.children if l.code == "sales.orders")
    assert sale_orders_item.domain_filter == {"state": "sale"}
    assert sale_orders_item.route_path == "/sales/orders"

    # 2. Accounting: Invoices vs Bills
    acct_root = next(r for r in roots if r.code == "accounting.root")
    cust_cat = next(c for c in acct_root.children if c.code == "accounting.customers_cat")
    inv_item = next(l for l in cust_cat.children if l.code == "accounting.invoices")
    assert inv_item.domain_filter == {"move_type": "out_invoice"}
    assert inv_item.route_path == "/accounting/invoices"

    vendor_cat = next(c for c in acct_root.children if c.code == "accounting.vendors_cat")
    bill_item = next(l for l in vendor_cat.children if l.code == "accounting.bills")
    assert bill_item.domain_filter == {"move_type": "in_invoice"}
    assert bill_item.route_path == "/accounting/bills"


@pytest.mark.asyncio
async def test_menu_rbac_and_empty_folder_pruning(db_session: AsyncSession):
    """Verify that unprivileged users have unauthorized items and empty folders pruned."""
    comp_id = uuid.uuid4()
    db_session.add(Company(id=comp_id, name="RBAC Menu Co", code=f"RMC_{comp_id.hex[:4]}"))

    standard_user = User(
        id=uuid.uuid4(),
        username=f"std_user_{uuid.uuid4().hex[:6]}",
        email=f"std_{uuid.uuid4().hex[:6]}@test.com",
        hashed_password="hash",
        full_name="Test User",
        company_id=comp_id,
        is_superuser=False,
    )
    db_session.add(standard_user)
    await db_session.commit()

    await seed_system_default_menus(db_session)

    # Standard user without settings or sales permissions
    roots = await UISchemaService.get_user_menu_tree(user=standard_user, db=db_session, company_id=comp_id)
    root_codes = [r.code for r in roots]

    # Settings must be pruned for non-admin
    assert "settings.root" not in root_codes

    # Grant read permission on SaleOrder
    perm = (await db_session.execute(
        select(Permission).where(Permission.code == "sales.sale_order.read")
    )).scalar_one_or_none()
    if not perm:
        perm = Permission(
            id=uuid.uuid4(),
            code="sales.sale_order.read",
            name="Read Sales Orders",
            module_name="sales",
            resource="sale_order",
            action="read",
        )
        db_session.add(perm)
        await db_session.commit()

    db_session.add(UserPermissionLink(user_id=standard_user.id, permission_id=perm.id, is_granted=True, company_id=comp_id))
    await db_session.commit()

    # Now Sales root should be visible with Quotations and Orders, but Customers pruned
    roots_after = await UISchemaService.get_user_menu_tree(user=standard_user, db=db_session, company_id=comp_id)
    sales_after = next((r for r in roots_after if r.code == "sales.root"), None)
    assert sales_after is not None

    orders_cat_after = next((c for c in sales_after.children if c.code == "sales.orders_cat"), None)
    assert orders_cat_after is not None
    leaf_codes_after = [l.code for l in orders_cat_after.children]
    assert "sales.quotations" in leaf_codes_after
    assert "sales.orders" in leaf_codes_after


@pytest.mark.asyncio
async def test_tenant_menu_override_and_studio_crud(db_session: AsyncSession):
    """Verify creating custom menu items and overriding system defaults per tenant."""
    comp_id = uuid.uuid4()
    db_session.add(Company(id=comp_id, name="Custom Studio Co", code=f"CSC_{comp_id.hex[:4]}"))

    admin = User(
        id=uuid.uuid4(),
        username=f"studio_admin_{uuid.uuid4().hex[:6]}",
        email=f"studio_{uuid.uuid4().hex[:6]}@test.com",
        hashed_password="hash",
        full_name="Test User",
        company_id=comp_id,
        is_superuser=True,
    )
    db_session.add(admin)
    await db_session.commit()

    await seed_system_default_menus(db_session)

    # 1. Create a custom top-level menu item
    custom_create = MenuItemCreate(
        code="custom_portal.root",
        name="Partner Portal",
        module_name="custom",
        icon="globe",
        sequence=50,
        action_type="url",
        route_path="/portal",
        company_id=comp_id,
        is_system=False,
    )
    created_item = await UISchemaService.create_menu_item(
        payload=custom_create,
        db=db_session,
        company_id=comp_id,
    )
    assert created_item.code == "custom_portal.root"
    assert created_item.name == "Partner Portal"
    assert created_item.is_system is False

    # Verify custom item appears in tree
    roots = await UISchemaService.get_user_menu_tree(user=admin, db=db_session, company_id=comp_id)
    assert any(r.code == "custom_portal.root" for r in roots)

    # 2. Customize a system menu (Tenant Override)
    # Find system 'sales.quotations'
    sys_stmt = select(MenuItem).where(MenuItem.code == "sales.quotations", MenuItem.company_id.is_(None))
    sys_quote = (await db_session.execute(sys_stmt)).scalar_one()

    # Update through service (should create a tenant-specific clone override)
    override = await UISchemaService.update_menu_item(
        menu_id=sys_quote.id,
        payload=MenuItemUpdate(name="Formal Offers"),
        db=db_session,
        company_id=comp_id,
    )
    assert override.name == "Formal Offers"
    assert override.company_id == comp_id
    assert override.is_system is False

    # Check that the tenant tree now reflects "Formal Offers"
    tenant_roots = await UISchemaService.get_user_menu_tree(user=admin, db=db_session, company_id=comp_id)
    sales_root = next(r for r in tenant_roots if r.code == "sales.root")
    orders_cat = next(c for c in sales_root.children if c.code == "sales.orders_cat")
    quote_leaf = next(l for l in orders_cat.children if l.code == "sales.quotations")
    assert quote_leaf.name == "Formal Offers"

    # 3. Soft-delete the custom item
    del_res = await UISchemaService.delete_menu_item(
        menu_id=created_item.id,
        db=db_session,
        company_id=comp_id,
        is_superuser=True,
    )
    assert del_res is True

    # Confirm it disappeared from tree
    roots_after_del = await UISchemaService.get_user_menu_tree(user=admin, db=db_session, company_id=comp_id)
    assert not any(r.code == "custom_portal.root" for r in roots_after_del)


@pytest.mark.asyncio
async def test_menu_rest_api_endpoints(db_session: AsyncSession):
    """Verify REST API /api/v1/ui/menus CRUD endpoints."""
    await seed_system_default_menus(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Menu API Corp", code=f"MAP_{comp_id.hex[:4]}"))
        await db_session.commit()

        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"menu_api_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Menu API Admin", "company_id": str(comp_id)},
        )
        u = (await db_session.execute(select(User).where(User.username == username))).scalar_one()
        u.is_superuser = True
        await db_session.commit()

        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Company-ID": str(comp_id)}

        # 1. GET /api/v1/ui/menus
        get_res = await client.get("/api/v1/ui/menus", headers=headers)
        assert get_res.status_code == 200
        tree = get_res.json()
        assert len(tree) >= 4
        codes = [item["code"] for item in tree]
        assert "sales.root" in codes
        assert "purchases.root" in codes
        assert "accounting.root" in codes
        assert "settings.root" in codes

        # 2. POST /api/v1/ui/menus (Create custom menu item)
        post_res = await client.post(
            "/api/v1/ui/menus",
            headers=headers,
            json={
                "code": "logistics.root",
                "name": "Logistics & Fleet",
                "module_name": "logistics",
                "icon": "truck",
                "sequence": 45,
                "action_type": "folder",
                "route_path": "/logistics",
            },
        )
        assert post_res.status_code == 201
        created_menu = post_res.json()
        menu_id = created_menu["id"]
        assert created_menu["code"] == "logistics.root"
        assert created_menu["name"] == "Logistics & Fleet"

        # 3. PUT /api/v1/ui/menus/{id}
        put_res = await client.put(
            f"/api/v1/ui/menus/{menu_id}",
            headers=headers,
            json={"name": "Fleet Management", "sequence": 46},
        )
        assert put_res.status_code == 200
        assert put_res.json()["name"] == "Fleet Management"

        # 4. DELETE /api/v1/ui/menus/{id}
        del_res = await client.delete(f"/api/v1/ui/menus/{menu_id}", headers=headers)
        assert del_res.status_code == 200
        assert del_res.json()["success"] is True
