"""Comprehensive golden benchmark verification for Sovereign AI Agent Bridge & FastMCP Tool Reflection."""

import uuid
from decimal import Decimal
from datetime import datetime, date, timezone
from unittest.mock import patch, MagicMock
import pytest
from httpx import AsyncClient, ASGITransport, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company, User
from modules.base.chatter.models import MailMessage
from modules.base.automated_actions.models import AutomatedAction, ActionExecutionLog, TriggerType
from modules.base.automated_actions.engine.dispatcher import TCADispatcher
from modules.base.automated_actions.engine.registry import action_registry
from modules.base.automated_actions.handlers.ai_handler import AIAgentActionHandler, AIAgentActionConfig
from modules.base.automated_actions.handlers.base import ActionContext
from modules.base.fiscal_calendar.models import FiscalYear, FiscalPeriod
from modules.base.parties.models import Party, PartyContact
from modules.base.pricing.models import PriceList, PriceListItem
from modules.base.taxes.models import Tax
from modules.base.payments.models import PaymentTerms, PaymentTermsLine
from core.mcp_bridge.reflection import mcp_registry


@pytest.mark.asyncio
async def test_ai_agent_action_handler_execution_and_chatter_feedback(db_session: AsyncSession):
    """Verify AIAgentActionHandler executes prompt interpolation, dispatches to Hermes, and links findings to Chatter."""
    company_id = uuid.uuid4()
    company = Company(id=company_id, name="Audit Enterprise", code=f"AE_{company_id.hex[:4]}")
    user = User(
        id=uuid.uuid4(),
        company_id=company_id,
        email=f"auditor_{uuid.uuid4().hex[:6]}@sovereign.local",
        username=f"auditor_{uuid.uuid4().hex[:6]}",
        hashed_password="mock_hash",
        full_name="Auditor User",
        user_type="human",
    )
    db_session.add_all([company, user])
    await db_session.commit()

    target_id = uuid.uuid4()
    context = ActionContext(
        company_id=company_id,
        target_model="Contract",
        target_id=target_id,
        trigger_type="on_create",
        record=None,
        record_data={"title": "Master Cloud Agreement", "amount": 120000.0, "auto_renew": True},
        user_id=user.id,
    )

    config = AIAgentActionConfig(
        agent_profile="qa_auditor",
        prompt_template="Analyze contract '{{ record.title }}' for company {{ company_id }}. Amount: ${{ record.amount }}.",
        system_prompt="You are a strict compliance auditor.",
        post_to_chatter=True,
        chatter_title="🤖 Pre-Flight Contract Audit",
        tag="compliance_check",
    )

    handler = AIAgentActionHandler()

    # Mock Hermes Gateway HTTP response
    mock_resp_payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "AUDIT VERDICT: APPROVED\n\nContract amount $120,000.0 is within risk threshold. Auto-renewal notice period verified.",
                }
            }
        ],
        "usage": {"prompt_tokens": 85, "completion_tokens": 34, "total_tokens": 119},
    }

    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 200
    mock_response.is_success = True
    mock_response.json.return_value = mock_resp_payload

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await handler.execute(db=db_session, context=context, config=config)

    # 1. Verify handler execution result
    assert result["status"] == "completed"
    assert result["agent_profile"] == "qa_auditor"
    assert "AUDIT VERDICT: APPROVED" in result["agent_response"]
    assert result["usage"]["total_tokens"] == 119
    assert result["chatter_message_id"] is not None

    # 2. Verify polymorphic Chatter note was created
    stmt_msg = select(MailMessage).where(MailMessage.res_id == target_id)
    chatter_msg = (await db_session.execute(stmt_msg)).scalar_one_or_none()
    assert chatter_msg is not None
    assert chatter_msg.author_type == "ai_agent"
    assert "Pre-Flight Contract Audit" in chatter_msg.body
    assert "AUDIT VERDICT: APPROVED" in chatter_msg.body
    assert chatter_msg.metadata_info["action_type"] == "invoke_ai_agent"
    assert chatter_msg.metadata_info["agent_profile"] == "qa_auditor"


