"""SQLAlchemy ORM lifecycle event interceptors capturing model mutations for TCA dispatch."""

import logging
from typing import Dict, Any, Tuple
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session
from core.base_models import BaseModel

logger = logging.getLogger("sovereign.automated_actions.interceptors")

_interceptors_registered = False


def extract_instance_state(obj: Any) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Extract current state, previous state, and field diff for an ORM instance."""
    insp = inspect(obj)
    current_state: Dict[str, Any] = {}
    old_state: Dict[str, Any] = {}
    diff: Dict[str, Any] = {}

    for attr in insp.mapper.column_attrs:
        key = attr.key
        hist = getattr(insp.attrs, key).history
        current_val = getattr(obj, key, None)
        current_state[key] = current_val

        if hist.has_changes():
            old_val = hist.deleted[0] if hist.deleted else None
            old_state[key] = old_val
            diff[key] = {"old": old_val, "new": current_val}
        else:
            old_state[key] = current_val

    return current_state, old_state, diff


def register_lifecycle_interceptors() -> None:
    """Register global SQLAlchemy session hooks to capture BaseModel mutations."""
    global _interceptors_registered
    if _interceptors_registered:
        return

    @event.listens_for(Session, "after_flush")
    def capture_tca_mutations(session: Session, flush_context) -> None:
        # Check if session has TCA mutation buffer
        if not hasattr(session, "_tca_mutation_buffer"):
            session._tca_mutation_buffer = []

        # 1. Inspect new instances (ON_CREATE)
        for obj in session.new:
            if isinstance(obj, BaseModel):
                current_state, _, _ = extract_instance_state(obj)
                session._tca_mutation_buffer.append({
                    "trigger_type": "on_create",
                    "target_model": obj.__class__.__name__,
                    "target_id": getattr(obj, "id", None),
                    "company_id": getattr(obj, "company_id", None),
                    "record_data": current_state,
                    "old_record_data": None,
                    "diff": None,
                    "user_id": getattr(obj, "created_by_id", None),
                })

        # 2. Inspect dirty instances (ON_UPDATE)
        for obj in session.dirty:
            if isinstance(obj, BaseModel):
                current_state, old_state, diff = extract_instance_state(obj)
                if diff:
                    session._tca_mutation_buffer.append({
                        "trigger_type": "on_update",
                        "target_model": obj.__class__.__name__,
                        "target_id": getattr(obj, "id", None),
                        "company_id": getattr(obj, "company_id", None),
                        "record_data": current_state,
                        "old_record_data": old_state,
                        "diff": diff,
                        "user_id": getattr(obj, "updated_by_id", None),
                    })

    _interceptors_registered = True
    logger.info("Registered global SQLAlchemy TCA lifecycle interceptors.")
