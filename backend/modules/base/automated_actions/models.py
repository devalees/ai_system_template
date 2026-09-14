"""Database models for Trigger-Condition-Action (TCA) Automated Actions and Execution Logs."""

import uuid
from enum import Enum
from typing import Optional, Dict, Any, List
from sqlalchemy import String, Text, Boolean, Integer, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.base_models import BaseModel


class TriggerType(str, Enum):
    """Supported event trigger modes for automated actions."""
    ON_CREATE = "on_create"
    ON_UPDATE = "on_update"
    ON_DELETE = "on_delete"
    ON_STATE_CHANGE = "on_state_change"
    ON_TIME_INTERVAL = "on_time_interval"
    MANUAL = "manual"


class ExecutionMode(str, Enum):
    """Execution dispatch strategies for automated actions."""
    SYNC = "sync"
    ASYNC_CELERY = "async_celery"


class ActionExecutionStatus(str, Enum):
    """Outcome status of an automated action execution."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class AutomatedAction(BaseModel):
    """Declarative Trigger-Condition-Action (TCA) automation rule."""
    __tablename__ = "automated_actions"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(50), default=TriggerType.ON_CREATE.value, nullable=False, index=True)
    watched_fields: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    condition_tree: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action_config: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(20), default=ExecutionMode.ASYNC_CELERY.value, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ActionExecutionLog(BaseModel):
    """Immutable execution history and telemetry log for an automated action run."""
    __tablename__ = "automated_action_logs"

    action_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("automated_actions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action_name: Mapped[str] = mapped_column(String(150), nullable=False)
    target_model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    condition_matched: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=ActionExecutionStatus.SUCCESS.value, nullable=False, index=True)
    execution_duration_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_context: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
