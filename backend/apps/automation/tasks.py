"""
Celery Asynchronous Tasks for Automation Engine.
"""

from typing import Any, Dict, Optional
from celery import shared_task


@shared_task(bind=True, name="apps.automation.tasks.execute_rule")
def execute_automation_rule_task(
    self,
    rule_id: int,
    trigger_context: Optional[Dict[str, Any]] = None,
    trigger_source: str = "celery_async"
) -> Dict[str, Any]:
    """
    Celery task to execute an AutomationRule asynchronously with retry safety.
    """
    from .engine import AutomationEngine
    return AutomationEngine.execute_rule(
        rule_id=rule_id,
        trigger_context=trigger_context,
        trigger_source=trigger_source
    )


@shared_task(bind=True, name="apps.automation.tasks.scheduled_run")
def scheduled_automation_task(self, rule_id: int) -> Dict[str, Any]:
    """
    Celery Beat task triggered on scheduled intervals.
    """
    from .engine import AutomationEngine
    return AutomationEngine.execute_rule(
        rule_id=rule_id,
        trigger_context={"scheduled": True},
        trigger_source=f"celery_beat:rule#{rule_id}"
    )
