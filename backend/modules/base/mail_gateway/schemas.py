"""Pydantic schemas for SMTP servers, templates, email queue, and rendering."""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, EmailStr


class MailServerBase(BaseModel):
    name: str = Field(..., max_length=100, description="Friendly SMTP server configuration name")
    smtp_host: str = Field(..., max_length=255, description="Host address or hostname of the SMTP server")
    smtp_port: int = Field(587, ge=1, le=65535, description="Port number (e.g., 587, 465, 25)")
    smtp_user: Optional[str] = Field(None, max_length=255, description="Authentication username")
    encryption: str = Field("tls", description="Encryption standard: tls, ssl, or none")
    from_email: str = Field(..., max_length=255, description="Default Sender email address")
    from_name: Optional[str] = Field(None, max_length=255, description="Default Sender display name")
    is_default: bool = Field(False, description="Whether this is the primary server for this tenant")
    is_active: bool = Field(True, description="Operational status")


class MailServerCreate(MailServerBase):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Production SendGrid Gateway",
                "smtp_host": "smtp.sendgrid.net",
                "smtp_port": 587,
                "smtp_user": "apikey",
                "smtp_password": "SG.secret_api_key_value",
                "encryption": "tls",
                "from_email": "notifications@sovereign-erp.com",
                "from_name": "Sovereign Notifications",
                "is_default": True,
                "is_active": True
            }
        }
    )

    smtp_password: Optional[str] = Field(None, max_length=255, description="Authentication password / API key")


class MailServerUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Primary Outbound Mail Server",
                "smtp_port": 587,
                "encryption": "tls",
                "is_default": True
            }
        }
    )

    name: Optional[str] = Field(None, max_length=100)
    smtp_host: Optional[str] = Field(None, max_length=255)
    smtp_port: Optional[int] = Field(None, ge=1, le=65535)
    smtp_user: Optional[str] = Field(None, max_length=255)
    smtp_password: Optional[str] = Field(None, max_length=255)
    encryption: Optional[str] = None
    from_email: Optional[str] = Field(None, max_length=255)
    from_name: Optional[str] = Field(None, max_length=255)
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class MailServerRead(MailServerBase):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "s0000000-0000-0000-0000-000000000001",
                "company_id": "a0000000-0000-0000-0000-000000000001",
                "name": "Production SendGrid Gateway",
                "smtp_host": "smtp.sendgrid.net",
                "smtp_port": 587,
                "smtp_user": "apikey",
                "encryption": "tls",
                "from_email": "notifications@sovereign-erp.com",
                "from_name": "Sovereign Notifications",
                "is_default": True,
                "is_active": True,
                "created_at": "2026-09-14T02:00:00Z"
            }
        }
    )

    id: uuid.UUID
    company_id: uuid.UUID
    created_at: datetime


class ConnectionTestResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "SMTP handshake and authentication successful",
                "latency_ms": 42.5
            }
        }
    )

    success: bool
    message: str
    latency_ms: Optional[float] = None


class MailTemplateBase(BaseModel):
    name: str = Field(..., max_length=150, description="Template human-readable label")
    code: str = Field(..., max_length=100, description="Unique alphanumeric identifier code")
    subject: str = Field(..., max_length=255, description="Jinja2 parameterized subject line")
    body_html: str = Field(..., description="Jinja2 parameterized HTML email template")
    body_text: Optional[str] = Field(None, description="Plaintext fallback template")
    language: str = Field("en", max_length=10, description="ISO language code")
    model_name: Optional[str] = Field(None, max_length=100, description="Target entity model")
    is_active: bool = Field(True, description="Operational status")


class MailTemplateCreate(MailTemplateBase):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Invoice Due Reminder",
                "code": "invoice_due_reminder",
                "subject": "Payment Reminder: Invoice #{{ invoice_number }} for {{ company_name }}",
                "body_html": "<p>Dear {{ recipient_name }},</p><p>Invoice <strong>#{{ invoice_number }}</strong> of amount {{ amount_due }} is due on {{ due_date }}.</p>",
                "body_text": "Dear {{ recipient_name }},\n\nInvoice #{{ invoice_number }} of amount {{ amount_due }} is due on {{ due_date }}.",
                "language": "en",
                "model_name": "account.invoice",
                "is_active": True
            }
        }
    )


class MailTemplateUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Updated Invoice Due Reminder",
                "subject": "Urgent: Invoice #{{ invoice_number }} Due Soon",
                "is_active": True
            }
        }
    )

    name: Optional[str] = Field(None, max_length=150)
    code: Optional[str] = Field(None, max_length=100)
    subject: Optional[str] = Field(None, max_length=255)
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    language: Optional[str] = Field(None, max_length=10)
    model_name: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class MailTemplateRead(MailTemplateBase):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "t0000000-0000-0000-0000-000000000001",
                "company_id": "a0000000-0000-0000-0000-000000000001",
                "name": "Invoice Due Reminder",
                "code": "invoice_due_reminder",
                "subject": "Payment Reminder: Invoice #{{ invoice_number }} for {{ company_name }}",
                "body_html": "<p>Dear {{ recipient_name }},</p><p>Invoice <strong>#{{ invoice_number }}</strong> of amount {{ amount_due }} is due on {{ due_date }}.</p>",
                "body_text": "Dear {{ recipient_name }},\n\nInvoice #{{ invoice_number }} of amount {{ amount_due }} is due on {{ due_date }}.",
                "language": "en",
                "model_name": "account.invoice",
                "is_active": True,
                "created_at": "2026-09-14T02:05:00Z"
            }
        }
    )

    id: uuid.UUID
    company_id: uuid.UUID
    created_at: datetime


class MailTemplateRenderRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "template_id": "t0000000-0000-0000-0000-000000000001",
                "context_data": {
                    "recipient_name": "Sarah Connor",
                    "invoice_number": "INV-2026-089",
                    "company_name": "Cyberdyne Systems",
                    "amount_due": "$12,450.00",
                    "due_date": "2026-09-30"
                }
            }
        }
    )

    template_id: Optional[uuid.UUID] = None
    template_code: Optional[str] = None
    context_data: Dict[str, Any] = Field(default_factory=dict, description="Variables to inject into Jinja2 templates")


class MailTemplateRenderResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "subject": "Payment Reminder: Invoice #INV-2026-089 for Cyberdyne Systems",
                "body_html": "<p>Dear Sarah Connor,</p><p>Invoice <strong>#INV-2026-089</strong> of amount $12,450.00 is due on 2026-09-30.</p>",
                "body_text": "Dear Sarah Connor,\n\nInvoice #INV-2026-089 of amount $12,450.00 is due on 2026-09-30."
            }
        }
    )

    subject: str
    body_html: str
    body_text: Optional[str] = None


class SendMailRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "to_email": "billing@clientcorp.com",
                "recipient_name": "Client Accounting Team",
                "subject": "Monthly Statement - August 2026",
                "body_html": "<p>Please find your monthly statement attached.</p>",
                "template_code": "invoice_due_reminder",
                "context_data": {
                    "recipient_name": "Client Accounting Team",
                    "invoice_number": "INV-2026-089",
                    "company_name": "Client Corp",
                    "amount_due": "$12,450.00",
                    "due_date": "2026-09-30"
                },
                "res_model": "account.invoice",
                "res_id": "c0000000-0000-0000-0000-000000000001",
                "async_send": True
            }
        }
    )

    to_email: EmailStr = Field(..., description="Recipient destination email address")
    recipient_name: Optional[str] = Field(None, max_length=255)
    cc: Optional[str] = Field(None, max_length=500)
    bcc: Optional[str] = Field(None, max_length=500)
    subject: Optional[str] = Field(None, max_length=255, description="Subject (or rendered from template)")
    body_html: Optional[str] = Field(None, description="HTML body (or rendered from template)")
    body_text: Optional[str] = Field(None, description="Plain text body (or rendered from template)")
    template_code: Optional[str] = Field(None, description="Code of registered MailTemplate to render")
    template_id: Optional[uuid.UUID] = Field(None, description="UUID of registered MailTemplate to render")
    context_data: Dict[str, Any] = Field(default_factory=dict, description="Variables for template rendering")
    server_id: Optional[uuid.UUID] = Field(None, description="Specific MailServer ID or fallback to default")
    res_model: Optional[str] = Field(None, max_length=100, description="Polymorphic source entity model")
    res_id: Optional[uuid.UUID] = Field(None, description="Polymorphic source entity record UUID")
    async_send: bool = Field(True, description="Whether to enqueue in Celery or send synchronously")


class MailQueueRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "q0000000-0000-0000-0000-000000000001",
                "company_id": "a0000000-0000-0000-0000-000000000001",
                "server_id": "s0000000-0000-0000-0000-000000000001",
                "template_id": "t0000000-0000-0000-0000-000000000001",
                "recipient_email": "billing@clientcorp.com",
                "recipient_name": "Client Accounting Team",
                "subject": "Payment Reminder: Invoice #INV-2026-089 for Client Corp",
                "state": "sent",
                "attempts": 1,
                "max_attempts": 3,
                "last_error": None,
                "sent_at": "2026-09-14T02:15:30Z",
                "res_model": "account.invoice",
                "res_id": "c0000000-0000-0000-0000-000000000001",
                "created_at": "2026-09-14T02:15:28Z"
            }
        }
    )

    id: uuid.UUID
    company_id: uuid.UUID
    server_id: Optional[uuid.UUID]
    template_id: Optional[uuid.UUID]
    recipient_email: str
    recipient_name: Optional[str]
    subject: str
    state: str
    attempts: int
    max_attempts: int
    last_error: Optional[str]
    sent_at: Optional[datetime]
    res_model: Optional[str]
    res_id: Optional[uuid.UUID]
    created_at: datetime


class SendMailResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "queue_id": "q0000000-0000-0000-0000-000000000001",
                "state": "sent",
                "message": "Email dispatched successfully"
            }
        }
    )

    queue_id: uuid.UUID
    state: str
    message: str
