"""
Pre-Registered Flagship Action Handlers for Automation Engine.
"""

import os
import shutil
from pathlib import Path
from typing import Any, Dict
import requests
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

from .registry import register_action


@register_action(
    name="provision_hermes_profile",
    category="hermes_agent",
    description="Provisions Hermes Agent profile directory, generates DRF Token, and injects runtime .env",
    schema={
        "username": "Target Django username (e.g. bot_analyst)",
        "profile_name": "Slug of the Hermes profile (e.g. analyst)",
        "display_name": "Human-readable profile name",
        "role": "Functional role of the profile",
        "provider": "LLM Provider (default: openrouter)",
        "model_name": "Model identifier (default: google/gemini-2.5-flash)",
    },
    presets=[
        {
            "name": "🤖 Provision Profile from Trigger Context",
            "description": "Uses trigger user/profile context to provision runtime files and token.",
            "params": {
                "username": "{{username}}",
                "profile_name": "{{username}}",
                "role": "specialist",
                "provider": "openrouter",
                "model_name": "google/gemini-2.5-flash"
            }
        }
    ]
)
def provision_hermes_profile_action(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Action Handler: Dynamic Hermes Profile & Token Auto-Provisioning.
    Automatically fires when an Agent User is created or updated in Django.
    """
    username = context.get('username')
    profile_name = context.get('profile_name') or context.get('hermes_profile_name')

    if not username and not profile_name:
        raise ValueError("Context must contain 'username' or 'profile_name'.")

    # Resolve User
    user = None
    if username:
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            pass

    if not user and profile_name:
        try:
            user = User.objects.get(username=f"bot_{profile_name}")
        except User.DoesNotExist:
            try:
                user = User.objects.get(username=profile_name)
            except User.DoesNotExist:
                pass

    if not user:
        raise ValueError(f"Could not locate Django user for context: {context}")

    # Resolve profile slug
    slug = profile_name or user.username.removeprefix("bot_")
    display_name = context.get('display_name') or getattr(user, 'profile', None) and user.profile.display_name or slug.replace('_', ' ').title()
    role = context.get('role') or getattr(user, 'profile', None) and user.profile.role or 'specialist'
    provider = context.get('provider') or getattr(user, 'profile', None) and user.profile.provider or 'openrouter'
    model_name = context.get('model_name') or getattr(user, 'profile', None) and user.profile.model_name or 'google/gemini-2.5-flash'
    reasoning_effort = context.get('reasoning_effort') or getattr(user, 'profile', None) and user.profile.reasoning_effort or 'medium'

    # 1. Generate or fetch DRF Auth Token
    token, _ = Token.objects.get_or_create(user=user)

    # 2. Synchronize Declarative Files (/app/agent_profiles/<slug>/)
    declarative_dir = Path("/app/agent_profiles") / slug
    declarative_dir.mkdir(parents=True, exist_ok=True)

    profile_yaml_path = declarative_dir / "profile.yaml"
    if not profile_yaml_path.exists():
        profile_yaml_content = f"""name: {slug}
display_name: "{display_name}"
role: "{role}"
description: "Dynamically provisioned agent profile for {display_name}."
default_model: "{model_name}"
default_provider: "{provider}"
created_by: "apps.automation"
"""
        profile_yaml_path.write_text(profile_yaml_content, encoding='utf-8')

    config_yaml_path = declarative_dir / "config.yaml"
    if not config_yaml_path.exists():
        config_yaml_content = f"""model: "{model_name}"
provider: "{provider}"
reasoning_effort: "{reasoning_effort}"
temperature: 0.7
max_tokens: 4096
"""
        config_yaml_path.write_text(config_yaml_content, encoding='utf-8')

    soul_md_path = declarative_dir / "SOUL.md"
    if not soul_md_path.exists():
        soul_md_content = f"""# Persona: {display_name}

You are **{display_name}**, a specialized autonomous agent operating within the AI System Template.
- Role: {role}
- Primary Model: {model_name}
- Reasoning Effort: {reasoning_effort}

Be direct, objective, concise, and rigorous. Execute assigned tasks with empirical verification.
"""
        soul_md_path.write_text(soul_md_content, encoding='utf-8')

    # 3. Synchronize Runtime Directory & Inject Credentials (/app/hermes_runtime_profiles/<slug>/)
    runtime_dir = Path("/app/hermes_runtime_profiles") / slug
    runtime_dir.mkdir(parents=True, exist_ok=True)

    # Copy declarative files into runtime
    for fname in ["profile.yaml", "config.yaml", "SOUL.md"]:
        src = declarative_dir / fname
        dst = runtime_dir / fname
        if src.exists():
            shutil.copy2(src, dst)

    # Write .env with Django API Token
    env_file = runtime_dir / ".env"
    api_url = getattr(settings, 'DJANGO_API_INTERNAL_URL', 'http://host.docker.internal:8000/api')
    env_lines = [
        f"DJANGO_API_URL={api_url}\n",
        f"DJANGO_API_TOKEN={token.key}\n",
    ]
    env_file.write_text("".join(env_lines), encoding='utf-8')

    return {
        "status": "success",
        "profile_slug": slug,
        "display_name": display_name,
        "token_prefix": f"{token.key[:8]}...",
        "declarative_path": str(declarative_dir),
        "runtime_path": str(runtime_dir),
        "env_configured": True,
    }


@register_action(
    name="dispatch_hermes_prompt",
    category="hermes_agent",
    description="Dispatches a prompt/message to the Hermes Agent Gateway API",
    schema={
        "prompt": "The prompt or instruction string to dispatch",
        "profile": "Optional Hermes profile name (e.g. orchestrator)",
        "task_id": "Optional Django AgentTask ID",
    },
    presets=[
        {
            "name": "⚡ General Agent Task Execution",
            "description": "Dispatches an instruction with trigger task variables to an agent.",
            "params": {
                "profile": "orchestrator",
                "prompt": "Execute task #{{pk}} ('{{task_name}}') and report back with findings."
            }
        }
    ]
)
def dispatch_hermes_prompt_action(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Action Handler: Dispatches prompt or task to Hermes Gateway API.
    """
    gateway_url = getattr(settings, 'HERMES_GATEWAY_URL', 'http://hermes:8642').rstrip('/')
    prompt = context.get('prompt') or context.get('description', '')
    profile = context.get('profile') or 'orchestrator'

    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "profile": profile,
    }
    headers = {"Content-Type": "application/json"}
    api_key = getattr(settings, 'HERMES_API_KEY', '')
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    timeout_seconds = getattr(settings, 'HERMES_REQUEST_TIMEOUT', 120)
    try:
        resp = requests.post(f"{gateway_url}/v1/chat/completions", json=payload, headers=headers, timeout=(10, timeout_seconds))
        is_error = resp.status_code >= 400
        res_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text[:300]
        err_detail = ""
        if is_error:
            if isinstance(res_data, dict):
                err_detail = res_data.get("error", {}).get("message") or str(res_data.get("error")) or f"HTTP {resp.status_code}"
            else:
                err_detail = str(res_data)

        return {
            "status": "error" if is_error else "dispatched",
            "http_status": resp.status_code,
            "response": res_data,
            "error": err_detail,
        }
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "gateway_url": gateway_url,
        }


