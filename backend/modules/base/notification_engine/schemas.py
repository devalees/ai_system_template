"""Pydantic schemas for notifications, preferences, push subscriptions, and dispatcher."""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


class NotificationRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "n0000000-0000-0000-0000-000000000001",
                "company_id": "a0000000-0000-0000-0000-000000000001",
                "recipient_id": "u0000000-0000-0000-0000-000000000001",
                "title": "New Lead Assigned",
                "body": "Lead 'Sovereign Corp' has been assigned to your sales queue.",
                "notification_type": "task",
                "priority": "normal",
                "is_read": False,
                "read_at": None,
                "action_url": "/crm/leads/l0000000-0000-0000-0000-000000000001",
                "res_model": "crm.lead",
                "res_id": "l0000000-0000-0000-0000-000000000001",
                "metadata_info": {"source": "lead_router"},
                "created_at": "2026-09-14T02:40:00Z"
            }
        }
    )

    id: uuid.UUID
    company_id: uuid.UUID
    recipient_id: uuid.UUID
    title: str
    body: str
    notification_type: str
    priority: str
    is_read: bool
    read_at: Optional[datetime]
    action_url: Optional[str]
    res_model: Optional[str]
    res_id: Optional[uuid.UUID]
    metadata_info: Dict[str, Any]
    created_at: datetime


class NotificationCountResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "unread_count": 5,
                "total_count": 42
            }
        }
    )

    unread_count: int
    total_count: int


class SendNotificationRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "recipient_id": "u0000000-0000-0000-0000-000000000001",
                "title": "System Security Alert",
                "body": "Unusual login attempt detected from new IP address.",
                "notification_type": "ai_alert",
                "priority": "urgent",
                "action_url": "/settings/security",
                "res_model": "res.users",
                "res_id": "u0000000-0000-0000-0000-000000000001",
                "metadata_info": {"ip": "192.168.1.100"},
                "channels": ["in_app", "web_push"]
            }
        }
    )

    recipient_id: uuid.UUID = Field(..., description="Target User UUID")
    title: str = Field(..., max_length=255, description="Notification header title")
    body: str = Field(..., description="Full text or markdown description")
    notification_type: str = Field("info", description="Classification: info, warning, success, danger, task, mention, ai_alert")
    priority: str = Field("normal", description="Priority level: low, normal, high, urgent")
    action_url: Optional[str] = Field(None, max_length=500, description="Deep link target URL")
    res_model: Optional[str] = Field(None, max_length=100, description="Polymorphic target record model")
    res_id: Optional[uuid.UUID] = Field(None, description="Polymorphic target record ID")
    metadata_info: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary custom payload attributes")
    channels: List[str] = Field(default_factory=lambda: ["in_app"], description="Requested delivery channels")


class SendNotificationResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "notification_id": "n0000000-0000-0000-0000-000000000001",
                "status": "delivered",
                "dispatched_channels": ["in_app", "web_push"]
            }
        }
    )

    notification_id: uuid.UUID
    status: str
    dispatched_channels: List[str]


class NotificationPreferenceRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "p0000000-0000-0000-0000-000000000001",
                "user_id": "u0000000-0000-0000-0000-000000000001",
                "channel": "email",
                "notification_type": "invoice",
                "is_enabled": True
            }
        }
    )

    id: uuid.UUID
    user_id: uuid.UUID
    channel: str
    notification_type: str
    is_enabled: bool


class NotificationPreferenceSet(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "channel": "email",
                "notification_type": "task",
                "is_enabled": False
            }
        }
    )

    channel: str = Field(..., description="Channel name: in_app, email, web_push, sms")
    notification_type: str = Field("all", description="Type: all, task, mention, invoice, alert")
    is_enabled: bool = Field(..., description="Whether delivery on this channel is enabled")


class PushSubscriptionCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "endpoint": "https://fcm.googleapis.com/fcm/send/sample_endpoint_token",
                "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QT9Q0A4APqOM89...",
                "auth": "tBHItJI5svbpez7KI4CCXg==",
                "user_agent": "Mozilla/5.0 Chrome/120.0"
            }
        }
    )

    endpoint: str = Field(..., description="Browser Push Service subscription URL")
    p256dh: str = Field(..., max_length=255, description="Client ECDH public key (P-256 curve)")
    auth: str = Field(..., max_length=255, description="Client authentication secret")
    user_agent: Optional[str] = Field(None, max_length=255, description="Client browser / device user agent")


class PushSubscriptionRead(PushSubscriptionCreate):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "sub0000-0000-0000-0000-000000000001",
                "user_id": "u0000000-0000-0000-0000-000000000001",
                "endpoint": "https://fcm.googleapis.com/fcm/send/sample_endpoint_token",
                "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QT9Q0A4APqOM89...",
                "auth": "tBHItJI5svbpez7KI4CCXg==",
                "user_agent": "Mozilla/5.0 Chrome/120.0",
                "created_at": "2026-09-14T02:42:00Z"
            }
        }
    )

    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
