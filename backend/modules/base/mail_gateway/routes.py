"""API routes for SMTP servers, email templates, rendering preview, and queued mail dispatch."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.exceptions import NotFoundException, ValidationException
from modules.base.identity_rbac.dependencies import get_current_user
from modules.base.identity_rbac.models import User
from modules.base.mail_gateway.models import MailServer, MailTemplate, MailQueue
from modules.base.mail_gateway.schemas import (
    MailServerCreate,
    MailServerUpdate,
    MailServerRead,
    ConnectionTestResponse,
    MailTemplateCreate,
    MailTemplateUpdate,
    MailTemplateRead,
    MailTemplateRenderRequest,
    MailTemplateRenderResponse,
    SendMailRequest,
    MailQueueRead,
    SendMailResponse,
)
from modules.base.mail_gateway.service import MailService

router = APIRouter()


# ==========================================
# 1. Mail Servers (SMTP Configuration)
# ==========================================

@router.get(
    "/servers",
    response_model=List[MailServerRead],
    tags=["Mail Gateway - Servers"],
    summary="List tenant SMTP outbound mail servers",
)
async def list_mail_servers(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[MailServer]:
    """Retrieve all configured outbound SMTP servers for the authenticated tenant."""
    query = select(MailServer).where(
        MailServer.company_id == current_user.company_id,
        MailServer.deleted_at.is_(None),
    )
    if is_active is not None:
        query = query.where(MailServer.is_active == is_active)

    res = await db.execute(query)
    return list(res.scalars().all())


@router.post(
    "/servers",
    response_model=MailServerRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Mail Gateway - Servers"],
    summary="Create SMTP server configuration",
)
async def create_mail_server(
    server_in: MailServerCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MailServer:
    """Register a new outbound SMTP server for the active company."""
    if server_in.is_default:
        # Unset previous default
        prev_defaults = await db.execute(
            select(MailServer).where(
                MailServer.company_id == current_user.company_id,
                MailServer.is_default == True,
            )
        )
        for prev in prev_defaults.scalars().all():
            prev.is_default = False

    server = MailServer(
        company_id=current_user.company_id,
        created_by_id=current_user.id,
        **server_in.model_dump(),
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return server


@router.get(
    "/servers/{server_id}",
    response_model=MailServerRead,
    tags=["Mail Gateway - Servers"],
    summary="Get SMTP server details",
)
async def get_mail_server(
    server_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MailServer:
    """Retrieve details for a specific outbound SMTP server configuration."""
    query = select(MailServer).where(
        MailServer.id == server_id,
        MailServer.company_id == current_user.company_id,
        MailServer.deleted_at.is_(None),
    )
    res = await db.execute(query)
    server = res.scalar_one_or_none()
    if not server:
        raise NotFoundException(f"Mail server '{server_id}' not found")
    return server


@router.patch(
    "/servers/{server_id}",
    response_model=MailServerRead,
    tags=["Mail Gateway - Servers"],
    summary="Update SMTP server configuration",
)
async def update_mail_server(
    server_id: uuid.UUID,
    server_in: MailServerUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MailServer:
    """Update fields on an existing outbound SMTP server configuration."""
    query = select(MailServer).where(
        MailServer.id == server_id,
        MailServer.company_id == current_user.company_id,
        MailServer.deleted_at.is_(None),
    )
    res = await db.execute(query)
    server = res.scalar_one_or_none()
    if not server:
        raise NotFoundException(f"Mail server '{server_id}' not found")

    update_data = server_in.model_dump(exclude_unset=True)
    if update_data.get("is_default") is True:
        prev_defaults = await db.execute(
            select(MailServer).where(
                MailServer.company_id == current_user.company_id,
                MailServer.is_default == True,
                MailServer.id != server_id,
            )
        )
        for prev in prev_defaults.scalars().all():
            prev.is_default = False

    for field, value in update_data.items():
        setattr(server, field, value)

    server.updated_by_id = current_user.id
    await db.commit()
    await db.refresh(server)
    return server


@router.delete(
    "/servers/{server_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Mail Gateway - Servers"],
    summary="Soft-delete SMTP server configuration",
)
async def delete_mail_server(
    server_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft delete an outbound SMTP configuration."""
    query = select(MailServer).where(
        MailServer.id == server_id,
        MailServer.company_id == current_user.company_id,
        MailServer.deleted_at.is_(None),
    )
    res = await db.execute(query)
    server = res.scalar_one_or_none()
    if not server:
        raise NotFoundException(f"Mail server '{server_id}' not found")

    await server.soft_delete(current_user.id)
    await db.commit()


