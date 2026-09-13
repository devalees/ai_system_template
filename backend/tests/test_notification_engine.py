"""Automated test suite for Multi-Channel Notification Engine."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.notification_engine.models import Notification, PushSubscription
from modules.base.notification_engine.schemas import SendNotificationRequest, PushSubscriptionCreate
from modules.base.notification_engine.service import NotificationService


@pytest.mark.asyncio
async def test_notification_dispatch_and_in_app_persistence(db_session: AsyncSession):
    """Verify in-app notification creation, unread count, and mark-as-read lifecycle."""
    company_id = uuid.uuid4()
    user_id = uuid.uuid4()

    req = SendNotificationRequest(
        recipient_id=user_id,
        title="Document Approved",
        body="Your expense report #EXP-101 has been approved.",
        notification_type="task",
        priority="high",
        action_url="/expenses/101",
        channels=["in_app"],
    )

    res = await NotificationService.send_notification(
        db=db_session,
        req=req,
        company_id=company_id,
    )
    assert res.status == "delivered"
    assert "in_app" in res.dispatched_channels
    notif_id = res.notification_id

    # Check unread count
    counts = await NotificationService.get_unread_count(db_session, user_id, company_id)
    assert counts["unread_count"] == 1
    assert counts["total_count"] == 1

    # Mark as read
    marked = await NotificationService.mark_as_read(db_session, notif_id, user_id)
    assert marked.is_read is True
    assert marked.read_at is not None

    # Verify unread count becomes 0
    counts_after = await NotificationService.get_unread_count(db_session, user_id, company_id)
    assert counts_after["unread_count"] == 0
    assert counts_after["total_count"] == 1


@pytest.mark.asyncio
async def test_notification_preferences_filtering(db_session: AsyncSession):
    """Verify user preference matrices successfully filter notifications on opt-out."""
    company_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # 1. Disable in_app notifications for 'ai_alert' type
    await NotificationService.set_user_preference(
        db=db_session,
        user_id=user_id,
        company_id=company_id,
        channel="in_app",
        notification_type="ai_alert",
        is_enabled=False,
    )

    # 2. Attempt dispatch
    req = SendNotificationRequest(
        recipient_id=user_id,
        title="Anomaly Detected",
        body="Agent detected high margin drop.",
        notification_type="ai_alert",
        channels=["in_app"],
    )
    res = await NotificationService.send_notification(
        db=db_session,
        req=req,
        company_id=company_id,
    )
    assert res.status == "filtered_by_preferences"
    assert len(res.dispatched_channels) == 0

    # Unread count should remain 0
    counts = await NotificationService.get_unread_count(db_session, user_id, company_id)
    assert counts["unread_count"] == 0


@pytest.mark.asyncio
async def test_push_subscription_lifecycle(db_session: AsyncSession):
    """Verify registering and storing WebPush (VAPID) client device subscription."""
    company_id = uuid.uuid4()
    user_id = uuid.uuid4()

    sub_in = PushSubscriptionCreate(
        endpoint="https://fcm.googleapis.com/fcm/send/token123",
        p256dh="key_p256dh_sample",
        auth="key_auth_sample",
        user_agent="Chrome 120",
    )

    sub = await NotificationService.register_push_subscription(
        db=db_session,
        user_id=user_id,
        company_id=company_id,
        sub_in=sub_in,
    )
    assert sub.id is not None
    assert sub.endpoint == "https://fcm.googleapis.com/fcm/send/token123"


@pytest.mark.asyncio
async def test_notification_api_endpoints_and_tenant_isolation(db_session: AsyncSession):
    """Verify REST endpoints for notifications, badge counts, and multi-tenant isolation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Register Tenant A
        company_a = uuid.uuid4()
        user_a = f"notif_a_{uuid.uuid4().hex[:6]}"
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
        user_a_id = login_a.json()["user"]["id"]
        headers_a = {
            "Authorization": f"Bearer {token_a}",
            "X-Company-ID": str(company_a),
        }

        # 2. Register Tenant B
        company_b = uuid.uuid4()
        user_b = f"notif_b_{uuid.uuid4().hex[:6]}"
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

        # 3. Tenant A sends notification to self
        send_res = await client.post(
            "/api/v1/notification_engine/send",
            headers=headers_a,
            json={
                "recipient_id": user_a_id,
                "title": "Welcome Notification",
                "body": "Welcome to the sovereign platform!",
                "notification_type": "info",
                "channels": ["in_app"],
            },
        )
        assert send_res.status_code == 201
        notif_id = send_res.json()["notification_id"]

        # 4. Tenant A checks unread count and list
        badge_res = await client.get("/api/v1/notification_engine/unread-count", headers=headers_a)
        assert badge_res.status_code == 200
        assert badge_res.json()["unread_count"] == 1

        list_res = await client.get("/api/v1/notification_engine/notifications", headers=headers_a)
        assert list_res.status_code == 200
        assert len(list_res.json()) == 1
        assert list_res.json()[0]["id"] == notif_id

        # 5. Tenant A marks notification read
        mark_res = await client.patch(
            f"/api/v1/notification_engine/notifications/{notif_id}/read",
            headers=headers_a,
        )
        assert mark_res.status_code == 200
        assert mark_res.json()["is_read"] is True

        # 6. Tenant B isolation verification
        # Tenant B has 0 notifications and 0 unread
        b_badge = await client.get("/api/v1/notification_engine/unread-count", headers=headers_b)
        assert b_badge.status_code == 200
        assert b_badge.json()["unread_count"] == 0

        b_list = await client.get("/api/v1/notification_engine/notifications", headers=headers_b)
        assert b_list.status_code == 200
        assert len(b_list.json()) == 0

        # Tenant B cannot mark Tenant A's notification read
        b_mark = await client.patch(
            f"/api/v1/notification_engine/notifications/{notif_id}/read",
            headers=headers_b,
        )
        assert b_mark.status_code == 404
