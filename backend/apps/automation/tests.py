"""
Automated Unit Tests for apps.automation.
"""

import os
import shutil
from django.test import TestCase, override_settings
from django.contrib import admin
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token
from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule, ClockedSchedule, SolarSchedule

from apps.automation.models import AutomationRule, AutomationLog
from apps.automation.registry import ServiceRegistry, register_action
from apps.automation.engine import AutomationEngine
from apps.automation.tasks import execute_automation_rule_task, scheduled_automation_task
from apps.automation.actions import provision_hermes_profile_action
from apps.integration.models import AgentTask, Profile


class AutomationCoreTests(TestCase):
    """Tests core registry, condition matching, engine execution, and scheduling."""

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

        # Admin user for API tests
        self.client = APIClient()
        self.admin_user = User.objects.create_superuser(
            username='admin_auto_test',
            email='admin@example.com',
            password='admin_password_123'
        )
        self.client.force_authenticate(user=self.admin_user)

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

    def test_provision_hermes_profile_action(self):
        user = User.objects.create_user(username='bot_unit_tester', password='secure_password_123')
        res = provision_hermes_profile_action({
            "username": "bot_unit_tester",
            "profile_name": "unit_tester",
            "display_name": "Unit Tester Agent",
            "role": "testing",
        })

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["profile_slug"], "unit_tester")

        # Verify token generated
        token = Token.objects.filter(user=user).first()
        self.assertIsNotNone(token)

        # Clean up files created during test
        for base_dir in ['/app/agent_profiles/unit_tester', '/app/hermes_runtime_profiles/unit_tester']:
            if os.path.exists(base_dir):
                shutil.rmtree(base_dir)

    def test_automation_api_endpoints(self):
        rule = AutomationRule.objects.create(
            name="API Test Rule",
            trigger_type="manual",
            action_category="internal_app",
            action_type="test_math_action",
            action_params={"x": 100},
            is_active=True,
        )

        # 1. List rules
        resp = self.client.get('/api/automation/rules/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # 2. Trigger rule on-demand
        resp = self.client.post(f'/api/automation/rules/{rule.id}/trigger/', {"x": 50}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn("task_id", resp.data)

        # 3. List logs
        resp = self.client.get('/api/automation/logs/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # 4. List registered services
        resp = self.client.get('/api/automation/services/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("services", resp.data)
        self.assertIn("available_models", resp.data)

    def test_celery_beat_models_unregistered_from_admin(self):
        """Verifies that confusing Celery Beat plumbing models are excluded from Django Admin."""
        for beat_model in (ClockedSchedule, CrontabSchedule, IntervalSchedule, SolarSchedule, PeriodicTask):
            self.assertNotIn(
                beat_model,
                admin.site._registry,
                f"Model {beat_model.__name__} should be unregistered from Django Admin."
            )

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_odoo_style_state_transition_triggers(self):
        """Tests that field_changed rules trigger only when the specific field transitions as configured."""
        user = User.objects.create_user(username='task_owner_test', password='password123')
        profile = user.profile
        profile.display_name = "Test Task Profile"
        profile.role = "general"
        profile.is_agent = True
        profile.save()

        task = AgentTask.objects.create(
            created_by=user,
            task_name="Verify QA Pipeline",
            assigned_profile=profile,
            status="review"
        )

        # Create state transition rule: status must change from 'review' to 'completed'
        rule = AutomationRule.objects.create(
            name="QA Approval Notification",
            trigger_type="model_event",
            target_model="integration.AgentTask",
            event_type="field_changed",
            trigger_field="status",
            previous_value="review",
            target_value="completed",
            action_category="internal_app",
            action_type="test_math_action",
            action_params={"x": 5},
            is_active=True
        )

        # 1. Update unrelated field (cost_usd) -> Should NOT trigger
        initial_log_count = AutomationLog.objects.count()
        task.cost_usd = 1.25
        task.save()
        self.assertEqual(AutomationLog.objects.count(), initial_log_count)

        # 2. Update status to wrong target ('failed') -> Should NOT trigger
        task.status = "failed"
        task.save()
        self.assertEqual(AutomationLog.objects.count(), initial_log_count)

        # 3. Transition status to 'review' again (reset)
        task.status = "review"
        task.save()
        self.assertEqual(AutomationLog.objects.count(), initial_log_count)

        # 4. Valid state transition: 'review' -> 'completed' -> MUST trigger!
        task.status = "completed"
        task.save()

        # Check that AutomationLog was created and executed successfully
        latest_log = AutomationLog.objects.filter(rule=rule).order_by('-executed_at').first()
        self.assertIsNotNone(latest_log)
        self.assertEqual(latest_log.status, "success")
        self.assertEqual(latest_log.output_result.get("result"), 10)
        self.assertIn("status", latest_log.input_context.get("changed_fields", []))

