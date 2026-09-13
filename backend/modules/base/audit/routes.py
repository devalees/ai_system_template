"""API Routes for Immutable Audit Trail Exploration."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from modules.base.identity_rbac.dependencies import get_current_user
from modules.base.identity_rbac.models import User
from modules.base.audit.models import AuditLog
from modules.base.audit.schemas import AuditLogRead
from modules.base.audit.service import AuditService

router = APIRouter()


@router.get(
    "/",
    response_model=List[AuditLogRead],
    tags=["Audit Trail"],
    summary="Query audit logs for the active tenant company",
)
async def list_audit_logs(
    model_name: Optional[str] = Query(None, description="Filter by target model name"),
    record_id: Optional[uuid.UUID] = Query(None, description="Filter by record ID"),
    actor_id: Optional[uuid.UUID] = Query(None, description="Filter by actor user/agent ID"),
    action: Optional[str] = Query(None, description="Filter by action (CREATE, UPDATE, DELETE, RESTORE)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[AuditLog]:
    """Query chronological audit log entries scoped to current tenant."""
    stmt = (
        select(AuditLog)
        .where(AuditLog.company_id == current_user.company_id)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
        .offset(offset)
    )
    if model_name:
        stmt = stmt.where(AuditLog.model_name == model_name)
    if record_id:
        stmt = stmt.where(AuditLog.record_id == record_id)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if action:
        stmt = stmt.where(AuditLog.action == action.upper())

    result = await db.execute(stmt)
    return result.scalars().all()


@router.get(
    "/entity/{model_name}/{record_id}",
    response_model=List[AuditLogRead],
    tags=["Audit Trail"],
    summary="Get complete chronological lifecycle audit trail for an entity",
)
async def get_entity_audit_trail(
    model_name: str,
    record_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[AuditLog]:
    """Retrieve full history of modifications for a single business entity."""
    return await AuditService.get_record_trail(
        db=db,
        model_name=model_name,
        record_id=record_id,
        company_id=current_user.company_id,
    )
