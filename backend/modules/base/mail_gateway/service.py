"""Business logic, Jinja2 rendering engine, and SMTP dispatcher for Mail Gateway."""

import os
import uuid
import smtplib
import time
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from jinja2 import Environment, BaseLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from core.event_bus import event_bus
from core.exceptions import NotFoundException, ValidationException
from modules.base.mail_gateway.models import MailServer, MailTemplate, MailQueue
from modules.base.mail_gateway.schemas import SendMailRequest, MailTemplateRenderResponse

logger = logging.getLogger("sovereign.mail_gateway.service")

# Jinja2 rendering environment with safe auto-escaping
jinja_env = Environment(
    loader=BaseLoader(),
    autoescape=select_autoescape(["html", "xml"]),
)


class MailService:
    """Service orchestrating email template rendering, SMTP transmission, and queue tracking."""

    @classmethod
    def render_string(cls, template_str: str, context: Dict[str, Any]) -> str:
        """Render a raw Jinja2 template string with provided context variables."""
        try:
            tmpl = jinja_env.from_string(template_str)
            return tmpl.render(**context)
        except Exception as exc:
            logger.error(f"Jinja2 rendering failure: {exc}")
            raise ValidationException(f"Template rendering error: {str(exc)}")

    @classmethod
    def render_mail_template(
        cls, template: MailTemplate, context: Dict[str, Any]
    ) -> MailTemplateRenderResponse:
        """Render a MailTemplate record's subject, body_html, and body_text."""
        rendered_subject = cls.render_string(template.subject, context)
        rendered_html = cls.render_string(template.body_html, context)
        rendered_text = (
            cls.render_string(template.body_text, context)
            if template.body_text
            else None
        )

        return MailTemplateRenderResponse(
            subject=rendered_subject,
            body_html=rendered_html,
            body_text=rendered_text,
        )

    @classmethod
    async def get_server_for_company(
        cls, db: AsyncSession, company_id: uuid.UUID, server_id: Optional[uuid.UUID] = None
    ) -> Optional[MailServer]:
        """Fetch specified server or default active server for the tenant."""
        if server_id:
            query = select(MailServer).where(
                MailServer.id == server_id,
                MailServer.company_id == company_id,
                MailServer.is_active == True,
            )
            result = await db.execute(query)
            return result.scalar_one_or_none()

        # Fallback to default server
        query = select(MailServer).where(
            MailServer.company_id == company_id,
            MailServer.is_default == True,
            MailServer.is_active == True,
        )
        result = await db.execute(query)
        server = result.scalar_one_or_none()
        if server:
            return server

        # Any active server for company
        query_any = select(MailServer).where(
            MailServer.company_id == company_id,
            MailServer.is_active == True,
        ).limit(1)
        result_any = await db.execute(query_any)
        return result_any.scalar_one_or_none()

    @classmethod
    def test_smtp_connection(cls, server: MailServer) -> Dict[str, Any]:
        """Test SMTP server connectivity, TLS handshake, and authentication."""
        start_time = time.time()
        
        # Test / Mock simulation mode
        if server.smtp_host in ("mock", "localhost", "127.0.0.1", "test.mock") or os.getenv("MOCK_SMTP", "0") == "1":
            latency = round((time.time() - start_time) * 1000, 2)
            return {
                "success": True,
                "message": f"SMTP handshake simulated successfully for '{server.name}' ({server.smtp_host}:{server.smtp_port})",
                "latency_ms": latency,
            }

        try:
            if server.encryption == "ssl":
                smtp = smtplib.SMTP_SSL(server.smtp_host, server.smtp_port, timeout=10)
            else:
                smtp = smtplib.SMTP(server.smtp_host, server.smtp_port, timeout=10)
                if server.encryption == "tls":
                    smtp.starttls()

            if server.smtp_user and server.smtp_password:
                smtp.login(server.smtp_user, server.smtp_password)

            smtp.noop()
            smtp.quit()
            latency = round((time.time() - start_time) * 1000, 2)
            return {
                "success": True,
                "message": "SMTP handshake and authentication successful",
                "latency_ms": latency,
            }
        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.warning(f"SMTP connection test failed for {server.name}: {exc}")
            return {
                "success": False,
                "message": f"SMTP connection failed: {str(exc)}",
                "latency_ms": latency,
            }

    @classmethod
    async def enqueue_mail(
        cls,
        db: AsyncSession,
        req: SendMailRequest,
        company_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> MailQueue:
        """Create a mail queue item and dispatch asynchronously via Celery or directly."""
        subject = req.subject
        body_html = req.body_html
        body_text = req.body_text
        template_id = req.template_id

        # Resolve template if specified
        if req.template_code or req.template_id:
            if req.template_id:
                stmt = select(MailTemplate).where(
                    MailTemplate.id == req.template_id,
                    MailTemplate.company_id == company_id,
                )
            else:
                stmt = select(MailTemplate).where(
                    MailTemplate.code == req.template_code,
                    MailTemplate.company_id == company_id,
                )
            res = await db.execute(stmt)
            template = res.scalar_one_or_none()
            if not template:
                raise NotFoundException(
                    f"Email template '{req.template_code or req.template_id}' not found"
                )

            rendered = cls.render_mail_template(template, req.context_data)
            subject = rendered.subject
            body_html = rendered.body_html
            body_text = rendered.body_text
            template_id = template.id

        if not subject:
            raise ValidationException("Email subject is required (or must be rendered from a template)")
        if not body_html:
            raise ValidationException("Email body_html is required (or must be rendered from a template)")

        server = await cls.get_server_for_company(db, company_id, req.server_id)
        server_id = server.id if server else None

        mail_item = MailQueue(
            company_id=company_id,
            created_by_id=user_id,
            server_id=server_id,
            template_id=template_id,
            recipient_email=req.to_email,
            recipient_name=req.recipient_name,
            cc=req.cc,
            bcc=req.bcc,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            state="pending",
            attempts=0,
            max_attempts=3,
            res_model=req.res_model,
            res_id=req.res_id,
        )
        db.add(mail_item)
        await db.commit()
        await db.refresh(mail_item)

        if req.async_send:
            try:
                from modules.base.mail_gateway.tasks import send_queued_mail_task
                send_queued_mail_task.delay(str(mail_item.id))
            except Exception as exc:
                logger.warning(
                    f"Celery dispatch failed (running in fallback synchronous mode): {exc}"
                )
                await cls.process_queued_mail(db, mail_item, server)
        else:
            await cls.process_queued_mail(db, mail_item, server)

        return mail_item

    @classmethod
    async def process_queued_mail(
        cls,
        db: AsyncSession,
        mail_item: MailQueue,
        server: Optional[MailServer] = None,
    ) -> Dict[str, Any]:
        """Dispatch a single queued email and update database status."""
        if not server:
            server = await cls.get_server_for_company(db, mail_item.company_id, mail_item.server_id)

        mail_item.attempts += 1
        mail_item.state = "sending"
        await db.commit()

        # SMTP dispatch (real or mock fallback)
        try:
            cls._send_smtp(server, mail_item)
            mail_item.state = "sent"
            mail_item.sent_at = datetime.now(timezone.utc)
            mail_item.last_error = None
            await db.commit()

            await event_bus.publish(
                "mail.sent",
                {
                    "mail_id": str(mail_item.id),
                    "company_id": str(mail_item.company_id),
                    "recipient": mail_item.recipient_email,
                    "subject": mail_item.subject,
                    "res_model": mail_item.res_model,
                    "res_id": str(mail_item.res_id) if mail_item.res_id else None,
                },
            )
            return {"status": "sent", "attempts": mail_item.attempts}
        except Exception as exc:
            logger.error(f"Failed to deliver email {mail_item.id}: {exc}", exc_info=True)
            mail_item.last_error = str(exc)
            if mail_item.attempts >= mail_item.max_attempts:
                mail_item.state = "failed"
            else:
                mail_item.state = "pending"
            await db.commit()

            await event_bus.publish(
                "mail.failed",
                {
                    "mail_id": str(mail_item.id),
                    "company_id": str(mail_item.company_id),
                    "recipient": mail_item.recipient_email,
                    "error": str(exc),
                    "state": mail_item.state,
                },
            )
            return {"status": mail_item.state, "error": str(exc), "attempts": mail_item.attempts}

    @classmethod
    def _send_smtp(cls, server: Optional[MailServer], mail_item: MailQueue) -> None:
        """Internal helper for SMTP transport or simulated mock delivery."""
        # Simulated delivery if no server configured or server is mock
        if (
            not server
            or server.smtp_host in ("mock", "test", "127.0.0.1", "test.mock")
            or os.getenv("MOCK_SMTP", "0") == "1"
        ):
            logger.info(
                f"[MOCK SMTP] Dispatched email to {mail_item.recipient_email} - Subject: {mail_item.subject}"
            )
            return

        msg = MIMEMultipart("alternative")
        from_header = (
            f"{server.from_name} <{server.from_email}>"
            if server.from_name
            else server.from_email
        )
        msg["From"] = from_header
        msg["To"] = mail_item.recipient_email
        msg["Subject"] = mail_item.subject

        if mail_item.cc:
            msg["Cc"] = mail_item.cc

        if mail_item.body_text:
            msg.attach(MIMEText(mail_item.body_text, "plain", "utf-8"))
        msg.attach(MIMEText(mail_item.body_html, "html", "utf-8"))

        recipients = [mail_item.recipient_email]
        if mail_item.cc:
            recipients.extend([x.strip() for x in mail_item.cc.split(",") if x.strip()])
        if mail_item.bcc:
            recipients.extend([x.strip() for x in mail_item.bcc.split(",") if x.strip()])

        if server.encryption == "ssl":
            smtp = smtplib.SMTP_SSL(server.smtp_host, server.smtp_port, timeout=15)
        else:
            smtp = smtplib.SMTP(server.smtp_host, server.smtp_port, timeout=15)
            if server.encryption == "tls":
                smtp.starttls()

        if server.smtp_user and server.smtp_password:
            smtp.login(server.smtp_user, server.smtp_password)

        smtp.sendmail(server.from_email, recipients, msg.as_string())
        smtp.quit()

    @classmethod
    async def process_queued_mail_by_id(cls, mail_queue_id: str) -> Dict[str, Any]:
        """Standalone helper for Celery workers with independent async session."""
        async with AsyncSessionLocal() as session:
            stmt = select(MailQueue).where(MailQueue.id == uuid.UUID(mail_queue_id))
            res = await session.execute(stmt)
            item = res.scalar_one_or_none()
            if not item:
                logger.error(f"MailQueue record {mail_queue_id} not found.")
                return {"status": "not_found", "mail_id": mail_queue_id}

            return await cls.process_queued_mail(session, item)