@pytest.mark.asyncio
async def test_mcp_reflection_registry_and_status_endpoint():
    """Verify FastMCP dynamic tool reflection exposes all 9 core capability tools with valid schemas."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Status endpoint
        resp_status = await client.get("/api/v1/mcp/status")
        assert resp_status.status_code == 200
        data_status = resp_status.json()
        assert data_status["status"] == "operational"
        assert data_status["total_tools"] == 9
        assert data_status["total_ai_enabled_modules"] >= 20

        expected_tools = {
            "query_records",
            "check_fiscal_period",
            "get_party_profile",
            "calculate_pricing",
            "calculate_taxes",
            "calculate_payment_terms",
            "submit_approval_request",
            "transition_workflow_state",
            "check_resource_availability",
        }
        assert set(data_status["tools"]) == expected_tools

        # 2. Tools schema endpoint
        resp_tools = await client.get("/api/v1/mcp/tools")
        assert resp_tools.status_code == 200
        data_tools = resp_tools.json()
        assert len(data_tools) == 9

        tool_names = {t["name"] for t in data_tools}
        assert tool_names == expected_tools
        for tool in data_tools:
            assert "description" in tool
            assert "parameters" in tool
            assert tool["parameters"].get("type") == "object"


@pytest.mark.asyncio
async def test_mcp_tools_execution_endpoints(db_session: AsyncSession):
    """Verify direct invocation of reflected FastMCP tools via /api/v1/mcp/execute."""
    company_id = uuid.uuid4()
    company = Company(id=company_id, name="MCP Test Co", code=f"MCP_{company_id.hex[:4]}")

    # Seed fiscal year & period
    f_year = FiscalYear(
        id=uuid.uuid4(),
        company_id=company_id,
        code="FY-2026",
        name="Fiscal Year 2026",
        date_from=date(2026, 1, 1),
        date_to=date(2026, 12, 31),
        is_closed=False,
    )
    f_period = FiscalPeriod(
        id=uuid.uuid4(),
        company_id=company_id,
        fiscal_year_id=f_year.id,
        code="2026-10",
        name="October 2026",
        date_from=date(2026, 10, 1),
        date_to=date(2026, 10, 31),
        period_type="month",
        state="open",
    )

    # Seed partner
    party = Party(
        id=uuid.uuid4(),
        company_id=company_id,
        name="Global Corp Ltd",
        legal_name="Global Corporation LLC",
        is_customer=True,
        is_vendor=False,
        tax_id="TAX-998811",
        credit_limit=Decimal("50000.00"),
    )
    contact = PartyContact(
        id=uuid.uuid4(),
        company_id=company_id,
        party_id=party.id,
        name="Jane Executive",
        email="jane@globalcorp.local",
        is_primary=True,
    )

    # Seed payment terms
    terms = PaymentTerms(
        id=uuid.uuid4(),
        company_id=company_id,
        name="30/60 Split",
        code="30-60-SPLIT",
    )
    term_line1 = PaymentTermsLine(
        company_id=company_id,
        terms_id=terms.id,
        sequence=1,
        value_type="percent",
        value=Decimal("50.0"),
        days=30,
        option="days_after_invoice",
    )
    term_line2 = PaymentTermsLine(
        company_id=company_id,
        terms_id=terms.id,
        sequence=2,
        value_type="balance",
        value=Decimal("0.0"),
        days=60,
        option="days_after_invoice",
    )

    # Seed tax
    tax = Tax(
        id=uuid.uuid4(),
        company_id=company_id,
        name="Standard VAT 15%",
        code="VAT-15",
        tax_scope="sales",
        calculation_type="percent",
        amount=Decimal("15.00"),
        is_inclusive=False,
        sequence=1,
        is_active=True,
    )

    # Seed pricing
    prod_id = uuid.uuid4()
    p_list = PriceList(
        id=uuid.uuid4(),
        company_id=company_id,
        name="Enterprise Price List",
        code="ENT-PL",
        is_active=True,
    )
    p_item = PriceListItem(
        company_id=company_id,
        price_list_id=p_list.id,
        applied_on="product",
        res_model="Product",
        res_id=prod_id,
        min_quantity=Decimal("1.0"),
        pricing_mode="fixed",
        fixed_price=Decimal("250.00"),
        sequence=1,
    )

    # Seed resource
    from modules.base.resources.models import Resource
    res_equipment = Resource(
        id=uuid.uuid4(),
        company_id=company_id,
        name="GPU Cluster Node A",
        code="GPU-NODE-A",
        resource_type="equipment",
        capacity_per_day=Decimal("24.0"),
        cost_per_hour=Decimal("5.0"),
        is_active=True,
    )

    db_session.add_all([company, f_year, f_period, party, contact, terms, term_line1, term_line2, tax, p_list, p_item, res_equipment])
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Tool 1: check_fiscal_period
        resp1 = await client.post(
            "/api/v1/mcp/execute",
            json={
                "tool": "check_fiscal_period",
                "arguments": {"date_str": "2026-10-15"},
                "company_id": str(company_id),
            },
        )
        assert resp1.status_code == 200
        res1 = resp1.json()
        assert res1["status"] == "success"
        assert res1["result"]["code"] == "2026-10"
        assert res1["result"]["is_open"] is True
        assert res1["result"]["can_post"] is True

        # Tool 2: get_party_profile
        resp2 = await client.post(
            "/api/v1/mcp/execute",
            json={
                "tool": "get_party_profile",
                "arguments": {"party_id": str(party.id)},
                "company_id": str(company_id),
            },
        )
        assert resp2.status_code == 200
        res2 = resp2.json()
        assert res2["status"] == "success"
        assert res2["result"]["name"] == "Global Corp Ltd"
        assert res2["result"]["tax_id"] == "TAX-998811"
        assert len(res2["result"]["contacts"]) == 1
        assert res2["result"]["contacts"][0]["name"] == "Jane Executive"

        # Tool 3: query_records
        resp3 = await client.post(
            "/api/v1/mcp/execute",
            json={
                "tool": "query_records",
                "arguments": {"model": "Party", "filters": {"is_customer": True}, "limit": 10},
                "company_id": str(company_id),
            },
        )
        assert resp3.status_code == 200
        res3 = resp3.json()
        assert res3["status"] == "success"
        assert res3["result"]["count"] >= 1
        assert res3["result"]["records"][0]["name"] == "Global Corp Ltd"

        # Tool 4: calculate_payment_terms
        resp4 = await client.post(
            "/api/v1/mcp/execute",
            json={
                "tool": "calculate_payment_terms",
                "arguments": {
                    "amount": 10000.0,
                    "terms_id": str(terms.id),
                    "invoice_date": "2026-10-01",
                },
                "company_id": str(company_id),
            },
        )
        assert resp4.status_code == 200
        res4 = resp4.json()
        assert res4["status"] == "success"
        assert len(res4["result"]["installments"]) == 2
        assert float(res4["result"]["installments"][0]["amount"]) == 5000.0
        assert float(res4["result"]["installments"][1]["amount"]) == 5000.0

        # Tool 5: calculate_pricing
        resp5 = await client.post(
            "/api/v1/mcp/execute",
            json={
                "tool": "calculate_pricing",
                "arguments": {
                    "price_list_id": str(p_list.id),
                    "items": [{"res_model": "Product", "res_id": str(prod_id), "quantity": 2.0, "base_price": 300.0}],
                },
                "company_id": str(company_id),
            },
        )
        assert resp5.status_code == 200
        res5 = resp5.json()
        assert res5["status"] == "success"
        assert float(res5["result"]["evaluations"][0]["unit_price"]) == 250.00


        # Tool 6: calculate_taxes
        resp6 = await client.post(
            "/api/v1/mcp/execute",
            json={
                "tool": "calculate_taxes",
                "arguments": {
                    "lines": [{"amount": 1000.0, "tax_ids": [str(tax.id)]}],
                },
                "company_id": str(company_id),
            },
        )
        assert resp6.status_code == 200
        res6 = resp6.json()
        assert res6["status"] == "success"
        assert float(res6["result"]["total_tax"]) == 150.00
        assert float(res6["result"]["total_amount"]) == 1150.00


        # Tool 7: check_resource_availability
        resp7 = await client.post(
            "/api/v1/mcp/execute",
            json={
                "tool": "check_resource_availability",
                "arguments": {
                    "resource_id": str(res_equipment.id),
                    "start_time": "2026-10-10T09:00:00Z",
                    "end_time": "2026-10-10T17:00:00Z",
                },
                "company_id": str(company_id),
            },
        )
        assert resp7.status_code == 200
        res7 = resp7.json()
        assert res7["status"] == "success"
        assert res7["result"]["is_available"] is True
        assert res7["result"]["conflicts_count"] == 0



@pytest.mark.asyncio
async def test_automated_action_tca_with_ai_agent(db_session: AsyncSession):
    """Verify end-to-end TCA pipeline triggering invoke_ai_agent on entity lifecycle events."""
    company_id = uuid.uuid4()
    company = Company(id=company_id, name="Automated AI Co", code=f"AA_{company_id.hex[:4]}")
    user = User(
        id=uuid.uuid4(),
        company_id=company_id,
        email=f"ai_ops_{uuid.uuid4().hex[:6]}@sovereign.local",
        username=f"ai_ops_{uuid.uuid4().hex[:6]}",
        hashed_password="mock_hash",
        full_name="AI Ops User",
        user_type="human",
    )

    action_rule = AutomatedAction(
        id=uuid.uuid4(),
        company_id=company_id,
        name="Auto AI Risk Audit on Contract Creation",
        target_model="Contract",
        trigger_type=TriggerType.ON_CREATE.value,
        condition_tree={"logic": "AND", "filters": [{"field": "amount", "operator": "gte", "value": 50000}]},
        action_type="invoke_ai_agent",
        action_config={
            "agent_profile": "cost_controller",
            "prompt_template": "Audit contract '{{ record.title }}' (amount: {{ record.amount }}).",
            "post_to_chatter": True,
            "chatter_title": "🤖 Spend Controller Audit",
        },
        execution_mode="sync",
        is_active=True,
    )

    db_session.add_all([company, user, action_rule])
    await db_session.commit()

    # Simulate Contract creation event
    contract_id = uuid.uuid4()
    mock_hermes_reply = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "SPEND AUDIT: APPROVED. Budget allocation verified.",
                }
            }
        ],
        "usage": {"prompt_tokens": 40, "completion_tokens": 15, "total_tokens": 55},
    }

    mock_resp = MagicMock(spec=Response)
    mock_resp.status_code = 200
    mock_resp.is_success = True
    mock_resp.json.return_value = mock_hermes_reply

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        dispatch_results = await TCADispatcher.dispatch_event(
            db=db_session,
            company_id=company_id,
            target_model="Contract",
            target_id=contract_id,
            record=None,
            trigger_type="on_create",
            record_data={"title": "High Value SLA", "amount": 75000.0},
            user_id=user.id,
        )

    assert len(dispatch_results) == 1
    assert dispatch_results[0]["status"] == "executed"

    # Verify execution log
    stmt_log = select(ActionExecutionLog).where(ActionExecutionLog.action_id == action_rule.id)
    log = (await db_session.execute(stmt_log)).scalar_one_or_none()
    assert log is not None
    assert log.status == "success"
    assert log.target_model == "Contract"

    # Verify Chatter thread
    stmt_msg = select(MailMessage).where(MailMessage.res_id == contract_id)
    msg = (await db_session.execute(stmt_msg)).scalar_one_or_none()
    assert msg is not None
    assert msg.author_type == "ai_agent"
    assert "SPEND AUDIT: APPROVED" in msg.body
