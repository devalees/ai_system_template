"""Unit and integration tests for Multi-Tenancy Engine, Base Models, and Soft-Delete Architecture."""

import uuid
import pytest
from sqlalchemy import String, select
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient, ASGITransport
from jose import jwt

from core.config import settings
from core.context import (
    get_active_company_id,
    set_active_company_id,
    get_current_user_id,
    set_current_user_id,
    get_actor_type,
    set_actor_type,
)
from core.base_models import BaseModel
from core.app import create_app


# Test domain model inheriting canonical BaseModel
class DummyCustomer(BaseModel):
    """Test customer entity verifying multi-tenancy, soft-delete, and custom fields."""
    __tablename__ = "test_customers"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=True)


def test_context_variables():
    """Verify thread-safe ContextVar getters and setters."""
    test_comp = uuid.uuid4()
    test_user = uuid.uuid4()

    set_active_company_id(test_comp)
    set_current_user_id(test_user)
    set_actor_type("ai_agent")

    assert get_active_company_id() == test_comp
    assert get_current_user_id() == test_user
    assert get_actor_type() == "ai_agent"

    # Reset
    set_active_company_id(None)
    set_current_user_id(None)
    set_actor_type("anonymous")


@pytest.mark.asyncio
async def test_multi_tenancy_middleware_context_extraction():
    """Verify middleware populates context from headers and JWT tokens."""
    app = create_app()

    @app.get("/test/context")
    async def get_context_snapshot():
        return {
            "company_id": str(get_active_company_id()) if get_active_company_id() else None,
            "user_id": str(get_current_user_id()) if get_current_user_id() else None,
            "actor_type": get_actor_type(),
        }

    company_uuid = uuid.uuid4()
    user_uuid = uuid.uuid4()

    # Create JWT token
    token = jwt.encode(
        {
            "sub": str(user_uuid),
            "company_id": str(company_uuid),
            "actor_type": "human",
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Bearer Token
        resp = await client.get("/test/context", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["company_id"] == str(company_uuid)
        assert data["user_id"] == str(user_uuid)
        assert data["actor_type"] == "human"

        # 2. X-Company-ID header override
        override_uuid = uuid.uuid4()
        resp2 = await client.get("/test/context", headers={"X-Company-ID": str(override_uuid)})
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["company_id"] == str(override_uuid)


@pytest.mark.asyncio
async def test_multi_tenancy_query_isolation(db_session: AsyncSession):
    """Verify queries automatically inject WHERE company_id = :active_company_id."""
    company_1 = uuid.uuid4()
    company_2 = uuid.uuid4()

    # Create records for both companies
    c1 = DummyCustomer(name="Company 1 Customer", company_id=company_1)
    c2 = DummyCustomer(name="Company 2 Customer", company_id=company_2)
    db_session.add_all([c1, c2])
    await db_session.commit()

    # Query with Company 1 context
    set_active_company_id(company_1)
    stmt1 = select(DummyCustomer)
    results1 = (await db_session.execute(stmt1)).scalars().all()
    assert len(results1) == 1
    assert results1[0].name == "Company 1 Customer"
    assert results1[0].company_id == company_1

    # Query with Company 2 context
    set_active_company_id(company_2)
    stmt2 = select(DummyCustomer)
    results2 = (await db_session.execute(stmt2)).scalars().all()
    assert len(results2) == 1
    assert results2[0].name == "Company 2 Customer"
    assert results2[0].company_id == company_2

    # Query with ignore_tenant override
    stmt_all = select(DummyCustomer).execution_options(ignore_tenant=True)
    results_all = (await db_session.execute(stmt_all)).scalars().all()
    assert len(results_all) >= 2

    # Reset
    set_active_company_id(None)


@pytest.mark.asyncio
async def test_soft_delete_lifecycle(db_session: AsyncSession):
    """Verify soft-delete query filtration, recovery, and audit tracking."""
    company_id = uuid.uuid4()
    user_id = uuid.uuid4()
    set_active_company_id(company_id)

    customer = DummyCustomer(name="Active Customer", company_id=company_id)
    db_session.add(customer)
    await db_session.commit()
    customer_id = customer.id

    # Verify normal query finds it
    cust = (await db_session.execute(select(DummyCustomer).where(DummyCustomer.id == customer_id))).scalar_one_or_none()
    assert cust is not None
    assert cust.is_deleted is False

    # Soft delete record
    cust.soft_delete(user_id=user_id)
    await db_session.commit()

    # Standard query should automatically filter out soft-deleted record
    cust_filtered = (await db_session.execute(select(DummyCustomer).where(DummyCustomer.id == customer_id))).scalar_one_or_none()
    assert cust_filtered is None  # Auto-filtered!

    # Query with include_deleted=True should return the record
    stmt = select(DummyCustomer).where(DummyCustomer.id == customer_id).execution_options(include_deleted=True)
    cust_deleted = (await db_session.execute(stmt)).scalar_one_or_none()
    assert cust_deleted is not None
    assert cust_deleted.is_deleted is True
    assert cust_deleted.deleted_by_id == user_id
    assert cust_deleted.deleted_at is not None

    # Restore record
    cust_deleted.restore()
    await db_session.commit()

    # Verify restored record is visible in standard queries again
    cust_restored = (await db_session.execute(select(DummyCustomer).where(DummyCustomer.id == customer_id))).scalar_one_or_none()
    assert cust_restored is not None
    assert cust_restored.is_deleted is False

    # Reset
    set_active_company_id(None)


@pytest.mark.asyncio
async def test_extensible_custom_fields_jsonb(db_session: AsyncSession):
    """Verify dynamic custom_fields JSONB storage, get/set helpers, and serialization."""
    company_id = uuid.uuid4()
    set_active_company_id(company_id)

    customer = DummyCustomer(
        name="VIP Customer",
        company_id=company_id,
        custom_fields={"tier": "platinum", "credit_limit": 50000},
    )
    customer.set_custom_field("assigned_agent", "bot_sales_agent")
    db_session.add(customer)
    await db_session.commit()
    cust_id = customer.id

    cust = (await db_session.execute(select(DummyCustomer).where(DummyCustomer.id == cust_id))).scalar_one()
    assert cust.get_custom_field("tier") == "platinum"
    assert cust.get_custom_field("credit_limit") == 50000
    assert cust.get_custom_field("assigned_agent") == "bot_sales_agent"
    assert cust.get_custom_field("non_existent", "default_val") == "default_val"

    # Check to_dict() serialization
    serialized = cust.to_dict()
    assert serialized["name"] == "VIP Customer"
    assert serialized["custom_fields"]["tier"] == "platinum"
    assert "id" in serialized
    assert "created_at" in serialized

    # Reset
    set_active_company_id(None)