@register_action(
    name="generic_webhook",
    category="external_webhook",
    description="Dispatches outbound HTTP POST to an external webhook URL",
    schema={
        "url": "Target destination URL (https://...)",
        "payload": "Dictionary payload to send",
        "headers": "Optional dictionary of custom HTTP headers",
    },
    presets=[
        {
            "name": "🌐 Dispatch Event Payload to Webhook",
            "description": "Sends event data and record details to external service.",
            "params": {
                "url": "https://webhook.site/your-endpoint",
                "payload": {
                    "event": "{{event}}",
                    "model": "{{model}}",
                    "pk": "{{pk}}",
                    "status": "{{status}}"
                }
            }
        }
    ]
)
def generic_webhook_action(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Action Handler: Dispatches an outbound webhook.
    """
    url = context.get('url')
    if not url:
        raise ValueError("Missing 'url' in generic_webhook context.")

    payload = context.get('payload', {})
    headers = context.get('headers', {"Content-Type": "application/json"})

    resp = requests.post(url, json=payload, headers=headers, timeout=15)
    return {
        "status": "success" if resp.status_code < 400 else "failed",
        "status_code": resp.status_code,
        "response_text": resp.text[:300],
    }


@register_action(
    name="provision_user_profile",
    category="internal_app",
    description="Provisions or updates a 1-to-1 Profile for a Django User, with automatic AI Agent bot detection",
    schema={
        "username": "Django User username (or pk in context)",
    },
    presets=[
        {
            "name": "👤 Auto-Provision User Profile",
            "description": "Automatically provisions linked Profile for created or updated User.",
            "params": {
                "username": "{{username}}"
            }
        }
    ]
)
def provision_user_profile_action(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Action Handler: Reified User Profile Auto-Provisioning.
    Automatically ensures every auth.User has an initialized Profile in integration.
    """
    from apps.integration.models import Profile

    username = context.get('username')
    user = None
    if username:
        user = User.objects.filter(username=username).first()
    if not user and context.get('pk'):
        user = User.objects.filter(pk=context.get('pk')).first()
    if not user:
        raise ValueError(f"User not found for context: {context}")

    is_bot = user.username.startswith("bot_")
    profile_slug = user.username.removeprefix("bot_") if is_bot else ""
    profile, created = Profile.objects.get_or_create(
        user=user,
        defaults={
            "display_name": user.get_full_name() or user.username,
            "name": profile_slug or user.username,
            "hermes_profile_name": profile_slug,
            "is_agent": is_bot,
            "user_type": "agent" if is_bot else ("human" if user.is_staff else "client"),
        }
    )
    return {
        "status": "success",
        "profile_id": str(profile.id),
        "username": user.username,
        "is_agent": profile.is_agent,
        "user_type": profile.user_type,
        "created": created,
    }

