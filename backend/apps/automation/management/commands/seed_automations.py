"""
Management command to seed default/flagship automation rules.
"""

from django.core.management.base import BaseCommand
from apps.automation.models import AutomationRule


DEFAULT_RULES = [
    {
        "name": "Auto-Provision Hermes Profile on Agent User Creation",
        "description": "Automatically generates DRF auth token, creates declarative configuration files, and injects runtime .env into the Hermes Agent container whenever an Agent User is created or updated in Django.",
        "trigger_type": "model_event",
        "execution_mode": "recurring",
        "target_model": "integration.Profile",
        "event_type": "any",
        "filter_conditions": {"is_agent": True},
        "action_category": "hermes_agent",
        "action_type": "provision_hermes_profile",
        "action_params": {},
        "is_active": True,
    },
    {
        "name": "Daily Spend & Token Audit Dispatch",
        "description": "Periodic scheduled routine dispatching the Cost Controller agent to audit token consumption and operational spend across all profile state databases every 24 hours.",
        "trigger_type": "time_based",
        "execution_mode": "recurring",
        "schedule_unit": "hours",
        "schedule_value": 24,
        "action_category": "hermes_agent",
        "action_type": "dispatch_hermes_prompt",
        "action_params": {
            "profile": "cost_controller",
            "prompt": "Perform daily token expenditure and budget status audit across all agent profiles."
        },
        "is_active": True,
    },
]


class Command(BaseCommand):
    help = "Seeds default flagship automation rules for Hermes profiles and scheduling."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Seeding default automation rules..."))

        created_count = 0
        updated_count = 0

        for rule_data in DEFAULT_RULES:
            name = rule_data["name"]
            rule, created = AutomationRule.objects.update_or_create(
                name=name,
                defaults=rule_data
            )
            # Trigger save() to ensure signals and Celery Beat schedules are synchronized
            rule.save()

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"  ✓ Created rule: {name}"))
            else:
                updated_count += 1
                self.stdout.write(self.style.NOTICE(f"  • Updated rule: {name}"))

        self.stdout.write(self.style.SUCCESS(f"\nAutomation seeding complete! ({created_count} created, {updated_count} updated)"))
