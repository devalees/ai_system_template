"""Central dispatcher matching events to automated action rules, evaluating conditions, and coordinating execution."""

import time
import uuid
import logging
from contextvars import ContextVar
from typing import Optional, Dict, Any, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.base.automated_actions.models import (
    AutomatedAction,
    ActionExecutionLog,
    TriggerType,
    ExecutionMode,
    ActionExecutionStatus,
)
from modules.base.automated_actions.engine.evaluator import ASTConditionEvaluator
from modules.base.automated_actions.engine.registry import action_registry
from modules.base.automated_actions.handlers.base import ActionContext

logger = logging.getLogger("sovereign.automated_actions.dispatcher")

# Context variable tracking cascading depth per async execution context
current_depth_var: ContextVar[int] = ContextVar("tca_current_depth", default=0)


class TCADispatcher:
    """Coordinates event observation, rule matching, AST evaluation, and action execution."""

    @classmethod
    async def dispatch_event(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        target_model: str,
        target_id: uuid.UUID,
        record: Any,
        trigger_type: str,
        record_data: Dict[str, Any],
        old_record_data: Optional[Dict[str, Any]] = None,
        diff: Optional[Dict[str, Any]] = None,
        user_id: Optional[uuid.UUID] = None,
        max_depth: int = 5,
    ) -> List[Dict[str, Any]]:
        """Find matching automated action rules and execute or enqueue them."""
        # 1. Depth check to prevent infinite recursive triggers
        depth = current_depth_var.get()
        if depth >= max_depth:
            logger.warning(f"TCA depth limit ({max_depth}) reached for {target_model} {target_id}. Halting cascade.")
            return [{"status": "depth_limit_exceeded", "depth": depth}]

        # 2. Query active rules for this tenant, model, and trigger type
        stmt = (
            select(AutomatedAction)
            .where(
                AutomatedAction.company_id == company_id,
                AutomatedAction.target_model.ilike(target_model),
                AutomatedAction.trigger_type == trigger_type,
                AutomatedAction.is_active == True,
            )
            .order_by(AutomatedAction.sequence.asc())
        )
        actions = (await db.execute(stmt)).scalars().all()
        if not actions:
            return []

        results = []
        token = current_depth_var.set(depth + 1)
        try:
            for rule in actions:
                res = await cls._process_single_rule(
                    db=db,
                    rule=rule,
                    company_id=company_id,
                    target_model=target_model,
                    target_id=target_id,
                    record=record,
                    trigger_type=trigger_type,
                    record_data=record_data,
                    old_record_data=old_record_data,
                    diff=diff,
                    user_id=user_id,
                    depth=depth + 1,
                )
                results.append(res)
        finally:
            current_depth_var.reset(token)

        return results

    @classmethod
    async def _process_single_rule(
        cls,
        db: AsyncSession,
        rule: AutomatedAction,
        company_id: uuid.UUID,
        target_model: str,
        target_id: uuid.UUID,
        record: Any,
        trigger_type: str,
        record_data: Dict[str, Any],
        old_record_data: Optional[Dict[str, Any]],
        diff: Optional[Dict[str, Any]],
        user_id: Optional[uuid.UUID],
        depth: int,
    ) -> Dict[str, Any]:
        """Evaluate conditions and execute or enqueue a single matched rule."""
        start_time = time.perf_counter()

        # 1. Watched fields check for ON_UPDATE
        if trigger_type == TriggerType.ON_UPDATE.value and rule.watched_fields:
            changed_fields = set((diff or {}).keys())
            watched = set(rule.watched_fields)
            if not changed_fields.intersection(watched):
                return {"rule_id": str(rule.id), "status": "skipped", "reason": "No watched fields changed"}

        # 2. Condition evaluation
        condition_matched = ASTConditionEvaluator.evaluate(
            condition_tree=rule.condition_tree,
            record_data=record_data,
            old_record_data=old_record_data,
            diff=diff,
        )

        if not condition_matched:
            return {"rule_id": str(rule.id), "status": "skipped", "reason": "Condition not matched"}

        # 3. Retrieve action handler
        handler = action_registry.get(rule.action_type)
        if not handler:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            await cls._record_log(
                db=db,
                company_id=company_id,
                action_id=rule.id,
                action_name=rule.name,
                target_model=target_model,
                target_id=target_id,
                trigger_type=trigger_type,
                condition_matched=True,
                status=ActionExecutionStatus.FAILED.value,
                duration_ms=duration_ms,
                error_message=f"Action handler '{rule.action_type}' not found in registry",
            )
            return {"rule_id": str(rule.id), "status": "failed", "reason": "Handler not found"}

        # 4. Parse action config
        try:
            config = handler.config_schema(**(rule.action_config or {}))
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            await cls._record_log(
                db=db,
                company_id=company_id,
                action_id=rule.id,
                action_name=rule.name,
                target_model=target_model,
                target_id=target_id,
                trigger_type=trigger_type,
                condition_matched=True,
                status=ActionExecutionStatus.FAILED.value,
                duration_ms=duration_ms,
                error_message=f"Invalid action config: {str(exc)}",
            )
            return {"rule_id": str(rule.id), "status": "failed", "reason": f"Config error: {exc}"}

        # 5. Build action context
        context = ActionContext(
            company_id=company_id,
            target_model=target_model,
            target_id=target_id,
            trigger_type=trigger_type,
            record=record,
            record_data=record_data,
            old_record_data=old_record_data,
            diff=diff,
            user_id=user_id,
            depth=depth,
        )

        # 6. Dispatch execution: SYNC or ASYNC_CELERY
        if rule.execution_mode == ExecutionMode.ASYNC_CELERY.value:
            try:
                from modules.base.automated_actions.tasks import execute_automated_action_task
                task_res = execute_automated_action_task.delay(
                    action_id=str(rule.id),
                    company_id=str(company_id),
                    target_model=target_model,
                    target_id=str(target_id),
                    trigger_type=trigger_type,
                    record_data=record_data,
                    old_record_data=old_record_data,
                    diff=diff,
                    user_id=str(user_id) if user_id else None,
                    depth=depth,
                )
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                await cls._record_log(
                    db=db,
                    company_id=company_id,
                    action_id=rule.id,
                    action_name=rule.name,
                    target_model=target_model,
                    target_id=target_id,
                    trigger_type=trigger_type,
                    condition_matched=True,
                    status=ActionExecutionStatus.SUCCESS.value,
                    duration_ms=duration_ms,
                    execution_context={"celery_task_id": task_res.id, "mode": "async_celery"},
                )
                return {"rule_id": str(rule.id), "status": "enqueued", "task_id": task_res.id}
            except Exception as exc:
                logger.warning(f"Failed to enqueue Celery task, falling back to synchronous execution: {exc}")
                # Fallback to sync execution if Celery unavailable during tests

        # Synchronous execution
        try:
            handler_result = await handler.execute(db=db, context=context, config=config)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            await cls._record_log(
                db=db,
                company_id=company_id,
                action_id=rule.id,
                action_name=rule.name,
                target_model=target_model,
                target_id=target_id,
                trigger_type=trigger_type,
                condition_matched=True,
                status=ActionExecutionStatus.SUCCESS.value,
                duration_ms=duration_ms,
                execution_context={"result": handler_result, "mode": "sync"},
            )
            return {"rule_id": str(rule.id), "status": "executed", "result": handler_result}
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"Action handler execution failed for rule '{rule.name}': {exc}", exc_info=True)
            await cls._record_log(
                db=db,
                company_id=company_id,
                action_id=rule.id,
                action_name=rule.name,
                target_model=target_model,
                target_id=target_id,
                trigger_type=trigger_type,
                condition_matched=True,
                status=ActionExecutionStatus.FAILED.value,
                duration_ms=duration_ms,
                error_message=str(exc),
            )
            return {"rule_id": str(rule.id), "status": "failed", "error": str(exc)}

    @classmethod
    async def _record_log(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        action_id: Optional[uuid.UUID],
        action_name: str,
        target_model: str,
        target_id: uuid.UUID,
        trigger_type: str,
        condition_matched: bool,
        status: str,
        duration_ms: float,
        error_message: Optional[str] = None,
        execution_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Persist execution log entry."""
        try:
            log_entry = ActionExecutionLog(
                company_id=company_id,
                action_id=action_id,
                action_name=action_name,
                target_model=target_model,
                target_id=target_id,
                trigger_type=trigger_type,
                condition_matched=condition_matched,
                status=status,
                execution_duration_ms=round(duration_ms, 2),
                error_message=error_message,
                execution_context=execution_context or {},
            )
            db.add(log_entry)
            await db.commit()
        except Exception as exc:
            logger.warning(f"Failed saving ActionExecutionLog: {exc}")
