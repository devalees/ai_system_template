"""
Core Execution Engine & Dispatcher for Centralized Automations.
"""

import re
import time
import traceback
import uuid
from typing import Any, Dict, List, Optional
from django.utils import timezone
from .models import AutomationRule, AutomationLog
from .registry import ServiceRegistry


def make_json_serializable(obj: Any) -> Any:
    """Recursively converts UUIDs, datetimes, and complex objects to JSON-serializable primitives."""
    if isinstance(obj, dict):
        return {str(k): make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set)):
        return [make_json_serializable(v) for v in obj]
    elif isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    return str(obj)


def get_nested_context_value(context: Dict[str, Any], key: str) -> Any:
    """Extracts a value from context supporting dot notation (e.g. 'profile.is_agent')."""
    if not key or not context:
        return None
    if key in context:
        return context[key]
    if '.' in key:
        parts = key.split('.')
        curr = context
        for p in parts:
            if isinstance(curr, dict):
                curr = curr.get(p)
            else:
                curr = getattr(curr, p, None)
            if curr is None:
                break
        return curr
    return None


def evaluate_single_condition(actual: Any, operator: str, expected: Any) -> bool:
    """Evaluates a single comparison between actual context value and expected rule value."""
    op = (operator or '==').strip().lower()

    if op in ('==', 'eq', 'equals'):
        if isinstance(expected, bool):
            return bool(actual) == expected
        if actual is None and expected is None:
            return True
        if actual is None or expected is None:
            return False
        try:
            return float(actual) == float(expected)
        except (ValueError, TypeError):
            return str(actual).strip().lower() == str(expected).strip().lower()

    elif op in ('!=', 'ne', 'not_equals'):
        return not evaluate_single_condition(actual, '==', expected)

    elif op in ('>', 'gt'):
        try:
            return float(actual) > float(expected)
        except (ValueError, TypeError):
            return False

    elif op in ('>=', 'gte'):
        try:
            return float(actual) >= float(expected)
        except (ValueError, TypeError):
            return False

    elif op in ('<', 'lt'):
        try:
            return float(actual) < float(expected)
        except (ValueError, TypeError):
            return False

    elif op in ('<=', 'lte'):
        try:
            return float(actual) <= float(expected)
        except (ValueError, TypeError):
            return False

    elif op in ('contains', 'icontains'):
        return str(expected).lower() in str(actual or '').lower()

    elif op in ('not_contains', 'not contains'):
        return str(expected).lower() not in str(actual or '').lower()

    elif op == 'in':
        if isinstance(expected, (list, tuple, set)):
            return actual in expected or str(actual).lower() in [str(x).lower() for x in expected]
        if isinstance(expected, str):
            candidates = [x.strip().lower() for x in expected.split(',')]
            return str(actual).strip().lower() in candidates
        return False

    elif op in ('not_in', 'not in'):
        return not evaluate_single_condition(actual, 'in', expected)

    elif op in ('is_empty', 'is_null'):
        return actual is None or actual == ''

    elif op in ('is_not_empty', 'is_not_null'):
        return actual is not None and actual != ''

    return False


def resolve_template_value(template: Any, context: Dict[str, Any], field_meta: Any = None) -> Any:
    """
    Interpolates {{variable}} expressions from context and coerces to target field type.
    """
    if not isinstance(template, str):
        return template

    template = template.strip()

    # 1. Exact match e.g. "{{cost_usd}}" or "{{assigned_profile}}"
    exact_match = re.match(r'^\{\{\s*([\w\.]+)\s*\}\}$', template)
    if exact_match:
        val = get_nested_context_value(context, exact_match.group(1))
    else:
        # 2. Embedded string interpolation e.g. "Task for {{username}}"
        def repl(match):
            k = match.group(1)
            v = get_nested_context_value(context, k)
            return str(v) if v is not None else ''

        val = re.sub(r'\{\{\s*([\w\.]+)\s*\}\}', repl, template)

    # 3. Field metadata type coercion
    if field_meta is not None and val is not None:
        internal_type = getattr(field_meta, 'get_internal_type', lambda: '')()

        if internal_type == 'BooleanField':
            if isinstance(val, str):
                return val.lower() in ('true', '1', 'yes', 't')
            return bool(val)

        elif internal_type in ('IntegerField', 'PositiveIntegerField', 'SmallIntegerField', 'BigIntegerField'):
            try:
                return int(val)
            except (ValueError, TypeError):
                pass

        elif internal_type in ('FloatField', 'DecimalField'):
            try:
                return float(val)
            except (ValueError, TypeError):
                pass

        elif field_meta.is_relation and field_meta.related_model:
            # If value is already an instance of related model
            if isinstance(val, field_meta.related_model):
                return val
            # If string and model has 'username', try to look up user
            if isinstance(val, str) and hasattr(field_meta.related_model, 'username'):
                user_obj = field_meta.related_model.objects.filter(username=val).first()
                if user_obj:
                    return user_obj
            # If UUID or PK
            try:
                obj = field_meta.related_model.objects.filter(pk=val).first()
                if obj:
                    return obj
            except Exception:
                pass

    return val


