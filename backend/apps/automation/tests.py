"""
Automated Unit Tests for apps.automation.
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule
from apps.automation.models import AutomationRule, AutomationLog
from apps.automation.registry import ServiceRegistry, register_action
from apps.automation.engine import AutomationEngine
from apps.automation.tasks import execute_automation_rule_task, scheduled_automation_task
from apps.automation.scheduler import sync_rule_to_celery_beat


class AutomationCoreTests(TestCase):
    """Tests core registry, condition matching, and engine execution."""

    def setUp(self):
        # Register a test action
        @register_action(
            name="test_math_action",
            category="internal_app",
            description="Multiplies value by 2",
            schema={"x": "number"}
        )
        def math_handler(context):
            x = context.get('x', 0)
            return {"result": x * 2}

    def test_registry_registration_and_lookup(self):
        action = ServiceRegistry.get_action("test_math_action")
        self.assertIsNotNone(action)
        self.assertEqual(action.category, "internal_app")
        self.assertEqual(action.description, "Multiplies value by 2")

    def test_dynamic_model_choices(self):
        choices = ServiceRegistry.get_registered_model_choices()
        self.assertTrue(len(choices) > 0)
        # Check that auth.User and integration.AgentTask are discovered
        model_identifiers = []
        for group_label, models_list in choices:
            for ident, label in models_list:
                model_identifiers.append(ident)

        self.assertIn("auth.User", model_identifiers)
        self.assertIn("integration.AgentTask", model_identifiers)

    def test_condition_evaluation(self):
        # Exact match
        self.assertTrue(AutomationEngine.evaluate_conditions({"status": "active"}, {"status": "active"}))
        self.assertFalse(AutomationEngine.evaluate_conditions({"status": "inactive"}, {"status": "active"}))

        # Boolean match
        self.assertTrue(AutomationEngine.evaluate_conditions({"is_agent": True}, {"is_agent": True}))
        self.assertFalse(AutomationEngine.evaluate_conditions({"is_agent": False}, {"is_agent": True}))

        # Nested lookup
        context = {"profile": {"is_agent": True, "tier": "gold"}}
        self.assertTrue(AutomationEngine.evaluate_conditions(context, {"profile.is_agent": True}))
        self.assertTrue(AutomationEngine.evaluate_conditions(context, {"profile.tier": "gold"}))
        self.assertFalse(AutomationEngine.evaluate_conditions(context, {"profile.tier": "silver"}))

    def test_engine_rule_execution_success(self):
        rule = AutomationRule.objects.create(
            name="Test Math Rule",
            trigger_type="manual",
            action_category="internal_app",
            action_type="test_math_action",
            action_params={"x": 21},
            is_active=True,
        )

        res = AutomationEngine.execute_rule(rule.id, trigger_source="unit_test")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["output"]["result"], 42)

        # Verify log entry
        log = AutomationLog.objects.filter(rule=rule).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, "success")
        self.assertEqual(log.output_result.get("result"), 42)
        self.assertTrue(log.duration_ms >= 0)

        # Verify rule metrics
        rule.refresh_from_db()
        self.assertEqual(rule.run_count, 1)
        self.assertIsNotNone(rule.last_run_at)

    def test_engine_paused_rule_skipped(self):
        rule = AutomationRule.objects.create(
            name="Paused Rule",
            trigger_type="manual",
            action_category="internal_app",
            action_type="test_math_action",
            is_active=False,
        )

        res = AutomationEngine.execute_rule(rule.id)
        self.assertEqual(res["status"], "skipped")
        self.assertIn("paused", res["reason"])
        self.assertEqual(AutomationLog.objects.filter(rule=rule).count(), 0)

    def test_engine_once_mode_deactivation(self):
        rule = AutomationRule.objects.create(
            name="Once Rule",
            trigger_type="manual",
            execution_mode="once",
            action_category="internal_app",
            action_type="test_math_action",
            action_params={"x": 5},
            is_active=True,
        )

        res = AutomationEngine.execute_rule(rule.id)
        self.assertEqual(res["status"], "success")

        # Verify rule is now inactive
        rule.refresh_from_db()
        self.assertFalse(rule.is_active)
        self.assertEqual(rule.run_count, 1)

    def test_celery_task_execution(self):
        rule = AutomationRule.objects.create(
            name="Celery Task Rule",
            trigger_type="manual",
            action_category="internal_app",
            action_type="test_math_action",
            action_params={"x": 10},
            is_active=True,
        )

        # Execute celery task synchronously in test
        res = execute_automation_rule_task(rule.id, {"x": 15}, "celery_test")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["output"]["result"], 30)

        # Scheduled task
        res_sched = scheduled_automation_task(rule.id)
        self.assertEqual(res_sched["status"], "success")
        self.assertEqual(res_sched["output"]["result"], 20)

    def test_celery_beat_interval_sync(self):
        rule = AutomationRule.objects.create(
            name="Periodic Beat Rule",
            trigger_type="time_based",
            schedule_unit="minutes",
            schedule_value=15,
            action_category="internal_app",
            action_type="test_math_action",
            is_active=True,
        )

        rule.refresh_from_db()
        self.assertIsNotNone(rule.periodic_task)
        self.assertTrue(rule.periodic_task.enabled)
        self.assertEqual(rule.periodic_task.interval.every, 15)
        self.assertEqual(rule.periodic_task.interval.period, IntervalSchedule.MINUTES)

        # Pause rule and verify periodic task is disabled
        rule.is_active = False
        rule.save()
        rule.refresh_from_db()
        self.assertFalse(rule.periodic_task.enabled)

        # Delete rule and verify periodic task is cleaned up
        periodic_task_id = rule.periodic_task.id
        rule.delete()
        self.assertFalse(PeriodicTask.objects.filter(id=periodic_task_id).exists())

    def test_celery_beat_months_sync(self):
        rule = AutomationRule.objects.create(
            name="Monthly Beat Rule",
            trigger_type="time_based",
            schedule_unit="months",
            schedule_value=2,
            action_category="internal_app",
            action_type="test_math_action",
            is_active=True,
        )

        rule.refresh_from_db()
        self.assertIsNotNone(rule.periodic_task)
        self.assertIsNotNone(rule.periodic_task.crontab)
        self.assertEqual(rule.periodic_task.crontab.month_of_year, "*/2")
