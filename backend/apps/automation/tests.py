"""
Automated Unit Tests for apps.automation.
Covers Core Registry, 1-to-N Decoupled Triggers and Actions Pipeline,
Unified Celery Dispatch, Target CRUD, Introspection, and Reified System Signals.
"""

import os
import shutil
from django.test import TestCase, override_settings
from django.contrib import admin
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token
from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule, ClockedSchedule, SolarSchedule

from apps.automation.models import AutomationTrigger, AutomationAction, AutomationLog, AutomationRule
from apps.automation.registry import ServiceRegistry, register_action
from apps.automation.engine import AutomationEngine
from apps.automation.tasks import (
    execute_automation_action_task,
    execute_automation_trigger_task,
    execute_automation_rule_task,
    scheduled_automation_task,
)
from apps.automation.actions import provision_hermes_profile_action, provision_user_profile_action
from apps.integration.models import AgentTask, Profile


class AutomationCoreTests(TestCase):
    """Tests core registry, condition matching, engine execution, and scheduling."""

    def setUp(self):
        @register_action(
            name="test_math_action",
            category="internal_app",
            description="Multiplies value by 2",
            schema={"x": "number"}
        )
        def math_handler(context):
            x = context.get('x', 0)
            return {"result": x * 2}

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
        model_identifiers = []
        for group_label, models_list in choices:
            for ident, label in models_list:
                model_identifiers.append(ident)

        self.assertIn("auth.User", model_identifiers)
        self.assertIn("integration.AgentTask", model_identifiers)

    def test_condition_evaluation(self):
        self.assertTrue(AutomationEngine.evaluate_conditions({"status": "active"}, {"status": "active"}))
        self.assertFalse(AutomationEngine.evaluate_conditions({"status": "inactive"}, {"status": "active"}))
        self.assertTrue(AutomationEngine.evaluate_conditions({"is_agent": True}, {"is_agent": True}))
        self.assertFalse(AutomationEngine.evaluate_conditions({"is_agent": False}, {"is_agent": True}))

        context = {"profile": {"is_agent": True, "tier": "gold"}}
        self.assertTrue(AutomationEngine.evaluate_conditions(context, {"profile.is_agent": True}))
        self.assertTrue(AutomationEngine.evaluate_conditions(context, {"profile.tier": "gold"}))
        self.assertFalse(AutomationEngine.evaluate_conditions(context, {"profile.tier": "silver"}))

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_engine_action_execution_success(self):
        trigger = AutomationTrigger.objects.create(
            name="Test Math Trigger",
            trigger_type="manual",
            is_active=True,
        )
        action = AutomationAction.objects.create(
            trigger=trigger,
            name="Multiply by 2",
            sequence=10,
            action_category="internal_app",
            action_type="test_math_action",
            action_params={"x": 21},
            is_active=True,
        )

        res = AutomationEngine.execute_action(action.id, trigger_source="unit_test")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["output"]["result"], 42)

        # Verify log entry
        log = AutomationLog.objects.filter(action=action).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, "success")
        self.assertEqual(log.trigger, trigger)
        self.assertEqual(log.output_result.get("result"), 42)
        self.assertTrue(log.duration_ms >= 0)

        # Verify action metrics
        action.refresh_from_db()
        self.assertEqual(action.run_count, 1)
        self.assertIsNotNone(action.last_run_at)

        # Verify trigger metrics
        trigger.refresh_from_db()
        self.assertEqual(trigger.trigger_count, 1)
        self.assertIsNotNone(trigger.last_triggered_at)

    def test_engine_paused_action_skipped(self):
        trigger = AutomationTrigger.objects.create(
            name="Paused Trigger",
            trigger_type="manual",
            is_active=True,
        )
        action = AutomationAction.objects.create(
            trigger=trigger,
            name="Paused Action",
            sequence=10,
            action_category="internal_app",
            action_type="test_math_action",
            is_active=False,
        )

        res = AutomationEngine.execute_action(action.id)
        self.assertEqual(res["status"], "skipped")
        self.assertIn("inactive", res["reason"])
        self.assertEqual(AutomationLog.objects.filter(action=action).count(), 0)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_engine_once_mode_deactivation(self):
        trigger = AutomationTrigger.objects.create(
            name="Once Trigger",
            trigger_type="manual",
            execution_mode="once",
            is_active=True,
        )
        action = AutomationAction.objects.create(
            trigger=trigger,
            name="Once Action Step",
            sequence=10,
            action_category="internal_app",
            action_type="test_math_action",
            action_params={"x": 5},
            is_active=True,
        )

        res = AutomationEngine.execute_action(action.id)
        self.assertEqual(res["status"], "success")

        # Verify trigger is now inactive
        trigger.refresh_from_db()
        self.assertFalse(trigger.is_active)
        self.assertEqual(trigger.trigger_count, 1)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_celery_task_execution(self):
        trigger = AutomationTrigger.objects.create(
            name="Celery Task Trigger",
            trigger_type="manual",
            is_active=True,
        )
        action = AutomationAction.objects.create(
            trigger=trigger,
            name="Celery Action",
            sequence=10,
            action_category="internal_app",
            action_type="test_math_action",
            action_params={"x": 10},
            is_active=True,
        )

        res = execute_automation_action_task(action.id, {"x": 15}, "celery_test")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["output"]["result"], 30)

        # Scheduled trigger task
        res_sched = scheduled_automation_task(trigger.id)
        self.assertEqual(res_sched["status"], "success")
        self.assertEqual(res_sched["dispatched_actions"], 1)

    def test_celery_beat_interval_sync(self):
        trigger = AutomationTrigger.objects.create(
            name="Periodic Beat Trigger",
            trigger_type="time_based",
            schedule_unit="minutes",
            schedule_value=15,
            is_active=True,
        )
        AutomationAction.objects.create(
            trigger=trigger,
            name="Periodic Action",
            sequence=10,
            action_category="internal_app",
            action_type="test_math_action",
            is_active=True,
        )

        trigger.refresh_from_db()
        self.assertIsNotNone(trigger.periodic_task)
        self.assertTrue(trigger.periodic_task.enabled)
        self.assertEqual(trigger.periodic_task.interval.every, 15)
        self.assertEqual(trigger.periodic_task.interval.period, IntervalSchedule.MINUTES)

        # Pause trigger and verify periodic task is disabled
        trigger.is_active = False
        trigger.save()
        trigger.refresh_from_db()
        self.assertFalse(trigger.periodic_task.enabled)

        # Delete trigger and verify periodic task is cleaned up
        periodic_task_id = trigger.periodic_task.id
        trigger.delete()
        self.assertFalse(PeriodicTask.objects.filter(id=periodic_task_id).exists())

    def test_celery_beat_months_sync(self):
        trigger = AutomationTrigger.objects.create(
            name="Monthly Beat Trigger",
            trigger_type="time_based",
            schedule_unit="months",
            schedule_value=2,
            is_active=True,
        )

        trigger.refresh_from_db()
        self.assertIsNotNone(trigger.periodic_task)
        self.assertIsNotNone(trigger.periodic_task.crontab)
        self.assertEqual(trigger.periodic_task.crontab.month_of_year, "*/2")

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

        token = Token.objects.filter(user=user).first()
        self.assertIsNotNone(token)

        for base_dir in ['/app/agent_profiles/unit_tester', '/app/hermes_runtime_profiles/unit_tester']:
            if os.path.exists(base_dir):
                shutil.rmtree(base_dir)

    def test_automation_api_endpoints(self):
        trigger = AutomationTrigger.objects.create(
            name="API Test Trigger",
            trigger_type="manual",
            is_active=True,
        )
        action = AutomationAction.objects.create(
            trigger=trigger,
            name="API Test Action",
            sequence=10,
            action_category="internal_app",
            action_type="test_math_action",
            action_params={"x": 100},
            is_active=True,
        )

        # 1. List triggers
        resp = self.client.get('/api/automation/triggers/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # 2. Trigger pipeline on-demand
        resp = self.client.post(f'/api/automation/triggers/{trigger.id}/trigger/', {"x": 50}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn("task_id", resp.data)

        # 3. List actions
        resp = self.client.get('/api/automation/actions/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # 4. List logs
        resp = self.client.get('/api/automation/logs/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # 5. List registered services
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

        trigger = AutomationTrigger.objects.create(
            name="QA Approval Notification",
            trigger_type="model_event",
            trigger_model="integration.AgentTask",
            event_type="field_changed",
            trigger_field="status",
            previous_value="review",
            target_value="completed",
            is_active=True
        )
        action = AutomationAction.objects.create(
            trigger=trigger,
            name="QA Approval Math Step",
            sequence=10,
            action_category="internal_app",
            action_type="test_math_action",
            action_params={"x": 5},
            is_active=True
        )

        # 1. Update unrelated field -> Should NOT trigger
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

        latest_log = AutomationLog.objects.filter(action=action).order_by('-executed_at').first()
        self.assertIsNotNone(latest_log)
        self.assertEqual(latest_log.status, "success")
        self.assertEqual(latest_log.output_result.get("result"), 10)
        self.assertIn("status", latest_log.input_context.get("changed_fields", []))


class Phase7DecoupledPipelineTests(TestCase):
    """Tests for Phase 7: 1-to-N Action Pipelines, System Signal Reification, and Target CRUD."""

    def setUp(self):
        @register_action(
            name="step_one_action",
            category="internal_app",
            description="Step 1 in pipeline",
            schema={}
        )
        def step_one(ctx):
            return {"step": 1, "done": True}

        @register_action(
            name="step_two_action",
            category="internal_app",
            description="Step 2 in pipeline",
            schema={}
        )
        def step_two(ctx):
            return {"step": 2, "done": True}

        self.client = APIClient()
        self.admin_user = User.objects.create_superuser(
            username='admin_phase7_test',
            email='phase7@example.com',
            password='password123'
        )
        self.client.force_authenticate(user=self.admin_user)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_one_to_n_sequenced_pipeline_execution(self):
        """Tests that a single trigger executes multiple actions in order with individual logs."""
        trigger = AutomationTrigger.objects.create(
            name="Multi-Step Pipeline Trigger",
            trigger_type="manual",
            is_active=True,
        )
        act1 = AutomationAction.objects.create(
            trigger=trigger,
            name="Step 1: First Action",
            sequence=10,
            action_category="internal_app",
            action_type="step_one_action",
            is_active=True,
        )
        act2 = AutomationAction.objects.create(
            trigger=trigger,
            name="Step 2: Second Action",
            sequence=20,
            action_category="internal_app",
            action_type="step_two_action",
            is_active=True,
        )

        res = AutomationEngine.execute_trigger(trigger.id, {"user": "tester"})
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["dispatched_actions"], 2)

        # Verify logs created for each action
        log1 = AutomationLog.objects.filter(action=act1).first()
        log2 = AutomationLog.objects.filter(action=act2).first()
        self.assertIsNotNone(log1)
        self.assertIsNotNone(log2)
        self.assertEqual(log1.trigger, trigger)
        self.assertEqual(log2.trigger, trigger)
        self.assertEqual(log1.output_result.get("step"), 1)
        self.assertEqual(log2.output_result.get("step"), 2)

    def test_introspection_api_success(self):
        response = self.client.get('/api/automation/introspection/?model=integration.AgentTask')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['model'], 'integration.AgentTask')
        self.assertIn('fields', data)
        self.assertIn('required_fields', data)
        field_names = [f['name'] for f in data['fields']]
        self.assertIn('task_name', field_names)
        self.assertIn('status', field_names)

    def test_introspection_api_catalog(self):
        response = self.client.get('/api/automation/introspection/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('available_models', data)
        self.assertTrue(data['count'] > 0)

    def test_introspection_api_errors(self):
        res1 = self.client.get('/api/automation/introspection/?model=AgentTask')
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)

        res2 = self.client.get('/api/automation/introspection/?model=nonexistent.FakeModel')
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_visual_condition_rules_evaluation(self):
        ctx = {"status": "completed", "cost_usd": 12.50, "tags": "ai,llm,test", "notes": None}

        self.assertTrue(AutomationEngine.evaluate_condition_rules(ctx, [{"field": "status", "operator": "==", "value": "completed"}]))
        self.assertFalse(AutomationEngine.evaluate_condition_rules(ctx, [{"field": "status", "operator": "==", "value": "pending"}]))
        self.assertTrue(AutomationEngine.evaluate_condition_rules(ctx, [{"field": "cost_usd", "operator": ">", "value": 10.0}]))
        self.assertFalse(AutomationEngine.evaluate_condition_rules(ctx, [{"field": "cost_usd", "operator": ">", "value": 20.0}]))
        self.assertTrue(AutomationEngine.evaluate_condition_rules(ctx, [{"field": "cost_usd", "operator": "<=", "value": 12.50}]))
        self.assertTrue(AutomationEngine.evaluate_condition_rules(ctx, [{"field": "tags", "operator": "contains", "value": "llm"}]))
        self.assertTrue(AutomationEngine.evaluate_condition_rules(ctx, [{"field": "status", "operator": "in", "value": "draft,pending,completed"}]))
        self.assertFalse(AutomationEngine.evaluate_condition_rules(ctx, [{"field": "status", "operator": "in", "value": "failed,cancelled"}]))
        self.assertTrue(AutomationEngine.evaluate_condition_rules(ctx, [{"field": "notes", "operator": "is_empty", "value": ""}]))
        self.assertTrue(AutomationEngine.evaluate_condition_rules(ctx, [{"field": "status", "operator": "is_not_empty", "value": ""}]))

    def test_temporal_date_condition_rules(self):
        """Tests that condition rules accurately evaluate dates and timestamps."""
        ctx = {
            "created_at": "2026-09-09T08:14:26+03:00",
            "due_date": "2026-09-15",
            "start_date": "2026-09-01",
        }

        # Date equality
        self.assertTrue(AutomationEngine.evaluate_condition_rules(
            ctx, [{"field": "due_date", "operator": "==", "value": "2026-09-15"}]
        ))
        self.assertFalse(AutomationEngine.evaluate_condition_rules(
            ctx, [{"field": "due_date", "operator": "==", "value": "2026-09-14"}]
        ))

        # Greater than / After Date
        self.assertTrue(AutomationEngine.evaluate_condition_rules(
            ctx, [{"field": "due_date", "operator": ">", "value": "2026-09-10"}]
        ))
        self.assertFalse(AutomationEngine.evaluate_condition_rules(
            ctx, [{"field": "due_date", "operator": ">", "value": "2026-09-20"}]
        ))

        # Less than / Before Date
        self.assertTrue(AutomationEngine.evaluate_condition_rules(
            ctx, [{"field": "start_date", "operator": "<", "value": "2026-09-05"}]
        ))

        # Datetime comparison against YYYY-MM-DD
        self.assertTrue(AutomationEngine.evaluate_condition_rules(
            ctx, [{"field": "created_at", "operator": "==", "value": "2026-09-09"}]
        ))
        self.assertTrue(AutomationEngine.evaluate_condition_rules(
            ctx, [{"field": "created_at", "operator": ">=", "value": "2026-09-01"}]
        ))
        self.assertTrue(AutomationEngine.evaluate_condition_rules(
            ctx, [{"field": "created_at", "operator": "<=", "value": "2026-09-10"}]
        ))

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_target_crud_create(self):
        trigger = AutomationTrigger.objects.create(
            name="Create Task Trigger",
            trigger_type="manual",
            is_active=True,
        )
        action = AutomationAction.objects.create(
            trigger=trigger,
            name="Create Agent Task Action",
            sequence=10,
            target_model="integration.AgentTask",
            target_operation="create",
            field_mappings={
                "task_name": "Automated Review for {{username}}",
                "created_by": "{{user_id}}",
                "status": "pending"
            },
            is_active=True
        )

        res = AutomationEngine.execute_action(
            action.id,
            trigger_context={"username": self.admin_user.username, "user_id": self.admin_user.id}
        )
        self.assertEqual(res["status"], "success")
        output = res["output"]
        self.assertEqual(output["operation"], "create")
        task_id = output["record_id"]

        task = AgentTask.objects.get(pk=task_id)
        self.assertEqual(task.task_name, f"Automated Review for {self.admin_user.username}")
        self.assertEqual(task.created_by, self.admin_user)
        self.assertEqual(task.status, "pending")

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_target_crud_update(self):
        task = AgentTask.objects.create(
            task_name="Existing Task",
            created_by=self.admin_user,
            status="pending"
        )

        trigger = AutomationTrigger.objects.create(
            name="Update Task Trigger",
            trigger_type="manual",
            is_active=True,
        )
        action = AutomationAction.objects.create(
            trigger=trigger,
            name="Update Task Status Action",
            sequence=10,
            target_model="integration.AgentTask",
            target_operation="update",
            field_mappings={
                "status": "completed",
                "cost_usd": "3.75"
            },
            is_active=True
        )

        res = AutomationEngine.execute_action(
            action.id,
            trigger_context={"target_record_id": str(task.id)}
        )
        self.assertEqual(res["status"], "success")

        task.refresh_from_db()
        self.assertEqual(task.status, "completed")
        self.assertEqual(float(task.cost_usd), 3.75)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_target_crud_delete(self):
        task = AgentTask.objects.create(
            task_name="Task to Delete",
            created_by=self.admin_user
        )

        trigger = AutomationTrigger.objects.create(
            name="Delete Task Trigger",
            trigger_type="manual",
            is_active=True,
        )
        action = AutomationAction.objects.create(
            trigger=trigger,
            name="Delete Task Action",
            sequence=10,
            target_model="integration.AgentTask",
            target_operation="delete",
            is_active=True
        )

        res = AutomationEngine.execute_action(
            action.id,
            trigger_context={"target_record_id": str(task.id)}
        )
        self.assertEqual(res["status"], "success")
        self.assertFalse(AgentTask.objects.filter(pk=task.id).exists())

    def test_system_trigger_and_action_protection(self):
        from django.core.exceptions import ValidationError

        system_trigger = AutomationTrigger.objects.create(
            name="Protected System Trigger",
            trigger_type="manual",
            is_system=True,
            is_active=True
        )
        system_action = AutomationAction.objects.create(
            trigger=system_trigger,
            name="Protected System Action",
            sequence=10,
            is_system=True,
            is_active=True
        )

        # Deleting trigger or action must raise ValidationError
        with self.assertRaises(ValidationError):
            system_trigger.delete()

        with self.assertRaises(ValidationError):
            system_action.delete()

        self.assertTrue(AutomationTrigger.objects.filter(pk=system_trigger.id).exists())
        self.assertTrue(AutomationAction.objects.filter(pk=system_action.id).exists())

    def test_seed_automations_command(self):
        from django.core.management import call_command
        call_command('seed_automations')

        # Check core triggers
        provision_trigger = AutomationTrigger.objects.filter(name="Auto-Provision Hermes Profile on Agent User Creation").first()
        self.assertIsNotNone(provision_trigger)
        self.assertTrue(provision_trigger.is_system)
        self.assertEqual(provision_trigger.trigger_model, "integration.Profile")
        self.assertTrue(provision_trigger.actions.filter(is_system=True).exists())

        reified_user_trigger = AutomationTrigger.objects.filter(name="Auto-Provision Profile on User Creation").first()
        self.assertIsNotNone(reified_user_trigger)
        self.assertTrue(reified_user_trigger.is_system)
        self.assertEqual(reified_user_trigger.trigger_model, "auth.User")
        self.assertEqual(reified_user_trigger.event_type, "created")
        self.assertTrue(reified_user_trigger.actions.filter(action_type="provision_user_profile").exists())

    def test_reified_user_profile_action(self):
        """Tests the provision_user_profile action directly."""
        new_user = User.objects.create_user(username='bot_coder', password='password123')
        res = provision_user_profile_action({"username": "bot_coder"})
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["is_agent"])
        self.assertEqual(res["user_type"], "agent")
