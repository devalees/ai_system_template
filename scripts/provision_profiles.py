#!/usr/bin/env python3
"""
Automated Provisioning Script for Hermes Agent Profiles.

Synchronizes declarative profile definitions from `agent_service/profiles/`
into the running Hermes container runtime (`/root/.hermes/profiles/<name>/`).

Can be executed directly on the host or inside the hermes container.
"""

import os
import sys
import subprocess
from pathlib import Path

# ANSI colors for beautiful terminal output
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def is_inside_container() -> bool:
    """Checks if script is running inside the Hermes docker container."""
    return Path("/.dockerenv").exists() or (Path("/workspace").exists() and os.environ.get("HOSTNAME", "").startswith("hermes"))


def get_source_dir() -> Path:
    """Resolves the declarative source directory."""
    if is_inside_container():
        return Path("/workspace/profiles")
    repo_root = Path(__file__).resolve().parent.parent
    return repo_root / "agent_service" / "profiles"


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
    """Executes a command either directly inside container or via docker compose exec."""
    if is_inside_container():
        return subprocess.run(cmd, capture_output=True, text=True)
    
    # Host execution: delegate to docker compose exec
    repo_root = Path(__file__).resolve().parent.parent
    compose_file = repo_root / "agent_service" / "docker-compose.yml"
    docker_cmd = [
        "docker", "compose", "-f", str(compose_file), "exec", "-T", "hermes"
    ] + cmd
    return subprocess.run(docker_cmd, capture_output=True, text=True)


def parse_yaml_simple(file_path: Path) -> dict:
    """Lightweight key-value parser for simple profile.yaml files without external deps."""
    data = {}
    if not file_path.exists():
        return data
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, val = line.split(":", 1)
                data[key.strip()] = val.strip().strip('"\'')
    return data


def provision_all():
    """Provisions all profiles found in source_dir into Hermes runtime."""
    source_dir = get_source_dir()

    print(f"\n{BOLD}{CYAN}═══════════════════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}{CYAN}      Hermes Agent: Automated Profile Provisioner                      {RESET}")
    print(f"{BOLD}{CYAN}═══════════════════════════════════════════════════════════════════════{RESET}\n")

    if not source_dir.exists():
        print(f"{RED}Error: Profiles source directory not found at: {source_dir}{RESET}")
        sys.exit(1)

    # 1. Fetch currently registered profiles in Hermes
    list_res = run_cmd(["hermes", "profile", "list"])
    existing_profiles = {"default"}
    if list_res.returncode == 0:
        import re
        for line in list_res.stdout.splitlines():
            # Matches profile name in parentheses e.g. (orchestrator) or leading name
            match = re.search(r'\(([a-z0-9_-]+)\)', line)
            if match:
                existing_profiles.add(match.group(1))
            else:
                parts = line.strip().split()
                if parts and not line.startswith("Profile") and not line.startswith("─"):
                    existing_profiles.add(parts[0].lstrip("◆").strip())

    profiles_to_provision = [
        p for p in sorted(source_dir.iterdir())
        if p.is_dir() and (p / "profile.yaml").exists()
    ]

    print(f"{BLUE}Found {len(profiles_to_provision)} declarative profile definitions in {source_dir.name}/{RESET}\n")

    success_count = 0

    for profile_path in profiles_to_provision:
        profile_name = profile_path.name
        meta = parse_yaml_simple(profile_path / "profile.yaml")
        display_name = meta.get("display_name", profile_name)
        description = meta.get("description", "")

        print(f"{BOLD}▶ Provisioning Profile: {GREEN}{profile_name}{RESET} ({display_name})")

        # Step A: Create profile in Hermes if missing
        if profile_name not in existing_profiles:
            print(f"  • Creating profile in Hermes engine...")
            create_cmd = ["hermes", "profile", "create", profile_name]
            if description:
                create_cmd.extend(["--description", description])
            c_res = run_cmd(create_cmd)
            if c_res.returncode != 0 and "already exists" not in c_res.stderr:
                print(f"    {YELLOW}Warning during creation: {c_res.stderr.strip()}{RESET}")
            else:
                print(f"    {GREEN}✓ Profile structure initialized.{RESET}")
        else:
            print(f"    {BLUE}✓ Profile already registered in engine.{RESET}")

        # Step B: Synchronize declarative files inside the container
        # /workspace/profiles/<profile_name>/ -> /root/.hermes/profiles/<profile_name>/
        sync_script = f"""
import os, shutil
src = '/workspace/profiles/{profile_name}'
dst = '/root/.hermes/profiles/{profile_name}'
os.makedirs(dst, exist_ok=True)
for f in ['SOUL.md', 'config.yaml', 'profile.yaml']:
    s = os.path.join(src, f)
    if os.path.exists(s):
        shutil.copy2(s, os.path.join(dst, f))
"""
        sync_res = run_cmd(["python", "-c", sync_script])
        if sync_res.returncode == 0:
            print(f"    {GREEN}✓ Synced SOUL.md, config.yaml, and profile.yaml.{RESET}")
        else:
            print(f"    {YELLOW}Warning syncing files: {sync_res.stderr.strip()}{RESET}")

        # Step C: Ensure description is updated in Hermes profile metadata
        if description:
            run_cmd(["hermes", "profile", "describe", profile_name, "--text", description])

        success_count += 1
        print()

    # Step D: Synchronize Custom Skills into Hermes Runtime
    print(f"\n{BOLD}{BLUE}▶ Synchronizing custom skills into Hermes runtime...{RESET}")
    skill_sync_script = """
import os, shutil
src_root = '/workspace/skills'
dst_root = '/root/.hermes/skills/custom'
os.makedirs(dst_root, exist_ok=True)
count = 0
if os.path.exists(src_root):
    for skill in os.listdir(src_root):
        s_path = os.path.join(src_root, skill)
        if os.path.isdir(s_path):
            d_path = os.path.join(dst_root, skill)
            if os.path.exists(d_path):
                shutil.rmtree(d_path)
            shutil.copytree(s_path, d_path)
            count += 1
print(f"Synced {count} custom skills.")
"""
    sk_res = run_cmd(["python", "-c", skill_sync_script])
    if sk_res.returncode == 0:
        print(f"  {GREEN}✓ {sk_res.stdout.strip()}{RESET}")
    else:
        print(f"  {YELLOW}Warning syncing skills: {sk_res.stderr.strip()}{RESET}")

    # Summary table
    print(f"{BOLD}{GREEN}═══════════════════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}{GREEN}  Successfully Provisioned {success_count}/{len(profiles_to_provision)} Profiles!{RESET}")
    print(f"{BOLD}{GREEN}═══════════════════════════════════════════════════════════════════════{RESET}\n")

    # Display updated profile list
    verify_res = run_cmd(["hermes", "profile", "list"])
    if verify_res.returncode == 0:
        print(f"{CYAN}Active Hermes Profiles Status:{RESET}")
        print(verify_res.stdout)


if __name__ == "__main__":
    provision_all()
