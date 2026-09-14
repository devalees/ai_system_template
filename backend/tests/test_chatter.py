"""Automated test suite for Chatter and Activity collaboration engine."""

import uuid
import json
import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from core.config import settings
from main import app
from modules.base.identity_rbac.models import Company
from modules.base.chatter.service import ChatterService


@pytest.mark.asyncio
async def test_chatter_service_messages_and_activities(db_session: AsyncSession):
    """Test ChatterService post message, activity scheduling, and completion."""
    company_id = uuid.uuid4()
    res_id = uuid.uuid4()
    res_model = "invoice"

    # 1. Post human comment
    msg1 = await ChatterService.post_message(
        db=db_session,
        res_model=res_model,
        res_id=res_id,
        body="Please review this invoice before sending to the client.",
        company_id=company_id,
        author_type="human",
        message_type="comment",
    )
    assert msg1.id is not None
    assert msg1.message_type == "comment"

    # 2. Post AI finding
    msg2 = await ChatterService.post_message(
        db=db_session,
        res_model=res_model,
        res_id=res_id,
        body="Automated AI Audit: VAT calculation is 100% verified.",
        company_id=company_id,
        author_type="ai_agent",
        message_type="ai_finding",
        metadata_info={"confidence": 0.99, "agent": "hermes"},
    )
    assert msg2.author_type == "ai_agent"
    assert msg2.metadata_info["confidence"] == 0.99

    # 3. Read chronological thread
    thread = await ChatterService.get_messages(
        db=db_session,
        res_model=res_model,
        res_id=res_id,
        company_id=company_id,
    )
    assert len(thread) == 2
    assert thread[0].body == "Please review this invoice before sending to the client."
    assert thread[1].message_type == "ai_finding"

    # 4. Schedule activity
    activity = await ChatterService.schedule_activity(
        db=db_session,
        res_model=res_model,
        res_id=res_id,
        summary="Call client for payment follow-up",
        company_id=company_id,
        activity_type="call",
    )
    assert activity.id is not None
    assert activity.is_completed is False

    # 5. Complete activity
    completed_act = await ChatterService.complete_activity(
        db=db_session,
        activity_id=activity.id,
        company_id=company_id,
    )
    assert completed_act.is_completed is True

    # 6. Verify activity completion logged to thread
    updated_thread = await ChatterService.get_messages(
        db=db_session,
        res_model=res_model,
        res_id=res_id,
        company_id=company_id,
    )
    assert len(updated_thread) == 3
    assert updated_thread[2].message_type == "activity"


@pytest.mark.asyncio
async def test_chatter_redis_pubsub_broadcast(db_session: AsyncSession):
    """Verify posting a chatter message broadcasts to the Redis Pub/Sub channel."""
    company_id = uuid.uuid4()
    res_id = uuid.uuid4()
    res_model = "order"
    channel = f"sovereign:chatter:{company_id}:{res_model}:{res_id}"

    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(channel)

    # Post message
    await ChatterService.post_message(
        db=db_session,
        res_model=res_model,
        res_id=res_id,
        body="Real-time Redis broadcast message test.",
        company_id=company_id,
    )

    # Receive from pubsub
    received_message = None
    for _ in range(10):
        msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
        if msg and msg["type"] == "message":
            received_message = json.loads(msg["data"])
            break
        await asyncio.sleep(0.1)

    await pubsub.unsubscribe(channel)
    await pubsub.aclose()
    await r.aclose()

    assert received_message is not None
    assert received_message["body"] == "Real-time Redis broadcast message test."
    assert received_message["res_model"] == "order"


@pytest.mark.asyncio
async def test_chatter_api_endpoints_and_isolation(db_session: AsyncSession):
    """Verify HTTP endpoints and strict tenant isolation on chatter threads."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Seed test companies
        company_a = uuid.uuid4()
        company_b = uuid.uuid4()
        db_session.add_all([
            Company(id=company_a, name="Company A", code=f"CA_{company_a.hex[:4]}", allow_registration=True),
            Company(id=company_b, name="Company B", code=f"CB_{company_b.hex[:4]}", allow_registration=True),
        ])
        await db_session.commit()

        # 1. Register Tenant A
        user_a = f"chatter_a_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={
                "email": f"{user_a}@test.com",
                "username": user_a,
                "password": "Password123!",
                "full_name": "Tenant A Chatter",
                "company_id": str(company_a),
            },
        )
        login_a = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user_a, "password": "Password123!"},
        )
        headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

        # 2. Register Tenant B
        user_b = f"chatter_b_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={
                "email": f"{user_b}@test.com",
                "username": user_b,
                "password": "Password123!",
                "full_name": "Tenant B Chatter",
                "company_id": str(company_b),
            },
        )
        login_b = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user_b, "password": "Password123!"},
        )
        headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

        target_res_id = uuid.uuid4()

        # 3. Tenant A posts message
        res_post_a = await client.post(
            f"/api/v1/chatter/project/{target_res_id}/messages",
            headers=headers_a,
            json={"body": "Confidential project update for Tenant A.", "message_type": "comment"},
        )
        assert res_post_a.status_code == 201
        assert res_post_a.json()["body"] == "Confidential project update for Tenant A."

        # 4. Tenant A schedules activity
        res_act_a = await client.post(
            f"/api/v1/chatter/project/{target_res_id}/activities",
            headers=headers_a,
            json={"summary": "Deploy Phase 1 release", "activity_type": "review"},
        )
        assert res_act_a.status_code == 201

        # 5. Tenant A reads messages
        res_msgs_a = await client.get(f"/api/v1/chatter/project/{target_res_id}/messages", headers=headers_a)
        assert res_msgs_a.status_code == 200
        assert len(res_msgs_a.json()) == 1

        # 6. Tenant B attempts to read same project messages -> must be empty (isolated)
        res_msgs_b = await client.get(f"/api/v1/chatter/project/{target_res_id}/messages", headers=headers_b)
        assert res_msgs_b.status_code == 200
        assert len(res_msgs_b.json()) == 0

        # 7. Tenant B attempts to read same project activities -> must be empty (isolated)
        res_act_b = await client.get(f"/api/v1/chatter/project/{target_res_id}/activities", headers=headers_b)
        assert res_act_b.status_code == 200
        assert len(res_act_b.json()) == 0
