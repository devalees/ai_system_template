"""Workflows & State Machine Engine module exports."""

from modules.base.workflows.interceptors import (
    register_record_lock_interceptor,
    RecordFrozenException,
)
from modules.base.workflows.models import (
    WorkflowDefinition,
    WorkflowTransition,
    WorkflowExecutionLog,
)
from modules.base.workflows.service import (
    WorkflowService,
    WorkflowTransitionException,
)

# Register database-level record lock interceptor
register_record_lock_interceptor()

__all__ = [
    "WorkflowDefinition",
    "WorkflowTransition",
    "WorkflowExecutionLog",
    "WorkflowService",
    "WorkflowTransitionException",
    "RecordFrozenException",
    "register_record_lock_interceptor",
]
