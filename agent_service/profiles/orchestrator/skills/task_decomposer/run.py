#!/usr/bin/env python3
"""
Task Decomposer Helper Script.

Used by the Orchestrator to validate task dependency graphs, map workloads
to specialist department heads, and register tasks in the Django AgentTask registry.
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error
from typing import Dict, List, Any


VALID_PROFILES = {
    "orchestrator": "Chief of Staff / Triage & Decomposition",
    "cost_controller": "Financial Controller & Budget Monitor",
    "qa_auditor": "Quality Assurance & Compliance Gatekeeper",
    "comms_agent": "Client Communications Coordinator",
    "archivist": "Knowledge & Documentation Archivist",
}

DEFAULT_TASK_TEMPLATES = {
    "audit_spend": {
        "title": "Audit Token Consumption & Spending Limits",
        "profile": "cost_controller",
        "description": "Execute cost_monitor skill to inspect session SQLite logs and verify daily budget.",
    },
    "qa_review": {
        "title": "Verify Deliverable Quality & Security Compliance",
        "profile": "qa_auditor",
        "description": "Execute output_validator skill to compile AST, detect leaked credentials, and emit verdict.",
    },
    "client_update": {
        "title": "Draft Client Milestone Progress Update",
        "profile": "comms_agent",
        "description": "Format completed deliverables into professional client-facing summary.",
    },
    "archive_docs": {
        "title": "Archive Learnings & Update Project Wiki",
        "profile": "archivist",
        "description": "Extract SOPs and synchronize system architecture documentation in docs/ai_wiki/.",
    },
}


def topological_sort(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Orders tasks sequentially based on dependency prerequisites."""
    task_map = {t["id"]: t for t in tasks}
    visited = set()
    visiting = set()
    ordered = []

    def dfs(node_id: str):
        if node_id in visiting:
            raise ValueError(f"Cyclic dependency detected involving task '{node_id}'")
        if node_id not in visited:
            visiting.add(node_id)
            for dep in task_map.get(node_id, {}).get("dependencies", []):
                if dep in task_map:
                    dfs(dep)
            visiting.remove(node_id)
            visited.add(node_id)
            ordered.append(task_map[node_id])

    for task in tasks:
        if task["id"] not in visited:
            dfs(task["id"])

    return ordered


def build_default_pipeline(goal: str) -> List[Dict[str, Any]]:
    """Constructs a structured 4-stage department pipeline for a given objective."""
    return [
        {
            "id": "task_1_execute",
            "name": f"Execute: {goal}",
            "assigned_profile": "orchestrator",
            "dependencies": [],
            "deliverable": "Working feature deliverables or initial artifacts.",
        },
        {
            "id": "task_2_qa",
            "name": f"QA Review: {goal}",
            "assigned_profile": "qa_auditor",
            "dependencies": ["task_1_execute"],
            "deliverable": "Quality score (0-100) and signed review verdict.",
        },
        {
            "id": "task_3_cost",
            "name": f"Spend Audit: {goal}",
            "assigned_profile": "cost_controller",
            "dependencies": ["task_1_execute"],
            "deliverable": "Token consumption ledger and budget cap verification.",
        },
        {
            "id": "task_4_archive",
            "name": f"Document & Archive: {goal}",
            "assigned_profile": "archivist",
            "dependencies": ["task_2_qa"],
            "deliverable": "Wiki synchronization and SOP extraction in docs/ai_wiki/.",
        },
        {
            "id": "task_5_comms",
            "name": f"Client Notification: {goal}",
            "assigned_profile": "comms_agent",
            "dependencies": ["task_2_qa", "task_3_cost"],
            "deliverable": "Executive summary sent to client via active notification channels.",
        },
    ]


def submit_tasks_to_django(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Submits validated tasks to Django /api/tasks/ endpoint using token auth."""
    api_url = os.environ.get("DJANGO_API_URL", "http://host.docker.internal:8000/api").rstrip("/")
    token = os.environ.get("DJANGO_API_TOKEN", "")

    if not token:
        print("[WARN] DJANGO_API_TOKEN not found in environment. Running in offline/dry-run mode.")
        return []

    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json",
    }

    results = []
    for task in tasks:
        payload = {
            "task_name": task["name"],
            "status": "pending",
        }
        req = urllib.request.Request(
            f"{api_url}/tasks/",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                results.append(data)
                print(f"  ✓ Registered task #{data.get('id')} ({task['name']}) -> {task['assigned_profile']}")
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8")
            print(f"  ✕ Failed registering task '{task['name']}': HTTP {e.code} - {err}")
        except Exception as e:
            print(f"  ✕ Error: {e}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Orchestrator Task Decomposer Helper")
    parser.add_argument("--goal", type=str, help="High-level goal to decompose")
    parser.add_argument("--plan-file", type=str, help="Path to custom JSON plan file")
    parser.add_argument("--submit", action="store_true", help="Submit tasks to Django backend")
    parser.add_argument("--dry-run", action="store_true", help="Validate and display without submitting")
    parser.add_argument("--json", action="store_true", help="Output raw JSON plan")

    args = parser.parse_args()

    if not args.goal and not args.plan_file:
        parser.print_help()
        sys.exit(1)

    if args.plan_file:
        with open(args.plan_file, "r", encoding="utf-8") as f:
            raw_tasks = json.load(f)
    else:
        raw_tasks = build_default_pipeline(args.goal)

    # Validate task profiles
    for t in raw_tasks:
        p = t.get("assigned_profile")
        if p not in VALID_PROFILES:
            print(f"[ERROR] Invalid profile '{p}' in task '{t.get('name')}'. Valid: {list(VALID_PROFILES.keys())}")
            sys.exit(1)

    # Resolve dependencies
    try:
        ordered_tasks = topological_sort(raw_tasks)
    except ValueError as e:
        print(f"[ERROR] Dependency error: {e}")
        sys.exit(1)

    if args.json:
        print(json.dumps(ordered_tasks, indent=2))
        return

    print("\n═══════════════════════════════════════════════════════════════════════")
    print("      Orchestrator: Decomposed Execution Plan Graph                     ")
    print("═══════════════════════════════════════════════════════════════════════\n")
    if args.goal:
        print(f"🎯 Objective: {args.goal}\n")

    print(f"Total Sub-tasks: {len(ordered_tasks)}")
    print("Execution Sequence:")
    for idx, t in enumerate(ordered_tasks, 1):
        deps = f" (Depends on: {', '.join(t['dependencies'])})" if t['dependencies'] else " (Root task)"
        print(f"  {idx}. [{t['assigned_profile'].upper()}] {t['name']}{deps}")
        print(f"     Deliverable: {t.get('deliverable', 'N/A')}")

    print()

    if args.submit:
        print("▶ Submitting tasks to Django backend...")
        submit_tasks_to_django(ordered_tasks)
        print("Done.")
    elif args.dry_run:
        print("✓ Dry-run completed. All dependency links and department profiles verified.")


if __name__ == "__main__":
    main()
