"""SQLAlchemy session interceptors enforcing physical database-level record freezing."""

import logging
from typing import Dict, Any, Optional
from fastapi import status
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from core.base_models import BaseModel
from core.exceptions import PlatformException

logger = logging.getLogger("sovereign.workflows.interceptors")

_interceptor_registered = False


class RecordFrozenException(PlatformException):
    """Raised when an UPDATE or DELETE is attempted on an immutable/frozen record."""

    def __init__(
        self,
        res_model: str,
        record_id: Any,
        state: str = "frozen",
        details: Optional[Dict[str, Any]] = None,
    ):
        base_details = {
            "res_model": res_model,
            "record_id": str(record_id),
            "state": state,
        }
        if details:
            base_details.update(details)
        super().__init__(
            code="RECORD_FROZEN",
            message=f"Cannot modify or delete record '{res_model}' ({record_id}) because it is locked in frozen state '{state}'.",
            resolution_hint="The record is immutable in this workflow state. Transition it to an active editable state or execute an authorized unfreeze action.",
            details=base_details,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


def register_record_lock_interceptor() -> None:
    """Register global SQLAlchemy session hooks to prevent mutation or deletion of frozen records."""
    global _interceptor_registered
    if _interceptor_registered:
        return

    @event.listens_for(Session, "before_flush")
    def intercept_frozen_record_mutations(session: Session, flush_context, instances=None) -> None:
        # 1. Guard against updates on frozen entities
        for obj in session.dirty:
            if getattr(obj, "_allow_workflow_mutation", False):
                continue
            if not isinstance(obj, BaseModel):
                continue

            insp = inspect(obj)
            was_locked = False
            frozen_state = "frozen"

            # Check custom_fields for _is_locked flag
            cf = getattr(obj, "custom_fields", None)
            if hasattr(insp.attrs, "custom_fields"):
                cf_hist = insp.attrs.custom_fields.history
                if cf_hist.has_changes():
                    old_cf = cf_hist.deleted[0] if cf_hist.deleted else {}
                    if isinstance(old_cf, dict) and old_cf.get("_is_locked"):
                        was_locked = True
                        frozen_state = old_cf.get("_frozen_state", "frozen")
                else:
                    if isinstance(cf, dict) and cf.get("_is_locked"):
                        was_locked = True
                        frozen_state = cf.get("_frozen_state", "frozen")

            # Check explicit is_locked attribute if declared on model
            if not was_locked and hasattr(obj, "is_locked") and hasattr(insp.attrs, "is_locked"):
                lock_hist = insp.attrs.is_locked.history
                if lock_hist.has_changes():
                    was_locked = bool(lock_hist.deleted and lock_hist.deleted[0])
                else:
                    was_locked = bool(getattr(obj, "is_locked", False))
                if was_locked:
                    frozen_state = getattr(obj, "state", getattr(obj, "status", "frozen"))

            if was_locked:
                # Determine if any business fields were actually modified
                changed_columns = []
                for attr in insp.mapper.column_attrs:
                    if attr.key in ("updated_at", "updated_by_id", "version_id"):
                        continue
                    if getattr(insp.attrs, attr.key).history.has_changes():
                        changed_columns.append(attr.key)

                if changed_columns:
                    raise RecordFrozenException(
                        res_model=obj.__class__.__name__,
                        record_id=getattr(obj, "id", None),
                        state=frozen_state,
                        details={"attempted_changes": changed_columns},
                    )

        # 2. Guard against deletes on frozen entities
        for obj in session.deleted:
            if getattr(obj, "_allow_workflow_mutation", False):
                continue
            if not isinstance(obj, BaseModel):
                continue

            cf = getattr(obj, "custom_fields", None)
            was_locked = False
            frozen_state = "frozen"

            if isinstance(cf, dict) and cf.get("_is_locked"):
                was_locked = True
                frozen_state = cf.get("_frozen_state", "frozen")
            elif hasattr(obj, "is_locked") and getattr(obj, "is_locked", False):
                was_locked = True
                frozen_state = getattr(obj, "state", getattr(obj, "status", "frozen"))

            if was_locked:
                raise RecordFrozenException(
                    res_model=obj.__class__.__name__,
                    record_id=getattr(obj, "id", None),
                    state=frozen_state,
                    details={"action": "delete"},
                )

    _interceptor_registered = True
    logger.info("Registered global SQLAlchemy Workflow RecordLockInterceptor.")
