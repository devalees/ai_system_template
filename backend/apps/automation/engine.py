"""
Core Execution Engine & Dispatcher for Centralized Automations.
"""

import time
import traceback
from typing import Any, Dict, Optional
from django.utils import timezone
from .models import AutomationRule, AutomationLog
from .registry import ServiceRegistry


class AutomationEngine:
    """Central engine orchestrating trigger evaluation and action execution."""

    @classmethod
    def evaluate_conditions(cls, context: Dict[str, Any], conditions: Dict[str, Any]) -> bool:
        """
        Evaluates filter conditions against execution context.
        Supports exact match, booleans, and string comparisons.
        """
        if not conditions:
            return True

        for key, expected_val in conditions.items():
            actual_val = context.get(key)
            if actual_val is None and '.' in key:
                # Support nested lookup e.g. "profile.is_agent"
                parts = key.split('.')
                curr = context
                for p in parts:
                    if isinstance(curr, dict):
                        curr = curr.get(p)
                    else:
                        curr = getattr(curr, p, None)
                actual_val = curr

            # Normalize booleans/strings
            if isinstance(expected_val, bool):
                if bool(actual_val) != expected_val:
                    return False
            elif str(actual_val).lower() != str(expected_val).lower():
                return False

        return True

    @classmethod
    def execute_rule(
        cls,
        rule_id: int,
        trigger_context: Optional[Dict[str, Any]] = None,
        trigger_source: str = "manual"
    ) -> Dict[str, Any]:
        """
        Executes an AutomationRule with timing, error containment, and audit logging.
        """
        try:
            rule = AutomationRule.objects.get(id=rule_id)
        except AutomationRule.DoesNotExist:
            return {"status": "error", "error": f"Rule {rule_id} not found"}

        context = dict(trigger_context or {})
        # Merge rule action_params into context
        if rule.action_params:
            for k, v in rule.action_params.items():
                context.setdefault(k, v)

        # 1. Active & Condition Validation
        if not rule.is_active:
            return {"status": "skipped", "reason": "Rule is currently paused (is_active=False)"}

        if rule.filter_conditions and not cls.evaluate_conditions(context, rule.filter_conditions):
            return {"status": "skipped", "reason": "Trigger conditions did not match"}

        # 2. Initialize Audit Log
        log_entry = AutomationLog.objects.create(
            rule=rule,
            trigger_source=trigger_source,
            status='running',
            input_context=context,
        )

        start_time = time.time()
        output_result = {}
        error_msg = ""
        success = False

        try:
            # 3. Resolve Action Handler
            action_type = rule.action_type
            if action_type.startswith("hermes_profile:"):
                # Dynamic dispatch to specific Hermes profile
                profile_slug = action_type.removeprefix("hermes_profile:")
                from .actions import dispatch_hermes_prompt_action
                context['profile'] = profile_slug
                output_result = dispatch_hermes_prompt_action(context)
                success = output_result.get('status') != 'error'
            else:
                action_def = ServiceRegistry.get_action(action_type)
                if not action_def or not action_def.handler:
                    raise ValueError(f"Action '{action_type}' has no registered handler.")
                output_result = action_def.handler(context) or {}
                success = True

        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {str(exc)}\n{traceback.format_exc()}"
            success = False
            output_result = {"error": str(exc)}

        duration_ms = int((time.time() - start_time) * 1000)

        # 4. Finalize Audit Log
        log_entry.status = 'success' if success else 'failed'
        log_entry.output_result = output_result
        log_entry.error_message = error_msg
        log_entry.duration_ms = duration_ms
        log_entry.save(update_fields=['status', 'output_result', 'error_message', 'duration_ms'])

        # 5. Update Rule Metrics & One-Shot State
        rule.last_run_at = timezone.now()
        rule.run_count += 1
        if rule.execution_mode == 'once' and success:
            rule.is_active = False

        rule.save(update_fields=['last_run_at', 'run_count', 'is_active'])

        return {
            "status": "success" if success else "failed",
            "log_id": log_entry.id,
            "duration_ms": duration_ms,
            "output": output_result,
            "error": error_msg,
        }

    @classmethod
    def dispatch_model_event(cls, instance: Any, event_type: str) -> int:
        """
        Finds and dispatches matching model event rules for a model instance.
        Returns count of rules dispatched.
        """
        app_label = instance._meta.app_label
        model_name = instance._meta.model_name
        model_identifier = f"{app_label}.{instance.__class__.__name__}"

        matching_rules = AutomationRule.objects.filter(
            is_active=True,
            trigger_type='model_event',
            target_model=model_identifier,
            event_type__in=[event_type, 'any']
        )

        if not matching_rules.exists():
            return 0

        # Build context snapshot
        context = {
            "model": model_identifier,
            "pk": instance.pk,
            "event": event_type,
        }
        for field in instance._meta.concrete_fields:
            val = getattr(instance, field.attname, None)
            if isinstance(val, (str, int, float, bool)) or val is None:
                context[field.name] = val
            elif hasattr(val, 'isoformat'):
                context[field.name] = val.isoformat()

        # If user model, check for attached profile fields
        if hasattr(instance, 'profile') and instance.profile:
            p = instance.profile
            context['is_agent'] = p.is_agent
            context['user_type'] = p.user_type
            context['hermes_profile_name'] = p.hermes_profile_name
            context['role'] = p.role
            context['provider'] = p.provider
            context['model_name'] = p.model_name
            context['reasoning_effort'] = p.reasoning_effort

        dispatched_count = 0
        from .tasks import execute_automation_rule_task

        for rule in matching_rules:
            # Check filter conditions pre-dispatch
            if rule.filter_conditions and not cls.evaluate_conditions(context, rule.filter_conditions):
                continue

            trigger_source = f"model_event:{model_identifier}#{instance.pk}:{event_type}"
            execute_automation_rule_task.delay(rule.id, context, trigger_source)
            dispatched_count += 1

        return dispatched_count
