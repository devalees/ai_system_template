"""
Management command to seed default/flagship automation triggers and action pipelines.
"""

from django.core.management.base import BaseCommand
from apps.automation.models import AutomationTrigger, AutomationAction, AutomationLog


DEFAULT_TRIGGERS = [
    {
        "name": "Auto-Provision Hermes Profile on Agent User Creation",
        "description": "Automatically generates DRF auth token, creates declarative configuration files, and injects runtime .env into the Hermes Agent container whenever an Agent User is created or updated in Django.",
        "trigger_type": "model_event",
        "execution_mode": "recurring",
        "trigger_model": "integration.Profile",
        "event_type": "any",
        "filter_conditions": {"is_agent": True},
        "is_system": True,
        "is_active": True,
        "actions": [
            {
                "name": "Provision Hermes Profile Files & Token",
                "sequence": 10,
                "action_category": "hermes_agent",
                "action_type": "provision_hermes_profile",
                "action_params": {},
                "is_system": True,
                "is_active": True,
            }
        ]
    },
    {
        "name": "Daily Spend & Token Audit Dispatch",
        "description": "Periodic scheduled routine dispatching the Cost Controller agent to audit token consumption and operational spend across all profile state databases every 24 hours.",
        "trigger_type": "time_based",
        "execution_mode": "recurring",
        "schedule_unit": "hours",
        "schedule_value": 24,
        "is_system": True,
        "is_active": True,
        "actions": [
            {
                "name": "Dispatch Cost Controller Audit",
                "sequence": 10,
                "action_category": "hermes_agent",
                "action_type": "dispatch_hermes_prompt",
                "action_params": {
                    "profile": "cost_controller",
                    "prompt": "Perform daily token expenditure and budget status audit across all agent profiles."
                },
                "is_system": True,
                "is_active": True,
            }
        ]
    },
    {
        "name": "QA Review Routing on Task Status Change",
        "description": "Monitors tasks transitioning into 'review' status and automatically notifies the QA Auditor agent to review work output.",
        "trigger_type": "model_event",
        "execution_mode": "recurring",
        "trigger_model": "integration.AgentTask",
        "event_type": "field_changed",
        "trigger_field": "status",
        "target_value": "review",
        "is_system": True,
        "is_active": True,
        "actions": [
            {
                "name": "Dispatch QA Auditor Review",
                "sequence": 10,
                "action_category": "hermes_agent",
                "action_type": "dispatch_hermes_prompt",
                "action_params": {
                    "profile": "qa_auditor",
                    "prompt": "Evaluate task quality, output correctness, and compliance for task in review."
                },
                "is_system": True,
                "is_active": True,
            }
        ]
    },
    {
        "name": "Daily Budget Alert Notification",
        "description": "Periodic automated check dispatching Cost Controller to evaluate burn rate and budget variance.",
        "trigger_type": "time_based",
        "execution_mode": "recurring",
        "schedule_unit": "hours",
        "schedule_value": 12,
        "is_system": True,
        "is_active": True,
        "actions": [
            {
                "name": "Dispatch Budget Variance Check",
                "sequence": 10,
                "action_category": "hermes_agent",
                "action_type": "dispatch_hermes_prompt",
                "action_params": {
                    "profile": "cost_controller",
                    "prompt": "Audit recent spend reports and alert on budget variance exceeding 80%."
                },
                "is_system": True,
                "is_active": True,
            }
        ]
    },
    {
        "name": "Auto-Provision Profile on User Creation",
        "description": "Reified system lifecycle routine automatically ensuring every auth.User has an initialized Profile in the integration system.",
        "trigger_type": "model_event",
        "execution_mode": "recurring",
        "trigger_model": "auth.User",
        "event_type": "created",
        "is_system": True,
        "is_active": True,
        "actions": [
            {
                "name": "Provision Django User Profile",
                "sequence": 10,
                "action_category": "internal_app",
                "action_type": "provision_user_profile",
                "action_params": {},
                "is_system": True,
                "is_active": True,
            }
        ]
    },
]


class Command(BaseCommand):
    help = "Seeds default flagship automation triggers and action pipelines."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Seeding default automation triggers & pipelines..."))

        created_triggers = 0
        updated_triggers = 0
        created_actions = 0

        for item in DEFAULT_TRIGGERS:
            name = item["name"]
            actions_data = item.get("actions", [])
            trigger_fields = {k: v for k, v in item.items() if k != "actions"}

            trigger, created = AutomationTrigger.objects.update_or_create(
                name=name,
                defaults=trigger_fields
            )
            trigger.save()

            if created:
                created_triggers += 1
                self.stdout.write(self.style.SUCCESS(f"  ✓ Trigger: {name}"))
            else:
                updated_triggers += 1
                self.stdout.write(self.style.NOTICE(f"  • Trigger (updated): {name}"))

            # Reconcile legacy auto-generated action records from migration 0004
            legacy_actions = trigger.actions.filter(name=f"{trigger.name} - Action")
            for leg_act in legacy_actions:
                canonical_name = actions_data[0]["name"] if actions_data else None
                existing_canonical = trigger.actions.filter(name=canonical_name).exclude(id=leg_act.id).first() if canonical_name else None
                if existing_canonical:
                    AutomationLog.objects.filter(action=leg_act).update(action=existing_canonical)
                    leg_act.delete()
                elif canonical_name:
                    leg_act.name = canonical_name
                    for k, v in actions_data[0].items():
                        setattr(leg_act, k, v)
                    leg_act.save()

            for act_data in actions_data:
                act_name = act_data["name"]
                action, act_created = AutomationAction.objects.update_or_create(
                    trigger=trigger,
                    name=act_name,
                    defaults=act_data
                )
                if act_created:
                    created_actions += 1
                    self.stdout.write(self.style.SUCCESS(f"     ↳ Action created: {act_name}"))

        self.stdout.write(self.style.SUCCESS(
            f"\nAutomation seeding complete! ({created_triggers} triggers created, {updated_triggers} triggers updated, {created_actions} actions created)"
        ))
