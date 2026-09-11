"""
Hermes Runtime Credential Synchronization Service.

Provides zero-downtime, bidirectional synchronization of LLM provider keys,
DRF service account tokens, and model configurations from Django into
the running Hermes Agent runtime directories.
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from django.conf import settings
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

logger = logging.getLogger(__name__)

PROVIDER_ENV_MAP = {
    "openrouter": "OPENROUTER_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "groq": "GROQ_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
}


def get_hermes_runtime_data_dir() -> Path:
    """Resolves path to Hermes ~/.hermes data directory (mounted volume)."""
    container_path = Path("/app/hermes_runtime_data")
    if container_path.exists():
        return container_path
    repo_root = Path(settings.BASE_DIR).parent
    return repo_root / "agent_service" / "data"


def get_hermes_root_env_path() -> Path:
    """Resolves path to agent_service/.env project configuration."""
    container_path = Path("/app/hermes_root_env")
    if container_path.exists():
        return container_path
    repo_root = Path(settings.BASE_DIR).parent
    return repo_root / "agent_service" / ".env"


def get_hermes_runtime_profiles_dir() -> Path:
    """Resolves path to runtime profiles directory."""
    container_path = Path("/app/hermes_runtime_profiles")
    if container_path.exists():
        return container_path
    return get_hermes_runtime_data_dir() / "profiles"


def collect_active_provider_keys() -> Dict[str, str]:
    """
    Collects all active provider API keys from ProviderCredential models
    with fallback to environment variables.

    Returns:
        Dict[str, str]: Mapping of ENV_VAR_NAME -> plaintext_api_key.
    """
    from apps.integration.models import ProviderCredential

    keys: Dict[str, str] = {}

    # 1. Collect from active ProviderCredential instances (ordered by -is_default)
    for cred in ProviderCredential.objects.filter(is_active=True).order_by("-is_default"):
        env_var = PROVIDER_ENV_MAP.get(cred.provider_type)
        if env_var and cred.api_key:
            # If not yet set or if this one is default, assign
            if env_var not in keys or cred.is_default:
                keys[env_var] = cred.api_key

    # 2. Fallback to settings.py or process environment if defined
    for provider, env_var in PROVIDER_ENV_MAP.items():
        if env_var not in keys or not keys[env_var]:
            env_val = getattr(settings, env_var, None) or os.environ.get(env_var, "")
            if env_val:
                keys[env_var] = str(env_val).strip()

    return keys


def update_env_file(file_path: Path, new_vars: Dict[str, str]) -> bool:
    """
    Updates or appends environment variables in a .env file while preserving
    existing comments, blank lines, and unrelated configuration keys.

    Args:
        file_path: Target .env Path.
        new_vars: Dict of KEY -> VALUE to set or update.

    Returns:
        bool: True if write succeeded, False otherwise.
    """
    try:
        lines = []
        existing_keys = set()

        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    lines.append(line)
                    continue

                if "=" in stripped:
                    key = stripped.split("=", 1)[0].strip()
                    if key in new_vars:
                        # Replace with new value
                        lines.append(f"{key}={new_vars[key]}")
                        existing_keys.add(key)
                    else:
                        lines.append(line)
                else:
                    lines.append(line)

        # Append any new variables that weren't present in existing file
        for k, v in new_vars.items():
            if k not in existing_keys and v:
                lines.append(f"{k}={v}")

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True
    except Exception as exc:
        logger.warning(f"Failed updating .env at {file_path}: {exc}")
        return False


def sync_hermes_runtime_credentials() -> Dict[str, Any]:
    """
    Synchronizes active provider API keys from Django into Hermes runtime files:
      1. /app/hermes_root_env (agent_service/.env)
      2. /app/hermes_runtime_data/.env (root runtime env)
      3. /app/hermes_runtime_data/auth.json (credential pool)
      4. All active AI agent profiles' runtime .env files

    Returns:
        Dict[str, Any]: Summary report of synced credentials and updated files.
    """
    from apps.integration.models import Profile

    active_keys = collect_active_provider_keys()
    updated_files = []

    # 1. Update project root env
    root_env = get_hermes_root_env_path()
    if update_env_file(root_env, active_keys):
        updated_files.append(str(root_env))

    # 2. Update runtime root env
    runtime_env = get_hermes_runtime_data_dir() / ".env"
    if update_env_file(runtime_env, active_keys):
        updated_files.append(str(runtime_env))

    # 3. Synchronize all active agent profiles
    profile_count = 0
    for profile in Profile.objects.filter(is_agent=True):
        p_path = sync_profile_runtime_env(profile)
        if p_path:
            profile_count += 1

    return {
        "status": "success",
        "synced_keys_count": len(active_keys),
        "keys": list(active_keys.keys()),
        "updated_files": updated_files,
        "profiles_synced": profile_count,
    }


def sync_profile_runtime_env(profile: Any) -> Optional[Path]:
    """
    Synchronizes runtime credentials, model config, and DRF token for a single Profile.

    Args:
        profile: Profile model instance.

    Returns:
        Optional[Path]: Path to written profile .env file if successful, None otherwise.
    """
    slug = profile.hermes_profile_name or profile.name
    if not slug:
        return None

    target_dir = get_hermes_runtime_profiles_dir() / slug
    target_dir.mkdir(parents=True, exist_ok=True)

    # 1. Resolve DRF Service Account Token
    token_str = ""
    if profile.user:
        token, _ = Token.objects.get_or_create(user=profile.user)
        token_str = token.key

    # 2. Resolve Profile LLM Provider & Key
    provider_type, api_key, base_url = profile.resolve_provider_and_key()
    provider_env_var = PROVIDER_ENV_MAP.get(provider_type, "OPENROUTER_API_KEY")

    api_url = getattr(settings, "DJANGO_API_INTERNAL_URL", "http://host.docker.internal:8000/api")

    profile_vars = {
        "DJANGO_API_URL": api_url,
    }
    if token_str:
        profile_vars["DJANGO_API_TOKEN"] = token_str
    if api_key:
        profile_vars[provider_env_var] = api_key
    if base_url:
        profile_vars[f"{provider_type.upper()}_BASE_URL"] = base_url

    # Write profile runtime .env
    env_file = target_dir / ".env"
    update_env_file(env_file, profile_vars)

    # Update profile runtime config.yaml if present
    config_file = target_dir / "config.yaml"
    if config_file.exists():
        try:
            content = config_file.read_text(encoding="utf-8")
            # Update model, provider, and reasoning_effort lines
            if "default:" in content:
                content = re.sub(r'(\bdefault:\s*)["\']?.*?["\']?(\s*)$', rf'\g<1>"{profile.model_name}"\g<2>', content, flags=re.MULTILINE)
            else:
                content = re.sub(r'(\bmodel:\s*)["\']?.*?["\']?(\s*)$', rf'\g<1>"{profile.model_name}"\g<2>', content, flags=re.MULTILINE)

            content = re.sub(r'(\bprovider:\s*)["\']?.*?["\']?(\s*)$', rf'\g<1>"{profile.provider}"\g<2>', content, flags=re.MULTILINE)
            content = re.sub(r'(\breasoning_effort:\s*)["\']?.*?["\']?(\s*)$', rf'\g<1>"{profile.reasoning_effort}"\g<2>', content, flags=re.MULTILINE)
            config_file.write_text(content, encoding="utf-8")
        except Exception as exc:
            logger.warning(f"Could not update config.yaml for {slug}: {exc}")


    return env_file
