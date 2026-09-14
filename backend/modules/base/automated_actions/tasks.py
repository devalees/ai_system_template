"""Celery background tasks for asynchronous automated action execution and time intervals."""

import uuid
import logging
import asyncio
from typing import Dict, Any, Optional
from celery_app import celery

logger = logging.getLogger("sovereign.automated_actions.tasks")


async def _async_execute_action(
    action_id: str,
    company_id: str,
    target_model: str,
    target_id: str,
    trigger_type: str,
    record_data: Dict[str, Any],
    old_record_data: Optional[Dict[str, Any]],
    diff: Optional[Dict[str, Any]],
    user_id: Optional[str],
    depth: int,
) -> Dict[str, Any]:
    """Execute action handler within an async database session."""
    from core.database import AsyncSessionLocal
    from modules.base.automated_actions.models import AutomatedAction, ActionExecutionLog, ActionExecutionStatus
    from modules.base.automated_actions.engine.registry import action_registry
    from modules.base.automated_actions.handlers.base import ActionContext
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        stmt = select(AutomatedAction).where(AutomatedAction.id == uuid.UUID(action_id))
        rule = (await db.execute(stmt)).scalar_one_or_none()
        if not rule or not rule.is_active:
            return {"status": "skipped", "reason": "Rule not found or inactive"}

        handler = action_registry.get(rule.action_type)
        if not handler:
            return {"status": "failed", "reason": f"Handler '{rule.action_type}' not found"}

        config = handler.config_schema(**(rule.action_config or {}))
        context = ActionContext(
            company_id=uuid.UUID(company_id),
            target_model=target_model,
            target_id=uuid.UUID(target_id),
            trigger_type=trigger_type,
            record=None,
            record_data=record_data,
            old_record_data=old_record_data,
            diff=diff,
            user_id=uuid.UUID(user_id) if user_id else None,
            depth=depth,
        )

        try:
            res = await handler.execute(db=db, context=context, config=config)
            return {"status": "success", "result": res}
        except Exception as exc:
            logger.error(f"Async execution failed for action {action_id}: {exc}", exc_info=True)
            raise exc


@celery.task(name="automated_actions.execute_automated_action", bind=True, max_retries=3, default_retry_delay=15)
def execute_automated_action_task(
    self,
    action_id: str,
    company_id: str,
    target_model: str,
    target_id: str,
    trigger_type: str,
    record_data: Dict[str, Any],
    old_record_data: Optional[Dict[str, Any]] = None,
    diff: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
    depth: int = 1,
) -> Dict[str, Any]:
    """Celery task executing an automated action asynchronously."""
    logger.info(f"Executing async automated action {action_id} for {target_model} {target_id}")
    try:
        return asyncio.run(
            _async_execute_action(
                action_id=action_id,
                company_id=company_id,
                target_model=target_model,
                target_id=target_id,
                trigger_type=trigger_type,
                record_data=record_data,
                old_record_data=old_record_data,
                diff=diff,
                user_id=user_id,
                depth=depth,
            )
        )
    except Exception as exc:
        logger.error(f"Task automated_actions.execute_automated_action failed: {exc}")
        raise self.retry(exc=exc)
