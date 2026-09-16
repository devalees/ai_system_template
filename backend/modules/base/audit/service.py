"""Audit logging service and state diff computation engine."""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy import select, inspect
from sqlalchemy.ext.asyncio import AsyncSession

from core.context import get_active_company_id, get_current_user_id, get_actor_type
from modules.base.audit.models import AuditLog


def _serialize_val(val: Any) -> Any:
    """Safely convert non-JSON serializable values like UUID and datetime to strings."""
    if isinstance(val, uuid.UUID):
        return str(val)
    if isinstance(val, datetime):
        return val.isoformat()
    return val


def compute_instance_diff(instance: Any) -> Dict[str, Dict[str, Any]]:
    """Compute field-level delta dictionary for an updated SQLAlchemy model instance."""
    state = inspect(instance)
    changes: Dict[str, Dict[str, Any]] = {}

    for prop in state.mapper.column_attrs:
        attr = state.attrs[prop.key]
        # Ignore security-sensitive or auto-managed audit timestamps
        if attr.key in ("hashed_password", "updated_at", "created_at"):
            continue

        hist = attr.load_history()
        if hist.has_changes():
            if hist.deleted:
                old_val = hist.deleted[0]
            elif attr.key in state.committed_state:
                old_val = state.committed_state[attr.key]
            else:
                old_val = None

            new_val = hist.added[0] if hist.added else getattr(instance, attr.key, None)
            changes[attr.key] = {
                "old": _serialize_val(old_val),
                "new": _serialize_val(new_val),
            }

    return changes


class AuditService:
    """Enterprise audit logger for entity lifecycle and state transitions."""

    @classmethod
    async def log_mutation(
        cls,
        db: AsyncSession,
        model_name: str,
        record_id: uuid.UUID,
        action: str,
        changes: Dict[str, Any],
        company_id: Optional[uuid.UUID] = None,
        actor_id: Optional[uuid.UUID] = None,
        actor_type: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Create and persist an immutable audit trail entry."""
        target_company_id = company_id or get_active_company_id()
        if not target_company_id:
            raise ValueError("Cannot log audit record without active company_id.")

        log_entry = AuditLog(
            company_id=target_company_id,
            actor_id=actor_id or get_current_user_id(),
            actor_type=actor_type or get_actor_type() or "human",
            model_name=model_name,
            record_id=record_id,
            action=action.upper(),
            changes=changes,
            ip_address=ip_address,
        )
        db.add(log_entry)
        await db.commit()
        await db.refresh(log_entry)
        return log_entry

    @classmethod
    async def get_record_trail(
        cls,
        db: AsyncSession,
        model_name: str,
        record_id: uuid.UUID,
        company_id: uuid.UUID,
    ) -> List[AuditLog]:
        """Fetch full chronological audit trail for a specific model record."""
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.company_id == company_id,
                AuditLog.model_name == model_name,
                AuditLog.record_id == record_id,
            )
            .order_by(AuditLog.created_at.asc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()