class AutomationEngine:
    """Central engine orchestrating trigger evaluation and action execution."""

    @classmethod
    def evaluate_conditions(cls, context: Dict[str, Any], conditions: Dict[str, Any]) -> bool:
        """
        Evaluates filter conditions against execution context.
        Supports exact match, booleans, nested keys, and string comparisons.
        """
        if not conditions:
            return True

        for key, expected_val in conditions.items():
            actual_val = get_nested_context_value(context, key)
            if not evaluate_single_condition(actual_val, '==', expected_val):
                return False

        return True

    @classmethod
    def evaluate_condition_rules(cls, context: Dict[str, Any], rules: Any) -> bool:
        """
        Evaluates Odoo-style visual condition rules.
        Expected format: [{'field': 'status', 'operator': '==', 'value': 'completed'}, ...]
        """
        if not rules or not isinstance(rules, list):
            return True

        for rule in rules:
            if not isinstance(rule, dict):
                continue
            field_name = rule.get('field')
            operator = rule.get('operator', '==')
            expected_val = rule.get('value')
            actual_val = get_nested_context_value(context, field_name)

            if not evaluate_single_condition(actual_val, operator, expected_val):
                return False

        return True

    @classmethod
    def execute_target_crud(cls, rule: AutomationRule, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes automated Odoo-style CRUD operations on rule.target_model.
        Supports 'create', 'update', and 'delete' with dynamic field mappings.
        """
        from django.apps import apps
        if not rule.target_model:
            raise ValueError("Target model is not specified for CRUD operation.")

        try:
            target_cls = apps.get_model(rule.target_model)
            if not target_cls:
                raise LookupError()
        except (LookupError, ValueError):
            raise ValueError(f"Target model '{rule.target_model}' not found in installed apps.")

        operation = (rule.target_operation or 'create').lower().strip()
        fields_by_name = {f.name: f for f in target_cls._meta.fields}
        resolved_fields = {}

        for k, raw_v in (rule.field_mappings or {}).items():
            field_meta = fields_by_name.get(k)
            resolved_v = resolve_template_value(raw_v, context, field_meta)
            if field_meta and field_meta.is_relation and not hasattr(resolved_v, '_meta'):
                # Scalar ID for relationship
                resolved_fields[field_meta.attname] = resolved_v
            else:
                resolved_fields[k] = resolved_v

        if operation == 'create':
            instance = target_cls.objects.create(**resolved_fields)
            return {
                "operation": "create",
                "target_model": rule.target_model,
                "record_id": str(instance.pk),
                "created_fields": make_json_serializable(resolved_fields),
            }

        elif operation == 'update':
            record_id = (
                resolved_fields.pop('id', None)
                or resolved_fields.pop('pk', None)
                or context.get('target_record_id')
                or context.get('pk')
            )
            if not record_id:
                raise ValueError("Update operation requires 'id' or 'target_record_id' in field_mappings or context.")

            instance = target_cls.objects.get(pk=record_id)
            updated_fields = []
            for f_name, f_val in resolved_fields.items():
                if hasattr(instance, f_name):
                    setattr(instance, f_name, f_val)
                    updated_fields.append(f_name)
            instance.save()
            return {
                "operation": "update",
                "target_model": rule.target_model,
                "record_id": str(instance.pk),
                "updated_fields": updated_fields,
            }

        elif operation == 'delete':
            record_id = (
                resolved_fields.get('id')
                or resolved_fields.get('pk')
                or context.get('target_record_id')
                or context.get('pk')
            )
            if not record_id:
                raise ValueError("Delete operation requires 'id' or 'target_record_id' in field_mappings or context.")

            instance = target_cls.objects.get(pk=record_id)
            instance.delete()
            return {
                "operation": "delete",
                "target_model": rule.target_model,
                "record_id": str(record_id),
            }

        else:
            raise ValueError(f"Unsupported target operation: '{rule.target_operation}'")

    @classmethod
    def execute_rule(
        cls,
        rule_id: int,
        trigger_context: Optional[Dict[str, Any]] = None,
        trigger_source: str = "manual"
    ) -> Dict[str, Any]:
        """
        Executes an AutomationRule with timing, error containment, and audit logging.
        Handles both target model CRUD operations and registered action handlers.
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

        if rule.condition_rules and not cls.evaluate_condition_rules(context, rule.condition_rules):
            return {"status": "skipped", "reason": "Condition rules did not match"}

        # 2. Initialize Audit Log (safe serialized context)
        safe_context = make_json_serializable(context)
        log_entry = AutomationLog.objects.create(
            rule=rule,
            trigger_source=trigger_source,
            status='running',
            input_context=safe_context,
        )

        start_time = time.time()
        output_result = {}
        error_msg = ""
        success = False

        try:
            crud_result = None
            if rule.target_model and rule.target_operation:
                crud_result = cls.execute_target_crud(rule, context)

            action_result = None
            action_type = rule.action_type
            if action_type and action_type not in ('', 'none', 'target_crud'):
                if action_type.startswith("hermes_profile:"):
                    # Dynamic dispatch to specific Hermes profile
                    profile_slug = action_type.removeprefix("hermes_profile:")
                    from .actions import dispatch_hermes_prompt_action
                    context['profile'] = profile_slug
                    action_result = dispatch_hermes_prompt_action(context)
                    success = action_result.get('status') != 'error'
                else:
                    action_def = ServiceRegistry.get_action(action_type)
                    if not action_def or not action_def.handler:
                        raise ValueError(f"Action '{action_type}' has no registered handler.")
                    action_result = action_def.handler(context) or {}
                    success = True
            elif crud_result:
                success = True
            else:
                raise ValueError(f"Action '{action_type}' has no registered handler.")

            if crud_result and action_result:
                output_result = {"crud": crud_result, "action": action_result}
            elif crud_result:
                output_result = crud_result
            else:
                output_result = action_result or {}

        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {str(exc)}\n{traceback.format_exc()}"
            success = False
            output_result = {"error": str(exc)}

        duration_ms = int((time.time() - start_time) * 1000)

        # 4. Finalize Audit Log
        log_entry.status = 'success' if success else 'failed'
        log_entry.output_result = make_json_serializable(output_result)
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
    def dispatch_model_event(cls, instance: Any, event_type: str, old_values: Optional[Dict[str, Any]] = None) -> int:
        """
        Finds and dispatches matching model event rules for a model instance.
        Supports creation, updates, deletions, and Odoo-style state transitions.
        Returns count of rules dispatched.
        """
        app_label = instance._meta.app_label
        model_name = instance._meta.model_name
        model_identifier = f"{app_label}.{instance.__class__.__name__}"

        matching_event_types = [event_type, 'any']
        if event_type == 'updated':
            matching_event_types.append('field_changed')

        matching_rules = AutomationRule.objects.filter(
            is_active=True,
            trigger_type='model_event',
            trigger_model=model_identifier,
            event_type__in=matching_event_types
        )

        if not matching_rules.exists():
            return 0

        # Build context snapshot
        context = {
            "model": model_identifier,
            "pk": str(instance.pk),
            "event": event_type,
        }

        changed_fields = []
        for field in instance._meta.concrete_fields:
            val = getattr(instance, field.attname, None)
            if isinstance(val, (str, int, float, bool)) or val is None:
                context[field.name] = val
            elif hasattr(val, 'isoformat'):
                context[field.name] = val.isoformat()
            else:
                context[field.name] = str(val)

            # Detect changed fields on update
            if event_type == 'updated' and old_values:
                old_val = old_values.get(field.name, old_values.get(field.attname))
                if old_val != getattr(instance, field.attname, None):
                    changed_fields.append(field.name)

        context['changed_fields'] = changed_fields
        if old_values:
            context['previous_values'] = make_json_serializable(old_values)

        if hasattr(instance, 'username'):
            context['username'] = instance.username

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

        # If profile model, check for attached user fields
        if hasattr(instance, 'user') and instance.user:
            context['username'] = instance.user.username
            context['is_agent'] = getattr(instance, 'is_agent', False)

        dispatched_count = 0
        from .tasks import execute_automation_rule_task

        for rule in matching_rules:
            # 1. State transition / Field change evaluation
            if rule.event_type == 'field_changed' or rule.trigger_field:
                if rule.trigger_field:
                    if rule.trigger_field not in changed_fields:
                        continue

                    # Previous value check (before update)
                    if rule.previous_value:
                        prev_val = old_values.get(rule.trigger_field) if old_values else None
                        if str(prev_val).lower() != str(rule.previous_value).lower():
                            continue

                    # Target value check (after update)
                    if rule.target_value:
                        new_val = context.get(rule.trigger_field)
                        if str(new_val).lower() != str(rule.target_value).lower():
                            continue

            # 2. General filter conditions check
            if rule.filter_conditions and not cls.evaluate_conditions(context, rule.filter_conditions):
                continue

            # 3. Visual condition rules check (Odoo-Style)
            if rule.condition_rules and not cls.evaluate_condition_rules(context, rule.condition_rules):
                continue

            trigger_source = f"model_event:{model_identifier}#{instance.pk}:{event_type}"
            if rule.trigger_field:
                trigger_source += f":{rule.trigger_field}"

            execute_automation_rule_task.delay(rule.id, context, trigger_source)
            dispatched_count += 1

        return dispatched_count
