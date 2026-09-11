"""
Celery Asynchronous Tasks for Centralized Automation Engine.
Unified asynchronous execution queue for all automated triggers and action pipelines.
"""

from typing import Any, Dict, Optional
from celery import shared_task


@shared_task(
    bind=True,
    name="apps.automation.tasks.execute_action",
    max_retries=3,
    default_retry_delay=5
)
def execute_automation_action_task(
    self,
    action_id: int,
    trigger_context: Optional[Dict[str, Any]] = None,
    trigger_source: str = "celery_async"
) -> Dict[str, Any]:
    """
    Celery task to execute a single AutomationAction step asynchronously.
    """
    from .engine import AutomationEngine
    return AutomationEngine.execute_action(
        action_id=action_id,
        trigger_context=trigger_context,
        trigger_source=trigger_source
    )


@shared_task(
    bind=True,
    name="apps.automation.tasks.execute_trigger",
    max_retries=3,
    default_retry_delay=5
)
def execute_automation_trigger_task(
    self,
    trigger_id: int,
    trigger_context: Optional[Dict[str, Any]] = None,
    trigger_source: str = "celery_async"
) -> Dict[str, Any]:
    """
    Celery task to evaluate an AutomationTrigger and execute its sequenced action pipeline.
    """
    from .engine import AutomationEngine
    return AutomationEngine.execute_pipeline(
        trigger_id=trigger_id,
        trigger_context=trigger_context,
        trigger_source=trigger_source
    )


# Backward-compatibility alias
execute_automation_rule_task = execute_automation_trigger_task


@shared_task(bind=True, name="apps.automation.tasks.scheduled_run")
def scheduled_automation_task(self, trigger_id: int) -> Dict[str, Any]:
    """
    Celery Beat task triggered on scheduled intervals for an AutomationTrigger.
    """
    from .engine import AutomationEngine
    return AutomationEngine.execute_pipeline(
        trigger_id=trigger_id,
        trigger_context={"scheduled": True},
        trigger_source=f"celery_beat:trigger#{trigger_id}"
    )
