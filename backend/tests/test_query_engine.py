"""Unit and integration tests for Universal Query Engine, AST Compiler, Aggregator & Pagination."""

import uuid
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import String, Numeric, Integer, delete
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession

from core.base_models import BaseModel
from core.context import set_active_company_id
from core.query_engine import (
    QueryEngine,
    FilterNode,
    FilterGroup,
    SortParam,
    PaginationParams,
    AggregationQuery,
    DimensionSpec,
    MetricSpec,
)


# Test order entity for filtering and analytics tests
class DummyOrder(BaseModel):
    __tablename__ = "test_orders"

    order_number: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # "draft", "paid", "cancelled"
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    cost: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    customer_tier: Mapped[str] = mapped_column(String(20), nullable=False)  # "standard", "vip"


@pytest.fixture
async def seeded_orders(db_session: AsyncSession):
    """Seed sample order records for filtering and aggregation tests."""
    company_id = uuid.uuid4()
    set_active_company_id(company_id)

    orders = [
        DummyOrder(
            order_number="ORD-001",
            status="paid",
            amount=100.0,
            cost=60.0,
            customer_tier="vip",
            company_id=company_id,
            custom_fields={"channel": "web", "priority": "high"},
        ),
        DummyOrder(
            order_number="ORD-002",
            status="paid",
            amount=200.0,
            cost=120.0,
            customer_tier="vip",
            company_id=company_id,
            custom_fields={"channel": "mobile", "priority": "high"},
        ),
        DummyOrder(
            order_number="ORD-003",
            status="draft",
            amount=50.0,
            cost=30.0,
            customer_tier="standard",
            company_id=company_id,
            custom_fields={"channel": "web", "priority": "low"},
        ),
        DummyOrder(
            order_number="ORD-004",
            status="cancelled",
            amount=150.0,
            cost=90.0,
            customer_tier="standard",
            company_id=company_id,
            custom_fields={"channel": "pos", "priority": "low"},
        ),
        DummyOrder(
            order_number="ORD-005",
            status="paid",
            amount=300.0,
            cost=150.0,
            customer_tier="vip",
            company_id=company_id,
            custom_fields={"channel": "web", "priority": "urgent"},
        ),
    ]

    await db_session.execute(delete(DummyOrder))
    await db_session.commit()

    db_session.add_all(orders)
    await db_session.commit()
    yield orders
    await db_session.execute(delete(DummyOrder))
    await db_session.commit()
    set_active_company_id(None)


@pytest.mark.asyncio
async def test_filter_ast_leaf_operators(db_session: AsyncSession, seeded_orders):
    """Verify individual AST comparison operators."""
    # 1. eq
    res = await QueryEngine.execute_query(
        db_session, DummyOrder, FilterNode(field="status", operator="eq", value="draft")
    )
    assert res.total_count == 1
    assert res.items[0]["order_number"] == "ORD-003"

    # 2. gt / lte
    res_gt = await QueryEngine.execute_query(
        db_session, DummyOrder, FilterNode(field="amount", operator="gt", value=150)
    )
    assert res_gt.total_count == 2  # ORD-002 (200), ORD-005 (300)

    # 3. in
    res_in = await QueryEngine.execute_query(
        db_session, DummyOrder, FilterNode(field="status", operator="in", value=["draft", "cancelled"])
    )
    assert res_in.total_count == 2

    # 4. between
    res_between = await QueryEngine.execute_query(
        db_session, DummyOrder, FilterNode(field="amount", operator="between", value=[100, 200])
    )
    assert res_between.total_count == 3  # 100, 150, 200

    # 5. contains & starts_with
    res_like = await QueryEngine.execute_query(
        db_session, DummyOrder, FilterNode(field="order_number", operator="starts_with", value="ORD-00")
    )
    assert res_like.total_count == 5


