"""
Hermes Agent Profile Discovery Service.

Scans declarative and runtime Hermes profile directories to provide
real-time profile metadata for Django Admin dropdowns and the REST API.
"""

import os
from pathlib import Path
from typing import Any, Dict, List


def parse_yaml_light(file_path: Path) -> Dict[str, str]:
    """Lightweight key-value YAML parser without hard external dependencies."""
    data: Dict[str, str] = {}
    if not file_path.exists():
        return data
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line:
                    key, val = line.split(":", 1)
                    clean_val = val.strip().strip('"\'')
                    data[key.strip()] = clean_val
    except Exception:
        pass
    return data


class HermesDiscoveryService:
    """Discovers available Hermes Agent profiles in real time."""

    SEARCH_PATHS = [
        Path("/app/agent_profiles"),
        Path("/app/hermes_runtime_profiles"),
        Path(__file__).resolve().parent.parent.parent.parent / "agent_service" / "profiles",
    ]

    @classmethod
    def get_profiles_directory(cls) -> Path:
        """Finds the first existing profiles directory."""
        for path in cls.SEARCH_PATHS:
            if path.exists() and path.is_dir():
                return path
        return Path("/app/agent_profiles")

    @classmethod
    def list_available_profiles(cls) -> List[Dict[str, Any]]:
        """
        Discovers and returns all available Hermes engine profiles.

        Returns:
            List of profile metadata dictionaries with name, display_name,
            role, description, and suggested model.
        """
        base_dir = cls.get_profiles_directory()
        profiles = []

        if not base_dir.exists():
            return profiles

        for entry in sorted(base_dir.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                profile_yaml = parse_yaml_light(entry / "profile.yaml")
                config_yaml = parse_yaml_light(entry / "config.yaml")

                display_name = profile_yaml.get("display_name") or entry.name.replace("_", " ").title()
                role = profile_yaml.get("role") or entry.name
                description = profile_yaml.get("description", "")
                default_model = config_yaml.get("model") or "google/gemini-2.5-flash"
                default_provider = "openrouter"

                profiles.append({
                    "name": entry.name,
                    "display_name": display_name,
                    "role": role,
                    "description": description,
                    "default_model": default_model,
                    "default_provider": default_provider,
                })

        return profiles
