from django.core.management.base import BaseCommand
from apps.integration.models import AgentProfile

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

class Command(BaseCommand):
    help = "Seeds or updates the 5 universal core agent profiles in the PostgreSQL database."

    def handle(self, *args, **options):
        self.stdout.write("Synchronizing core agent profiles into database...")
        for p in CORE_PROFILES:
            obj, created = AgentProfile.objects.update_or_create(
                name=p["name"],
                defaults=p
            )
            action = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"  ✓ {action} profile: {obj.display_name} ({obj.name})"))
        self.stdout.write(self.style.SUCCESS("All core profiles successfully seeded."))