@router.post(
    "/servers/{server_id}/test",
    response_model=ConnectionTestResponse,
    tags=["Mail Gateway - Servers"],
    summary="Test SMTP connection and authentication",
)
async def test_mail_server_connection(
    server_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectionTestResponse:
    """Test network handshake, TLS negotiation, and credentials for an SMTP configuration."""
    query = select(MailServer).where(
        MailServer.id == server_id,
        MailServer.company_id == current_user.company_id,
        MailServer.deleted_at.is_(None),
    )
    res = await db.execute(query)
    server = res.scalar_one_or_none()
    if not server:
        raise NotFoundException(f"Mail server '{server_id}' not found")

    result = MailService.test_smtp_connection(server)
    return ConnectionTestResponse(**result)


# ==========================================
# 2. Mail Templates
# ==========================================

@router.get(
    "/templates",
    response_model=List[MailTemplateRead],
    tags=["Mail Gateway - Templates"],
    summary="List email templates",
)
async def list_mail_templates(
    model_name: Optional[str] = Query(None, description="Filter by target model name"),
    language: Optional[str] = Query(None, description="Filter by language code"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[MailTemplate]:
    """List Jinja2 email templates for the authenticated tenant."""
    query = select(MailTemplate).where(
        MailTemplate.company_id == current_user.company_id,
        MailTemplate.deleted_at.is_(None),
    )
    if model_name:
        query = query.where(MailTemplate.model_name == model_name)
    if language:
        query = query.where(MailTemplate.language == language)

    res = await db.execute(query)
    return list(res.scalars().all())


@router.post(
    "/templates",
    response_model=MailTemplateRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Mail Gateway - Templates"],
    summary="Create email template",
)
async def create_mail_template(
    template_in: MailTemplateCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MailTemplate:
    """Register a new parameterized Jinja2 email template."""
    # Check duplicate code within company
    exist_check = await db.execute(
        select(MailTemplate).where(
            MailTemplate.company_id == current_user.company_id,
            MailTemplate.code == template_in.code,
            MailTemplate.deleted_at.is_(None),
        )
    )
    if exist_check.scalar_one_or_none():
        raise ValidationException(f"Template with code '{template_in.code}' already exists")

    template = MailTemplate(
        company_id=current_user.company_id,
        created_by_id=current_user.id,
        **template_in.model_dump(),
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


@router.get(
    "/templates/{template_id}",
    response_model=MailTemplateRead,
    tags=["Mail Gateway - Templates"],
    summary="Get email template details",
)
async def get_mail_template(
    template_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MailTemplate:
    """Retrieve an email template record by UUID."""
    query = select(MailTemplate).where(
        MailTemplate.id == template_id,
        MailTemplate.company_id == current_user.company_id,
        MailTemplate.deleted_at.is_(None),
    )
    res = await db.execute(query)
    template = res.scalar_one_or_none()
    if not template:
        raise NotFoundException(f"Mail template '{template_id}' not found")
    return template


@router.patch(
    "/templates/{template_id}",
    response_model=MailTemplateRead,
    tags=["Mail Gateway - Templates"],
    summary="Update email template",
)
async def update_mail_template(
    template_id: uuid.UUID,
    template_in: MailTemplateUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MailTemplate:
    """Update fields of an existing email template."""
    query = select(MailTemplate).where(
        MailTemplate.id == template_id,
        MailTemplate.company_id == current_user.company_id,
        MailTemplate.deleted_at.is_(None),
    )
    res = await db.execute(query)
    template = res.scalar_one_or_none()
    if not template:
        raise NotFoundException(f"Mail template '{template_id}' not found")

    for field, value in template_in.model_dump(exclude_unset=True).items():
        setattr(template, field, value)

    template.updated_by_id = current_user.id
    await db.commit()
    await db.refresh(template)
    return template


@router.delete(
    "/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Mail Gateway - Templates"],
    summary="Soft-delete email template",
)
async def delete_mail_template(
    template_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft delete an email template."""
    query = select(MailTemplate).where(
        MailTemplate.id == template_id,
        MailTemplate.company_id == current_user.company_id,
        MailTemplate.deleted_at.is_(None),
    )
    res = await db.execute(query)
    template = res.scalar_one_or_none()
    if not template:
        raise NotFoundException(f"Mail template '{template_id}' not found")

    await template.soft_delete(current_user.id)
    await db.commit()


@router.post(
    "/templates/render",
    response_model=MailTemplateRenderResponse,
    tags=["Mail Gateway - Templates"],
    summary="Render Jinja2 template preview with test variables",
)
async def render_mail_template_preview(
    render_req: MailTemplateRenderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MailTemplateRenderResponse:
    """Dynamically compile and preview rendered email subject and HTML using provided sample data."""
    if render_req.template_id:
        query = select(MailTemplate).where(
            MailTemplate.id == render_req.template_id,
            MailTemplate.company_id == current_user.company_id,
        )
    elif render_req.template_code:
        query = select(MailTemplate).where(
            MailTemplate.code == render_req.template_code,
            MailTemplate.company_id == current_user.company_id,
        )
    else:
        raise ValidationException("Either template_id or template_code must be provided")

    res = await db.execute(query)
    template = res.scalar_one_or_none()
    if not template:
        raise NotFoundException("Specified email template not found")

    return MailService.render_mail_template(template, render_req.context_data)


# ==========================================
# 3. Email Sending & Queue Pipeline
# ==========================================

@router.post(
    "/send",
    response_model=SendMailResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Mail Gateway - Pipeline"],
    summary="Enqueue and dispatch outbound email",
)
async def send_mail(
    mail_req: SendMailRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SendMailResponse:
    """Enqueue an outbound email with Jinja2 rendering and asynchronous Celery background transmission."""
    mail_item = await MailService.enqueue_mail(
        db=db,
        req=mail_req,
        company_id=current_user.company_id,
        user_id=current_user.id,
    )
    return SendMailResponse(
        queue_id=mail_item.id,
        state=mail_item.state,
        message="Email successfully processed and enqueued for delivery",
    )


@router.get(
    "/queue",
    response_model=List[MailQueueRead],
    tags=["Mail Gateway - Pipeline"],
    summary="List outbound mail queue entries",
)
async def list_mail_queue(
    state: Optional[str] = Query(None, description="Filter by delivery state: pending, sending, sent, failed"),
    recipient: Optional[str] = Query(None, description="Filter by recipient email substring"),
    limit: int = Query(50, ge=1, le=100, description="Pagination size"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[MailQueue]:
    """List queued, sent, and failed outbound email transmissions."""
    query = (
        select(MailQueue)
        .where(MailQueue.company_id == current_user.company_id)
        .order_by(MailQueue.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if state:
        query = query.where(MailQueue.state == state)
    if recipient:
        query = query.where(MailQueue.recipient_email.ilike(f"%{recipient}%"))

    res = await db.execute(query)
    return list(res.scalars().all())


@router.get(
    "/queue/{queue_id}",
    response_model=MailQueueRead,
    tags=["Mail Gateway - Pipeline"],
    summary="Get mail queue delivery status",
)
async def get_mail_queue_item(
    queue_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MailQueue:
    """Retrieve detailed telemetry and delivery status for an enqueued email."""
    query = select(MailQueue).where(
        MailQueue.id == queue_id,
        MailQueue.company_id == current_user.company_id,
    )
    res = await db.execute(query)
    item = res.scalar_one_or_none()
    if not item:
        raise NotFoundException(f"Queue item '{queue_id}' not found")
    return item


@router.post(
    "/queue/{queue_id}/retry",
    response_model=SendMailResponse,
    tags=["Mail Gateway - Pipeline"],
    summary="Manually trigger retry for a failed email",
)
async def retry_queued_mail(
    queue_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SendMailResponse:
    """Reset attempt counter and re-dispatch delivery for a failed email."""
    query = select(MailQueue).where(
        MailQueue.id == queue_id,
        MailQueue.company_id == current_user.company_id,
    )
    res = await db.execute(query)
    item = res.scalar_one_or_none()
    if not item:
        raise NotFoundException(f"Queue item '{queue_id}' not found")

    item.state = "pending"
    item.last_error = None
    await db.commit()

    # Re-dispatch
    try:
        from modules.base.mail_gateway.tasks import send_queued_mail_task
        send_queued_mail_task.delay(str(item.id))
    except Exception:
        await MailService.process_queued_mail(db, item)

    return SendMailResponse(
        queue_id=item.id,
        state=item.state,
        message="Email retry scheduled successfully",
    )
