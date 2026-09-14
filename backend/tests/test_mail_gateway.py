"""Automated test suite for Mail Gateway, Jinja2 template rendering, and async mail pipeline."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company
from modules.base.mail_gateway.models import MailServer, MailTemplate, MailQueue
from modules.base.mail_gateway.schemas import SendMailRequest
from modules.base.mail_gateway.service import MailService


@pytest.mark.asyncio
async def test_mail_template_jinja2_rendering(db_session: AsyncSession):
    """Verify Jinja2 template rendering for subject, HTML body, and plaintext."""
    company_id = uuid.uuid4()
    
    # 1. Direct string rendering
    rendered = MailService.render_string(
        "Hello {{ name }}, your balance is ${{ balance }}.",
        {"name": "Alice", "balance": "1,250"},
    )
    assert rendered == "Hello Alice, your balance is $1,250."

    # 2. Template model rendering
    template = MailTemplate(
        company_id=company_id,
        name="Invoice Notification",
        code="inv_notify",
        subject="Invoice #{{ inv_no }} Issued",
        body_html="<p>Dear {{ client }}, amount is {{ amount }}.</p>",
        body_text="Dear {{ client }}, amount is {{ amount }}.",
    )
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)

    result = MailService.render_mail_template(
        template,
        {"inv_no": "INV-2026-001", "client": "Acme Corp", "amount": "$5,000"},
    )
    assert result.subject == "Invoice #INV-2026-001 Issued"
    assert result.body_html == "<p>Dear Acme Corp, amount is $5,000.</p>"
    assert result.body_text == "Dear Acme Corp, amount is $5,000."


@pytest.mark.asyncio
async def test_mail_server_configuration_and_mock_smtp(db_session: AsyncSession):
    """Verify SMTP server registration, default flag management, and handshake test."""
    company_id = uuid.uuid4()

    server = MailServer(
        company_id=company_id,
        name="Test Mail Server",
        smtp_host="mock",
        smtp_port=587,
        from_email="noreply@example.com",
        from_name="Test Sender",
        is_default=True,
    )
    db_session.add(server)
    await db_session.commit()
    await db_session.refresh(server)

    test_res = MailService.test_smtp_connection(server)
    assert test_res["success"] is True
    assert "simulated successfully" in test_res["message"]


@pytest.mark.asyncio
async def test_mail_queue_and_sending_pipeline(db_session: AsyncSession):
    """Verify queueing an email with template resolution and simulated dispatch."""
    company_id = uuid.uuid4()

    # 1. Setup server and template
    server = MailServer(
        company_id=company_id,
        name="Mock Outbound",
        smtp_host="mock",
        smtp_port=587,
        from_email="billing@sovereign.com",
        is_default=True,
    )
    template = MailTemplate(
        company_id=company_id,
        name="Welcome Mail",
        code="welcome_user",
        subject="Welcome {{ username }}!",
        body_html="<h1>Welcome to Sovereign, {{ username }}!</h1>",
    )
    db_session.add_all([server, template])
    await db_session.commit()

    # 2. Enqueue email
    req = SendMailRequest(
        to_email="newuser@example.com",
        template_code="welcome_user",
        context_data={"username": "David"},
        async_send=False,  # direct dispatch in test
    )

    mail_item = await MailService.enqueue_mail(
        db=db_session,
        req=req,
        company_id=company_id,
    )

    assert mail_item.id is not None
    assert mail_item.recipient_email == "newuser@example.com"
    assert mail_item.subject == "Welcome David!"
    assert mail_item.state == "sent"
    assert mail_item.sent_at is not None
    assert mail_item.attempts == 1


@pytest.mark.asyncio
async def test_mail_api_endpoints_and_tenant_isolation(db_session: AsyncSession):
    """Verify REST API routes for servers, templates, send, queue, and multi-tenant isolation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Seed test companies
        company_a = uuid.uuid4()
        company_b = uuid.uuid4()
        db_session.add_all([
            Company(id=company_a, name="Company A", code=f"CA_{company_a.hex[:4]}", allow_registration=True),
            Company(id=company_b, name="Company B", code=f"CB_{company_b.hex[:4]}", allow_registration=True),
        ])
        await db_session.commit()

        # 1. Setup Tenant A
        user_a = f"user_a_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={
                "email": f"{user_a}@example.com",
                "username": user_a,
                "password": "Password123!",
                "full_name": "Admin Tenant A",
                "company_id": str(company_a),
            },
        )
        login_a = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user_a, "password": "Password123!"},
        )
        token_a = login_a.json()["access_token"]
        headers_a = {
            "Authorization": f"Bearer {token_a}",
            "X-Company-ID": str(company_a),
        }

        # 2. Setup Tenant B
        user_b = f"user_b_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={
                "email": f"{user_b}@example.com",
                "username": user_b,
                "password": "Password123!",
                "full_name": "Admin Tenant B",
                "company_id": str(company_b),
            },
        )
        login_b = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user_b, "password": "Password123!"},
        )
        token_b = login_b.json()["access_token"]
        headers_b = {
            "Authorization": f"Bearer {token_b}",
            "X-Company-ID": str(company_b),
        }

        # 3. Tenant A creates SMTP Server
        srv_res = await client.post(
            "/api/v1/mail_gateway/servers",
            headers=headers_a,
            json={
                "name": "SendGrid Prod",
                "smtp_host": "mock",
                "smtp_port": 587,
                "from_email": "tenant_a@sovereign.com",
                "is_default": True,
            },
        )
        assert srv_res.status_code == 201
        server_id = srv_res.json()["id"]

        # 4. Tenant A tests SMTP connection
        test_res = await client.post(
            f"/api/v1/mail_gateway/servers/{server_id}/test",
            headers=headers_a,
        )
        assert test_res.status_code == 200
        assert test_res.json()["success"] is True

        # 5. Tenant A creates Template
        tmpl_res = await client.post(
            "/api/v1/mail_gateway/templates",
            headers=headers_a,
            json={
                "name": "Order Confirmation",
                "code": "order_confirmed",
                "subject": "Order #{{ order_id }} Confirmed",
                "body_html": "<p>Thank you {{ customer }} for order #{{ order_id }}.</p>",
            },
        )
        assert tmpl_res.status_code == 201
        tmpl_id = tmpl_res.json()["id"]

        # 6. Tenant A tests Template Preview
        preview_res = await client.post(
            "/api/v1/mail_gateway/templates/render",
            headers=headers_a,
            json={
                "template_code": "order_confirmed",
                "context_data": {"order_id": "ORD-99", "customer": "John Doe"},
            },
        )
        assert preview_res.status_code == 200
        assert preview_res.json()["subject"] == "Order #ORD-99 Confirmed"
        assert "<p>Thank you John Doe for order #ORD-99.</p>" in preview_res.json()["body_html"]

        # 7. Tenant A enqueues and dispatches an email
        send_res = await client.post(
            "/api/v1/mail_gateway/send",
            headers=headers_a,
            json={
                "to_email": "customer@buyer.com",
                "template_code": "order_confirmed",
                "context_data": {"order_id": "ORD-99", "customer": "John Doe"},
                "async_send": False,
            },
        )
        assert send_res.status_code == 202
        queue_id = send_res.json()["queue_id"]

        # 8. Tenant A inspects queue
        queue_res = await client.get("/api/v1/mail_gateway/queue", headers=headers_a)
        assert queue_res.status_code == 200
        items = queue_res.json()
        assert len(items) >= 1
        assert any(item["id"] == queue_id for item in items)

        # 9. Tenant B isolation verification:
        # Tenant B cannot see Tenant A's server, template, or queue items
        b_servers = await client.get("/api/v1/mail_gateway/servers", headers=headers_b)
        assert b_servers.status_code == 200
        assert len(b_servers.json()) == 0

        b_templates = await client.get("/api/v1/mail_gateway/templates", headers=headers_b)
        assert b_templates.status_code == 200
        assert len(b_templates.json()) == 0

        b_queue = await client.get("/api/v1/mail_gateway/queue", headers=headers_b)
        assert b_queue.status_code == 200
        assert len(b_queue.json()) == 0

        b_get_server = await client.get(f"/api/v1/mail_gateway/servers/{server_id}", headers=headers_b)
        assert b_get_server.status_code == 404

        b_get_tmpl = await client.get(f"/api/v1/mail_gateway/templates/{tmpl_id}", headers=headers_b)
        assert b_get_tmpl.status_code == 404