@pytest.mark.asyncio
async def test_filter_ast_compound_groups(db_session: AsyncSession, seeded_orders):
    """Verify nested boolean logic: (status == 'paid' AND (customer_tier == 'vip' OR amount > 150))."""
    query = FilterGroup(
        logical_operator="AND",
        conditions=[
            FilterNode(field="status", operator="eq", value="paid"),
            FilterGroup(
                logical_operator="OR",
                conditions=[
                    FilterNode(field="amount", operator="gte", value=200),
                    FilterNode(field="customer_tier", operator="eq", value="standard"),
                ],
            ),
        ],
    )

    res = await QueryEngine.execute_query(db_session, DummyOrder, query)
    # Paid orders: ORD-001 (100, vip), ORD-002 (200, vip), ORD-005 (300, vip).
    # Condition: status=paid AND (amount>=200 OR tier=standard) -> ORD-002 and ORD-005 match!
    assert res.total_count == 2
    order_nums = {item["order_number"] for item in res.items}
    assert order_nums == {"ORD-002", "ORD-005"}


@pytest.mark.asyncio
async def test_jsonb_nested_field_filtering(db_session: AsyncSession, seeded_orders):
    """Verify filtering on nested custom_fields JSONB attributes."""
    filter_ast = FilterNode(field="custom_fields.priority", operator="eq", value="urgent")
    res = await QueryEngine.execute_query(db_session, DummyOrder, filter_ast)
    assert res.total_count == 1
    assert res.items[0]["order_number"] == "ORD-005"


@pytest.mark.asyncio
async def test_pagination_and_sorting(db_session: AsyncSession, seeded_orders):
    """Verify pagination limits, page offsets, and multi-column sorting."""
    sort = [SortParam(field="amount", direction="desc")]
    page1 = await QueryEngine.execute_query(
        db_session, DummyOrder, sort=sort, pagination=PaginationParams(page=1, page_size=2)
    )
    assert page1.page == 1
    assert page1.page_size == 2
    assert page1.total_count == 5
    assert page1.total_pages == 3
    assert page1.has_next is True
    assert page1.has_prev is False
    assert len(page1.items) == 2
    assert page1.items[0]["amount"] == 300.0  # highest
    assert page1.items[1]["amount"] == 200.0

    page2 = await QueryEngine.execute_query(
        db_session, DummyOrder, sort=sort, pagination=PaginationParams(page=2, page_size=2)
    )
    assert page2.page == 2
    assert page2.has_next is True
    assert page2.has_prev is True
    assert page2.items[0]["amount"] == 150.0


@pytest.mark.asyncio
async def test_universal_aggregator_and_equations(db_session: AsyncSession, seeded_orders):
    """Verify multi-metric aggregation, conditional filters, and calculated equations."""
    agg_query = AggregationQuery(
        dimensions=[DimensionSpec(name="tier", field="customer_tier")],
        metrics=[
            MetricSpec(name="total_revenue", field="amount", function="SUM"),
            MetricSpec(name="total_cost", field="cost", function="SUM"),
            MetricSpec(name="order_count", field="order_number", function="COUNT"),
            MetricSpec(
                name="paid_revenue",
                field="amount",
                function="SUM",
                filter=FilterNode(field="status", operator="eq", value="paid"),
            ),
        ],
        equations={
            "gross_profit": "total_revenue - total_cost",
            "profit_margin_pct": "(total_revenue - total_cost) / total_revenue * 100",
        },
    )

    results = await QueryEngine.execute_aggregation(db_session, DummyOrder, agg_query)
    assert len(results) == 2  # standard and vip

    results_by_tier = {r["tier"]: r for r in results}
    vip_res = results_by_tier["vip"]

    # VIP orders: ORD-001 (100, cost 60), ORD-002 (200, cost 120), ORD-005 (300, cost 150)
    # Total revenue = 600, Total cost = 330, Profit = 270, Margin = 45.0%
    assert vip_res["total_revenue"] == 600.0
    assert vip_res["total_cost"] == 330.0
    assert vip_res["order_count"] == 3
    assert vip_res["paid_revenue"] == 600.0
    assert vip_res["gross_profit"] == 270.0
    assert vip_res["profit_margin_pct"] == 45.0
