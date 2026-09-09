import json
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from rest_framework.authtoken.models import Token
from apps.integration.models import Profile

CORE_PROFILES = [
    {
        "name": "orchestrator",
        "display_name": "Chief of Staff / Orchestrator",
        "role": "orchestrator",
        "description": "Primary request intake, goal decomposition, Kanban workstream routing, and final executive synthesis.",
        "model_name": "google/gemini-2.5-flash",
        "provider": "openrouter",
        "reasoning_effort": "medium",
    },
    {
        "name": "cost_controller",
        "display_name": "Financial & Cost Controller",
        "role": "finance",
        "description": "Monitors token consumption, tracks operational budgets, audits expenses, and enforces spending limits.",
        "model_name": "google/gemini-2.5-flash",
        "provider": "openrouter",
        "reasoning_effort": "low",
    },
    {
        "name": "qa_auditor",
        "display_name": "Quality Assurance & Compliance Auditor",
        "role": "quality_assurance",
        "description": "Reviews task deliverables, verifies code and output integrity, audits compliance, and governs the review gate.",
        "model_name": "google/gemini-2.5-flash",
        "provider": "openrouter",
        "reasoning_effort": "high",
    },
    {
        "name": "comms_agent",
        "display_name": "Communications & Client Coordinator",
        "role": "communications",
        "description": "Manages customer interactions, drafts professional client emails and proposals, and coordinates schedules.",
        "model_name": "google/gemini-2.5-flash",
        "provider": "openrouter",
        "reasoning_effort": "low",
    },
    {
        "name": "archivist",
        "display_name": "Knowledge & Documentation Archivist",
        "role": "knowledge_management",
        "description": "Maintains system documentation, standard operating procedures (SOPs), knowledge bases, and corporate memory.",
        "model_name": "google/gemini-2.5-flash",
        "provider": "openrouter",
        "reasoning_effort": "medium",
    },
]

ROLE_GROUP_PERMISSIONS = {
    "orchestrator": {
        "group_name": "Agent_Orchestrator",
        "permissions": [
            ("integration", "agenttask", "add_agenttask"),
            ("integration", "agenttask", "change_agenttask"),
            ("integration", "agenttask", "view_agenttask"),
            ("integration", "profile", "view_profile"),
        ]
    },
    "cost_controller": {
        "group_name": "Agent_CostController",
        "permissions": [
            ("integration", "spendreport", "add_spendreport"),
            ("integration", "spendreport", "view_spendreport"),
            ("integration", "profile", "view_profile"),
        ]
    },
    "qa_auditor": {
        "group_name": "Agent_QAAuditor",
        "permissions": [
            ("integration", "agenttask", "change_agenttask"),
            ("integration", "agenttask", "view_agenttask"),
            ("integration", "profile", "view_profile"),
        ]
    },
    "comms_agent": {
        "group_name": "Agent_CommsAgent",
        "permissions": [
            ("integration", "agenttask", "view_agenttask"),
            ("integration", "profile", "view_profile"),
        ]
    },
    "archivist": {
        "group_name": "Agent_Archivist",
        "permissions": [
            ("integration", "agenttask", "view_agenttask"),
            ("integration", "profile", "view_profile"),
            ("integration", "spendreport", "view_spendreport"),
        ]
    },
}


class Command(BaseCommand):
    help = "Seeds core agent profiles, provisions RBAC Groups, creates bot User service accounts, and manages DRF Tokens."

    def add_arguments(self, parser):
        parser.add_argument(
            '--export-tokens',
            type=str,
            default=None,
            help="Path to export JSON mapping of profile names to authentication tokens."
        )

    def handle(self, *args, **options):
        self.stdout.write("Synchronizing RBAC Groups, Permissions, and Core Agent Profiles...")

        tokens_manifest = {}

        for p in CORE_PROFILES:
            name = p["name"]
            rbac_meta = ROLE_GROUP_PERMISSIONS.get(name, {})
            group_name = rbac_meta.get("group_name", f"Agent_{name.capitalize()}")
            perms_to_assign = rbac_meta.get("permissions", [])

            # 1. Create or retrieve Django Group
            group, _ = Group.objects.get_or_create(name=group_name)

            # 2. Assign model permissions to Group
            for app_label, model_name, codename in perms_to_assign:
                try:
                    content_type = ContentType.objects.get(app_label=app_label, model=model_name)
                    perm = Permission.objects.get(content_type=content_type, codename=codename)
                    group.permissions.add(perm)
                except (ContentType.DoesNotExist, Permission.DoesNotExist) as exc:
                    self.stdout.write(self.style.WARNING(f"  ! Could not assign permission {codename}: {exc}"))

            # 3. Create or update Bot Service User
            bot_username = f"bot_{name}"
            bot_user, user_created = User.objects.get_or_create(
                username=bot_username,
                defaults={
                    "email": f"{bot_username}@local.hermes",
                    "first_name": p["display_name"][:30],
                    "is_active": True,
                    "is_staff": False,
                }
            )
            bot_user.set_unusable_password()
            bot_user.is_active = True
            bot_user.groups.add(group)
            bot_user.save()

            # 4. Create or retrieve DRF API Token
            token, _ = Token.objects.get_or_create(user=bot_user)

            # 5. Create or update Profile linked to Bot User
            profile_defaults = dict(p)
            profile_defaults["user"] = bot_user
            profile_defaults["is_agent"] = True
            profile_defaults["user_type"] = "agent"
            profile_defaults["hermes_profile_name"] = name

            obj, created = Profile.objects.update_or_create(
                user=bot_user,
                defaults=profile_defaults
            )

            action = "Created" if created else "Updated"
            self.stdout.write(
                self.style.SUCCESS(
                    f"  ✓ {action} profile: {obj.display_name} -> User: {bot_username} | Group: {group_name} | Token: {token.key[:10]}..."
                )
            )

            tokens_manifest[name] = {
                "profile": name,
                "username": bot_username,
                "group": group_name,
                "token": token.key,
            }

        # 6. Optional token export to JSON file
        export_path = options.get("export_tokens")
        if export_path:
            try:
                with open(export_path, "w", encoding="utf-8") as f:
                    json.dump(tokens_manifest, f, indent=2)
                self.stdout.write(self.style.SUCCESS(f"\nTokens successfully exported to: {export_path}"))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"\nFailed to export tokens to {export_path}: {exc}"))

        self.stdout.write(self.style.SUCCESS("\nAll core profiles, service accounts, and RBAC groups synchronized."))
