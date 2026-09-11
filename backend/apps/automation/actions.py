"""
Pre-Registered Flagship Action Handlers for Automation Engine.
"""

import os
import shutil
import time
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
    Action Handler: Dispatches prompt or task to Hermes Gateway API with pre-execution
    budget gating and post-execution direct token spend accounting.
    """
    from django.utils import timezone
    from django.db.models import Sum
    from apps.core.config import get_setting
    from apps.integration.models import SpendReport, Profile, AgentTask

    # 1. Pre-Execution Budget Ceiling Gate
    daily_budget = float(get_setting('integration.DAILY_BUDGET_CAP_USD', default=50.0))
    today = timezone.now().date()
    today_spend = SpendReport.objects.filter(created_at__date=today).aggregate(total=Sum('total_cost_usd'))['total'] or 0.0
    if float(today_spend) >= daily_budget:
        return {
            "status": "budget_exceeded",
            "error": f"Daily token budget cap of ${daily_budget:.2f} USD reached (current: ${float(today_spend):.2f} USD). Execution aborted.",
            "today_spend_usd": float(today_spend),
            "daily_budget_usd": daily_budget,
        }

    gateway_url = getattr(settings, 'HERMES_GATEWAY_URL', 'http://hermes:8642').rstrip('/')
    prompt = context.get('prompt') or context.get('description', '')
    profile = context.get('profile') or 'orchestrator'

    # Support deliverable fallback from upstream pipeline step
    if not prompt and context.get('deliverable'):
        prompt = context['deliverable']

    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "profile": profile,
    }

    reasoning_effort = context.get('reasoning_effort')
    if reasoning_effort and reasoning_effort != "inherit":
        payload["reasoning_effort"] = reasoning_effort

    headers = {"Content-Type": "application/json"}
    api_key = getattr(settings, 'HERMES_API_KEY', '')
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    timeout_seconds = get_setting('automation.HERMES_REQUEST_TIMEOUT', default=getattr(settings, 'HERMES_REQUEST_TIMEOUT', 120))
    max_retries = int(context.get('max_retries', 2))
    last_resp = None
    last_exc = None

    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(f"{gateway_url}/v1/chat/completions", json=payload, headers=headers, timeout=(10, timeout_seconds))
            last_resp = resp
            if resp.status_code < 400:
                res_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"text": resp.text[:500]}

                # 2. Extract Deliverable and Token Accounting
                assistant_deliverable = ""
                if isinstance(res_data, dict):
                    choices = res_data.get("choices", [])
                    if choices and isinstance(choices, list):
                        assistant_deliverable = choices[0].get("message", {}).get("content", "")

                usage = res_data.get("usage", {}) if isinstance(res_data, dict) else {}
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
                # Standard estimation: $0.15/1M input, $0.60/1M output
                cost_usd = round((prompt_tokens * 0.00000015) + (completion_tokens * 0.00000060), 6)

                # 3. Post-Execution Direct Spend Tracking into SpendReport
                profile_obj = Profile.objects.filter(hermes_profile_name=profile).first() or Profile.objects.filter(name=profile).first()
                new_spend = float(today_spend) + cost_usd
                budget_status = "EXCEEDED" if new_spend >= daily_budget else ("WARNING" if new_spend >= (daily_budget * 0.8) else "OK")

                SpendReport.objects.create(
                    profile=profile_obj,
                    reported_by=profile,
                    total_api_calls=1,
                    total_tokens=total_tokens,
                    total_cost_usd=cost_usd,
                    daily_budget_usd=daily_budget,
                    budget_status=budget_status,
                    payload={
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens,
                        "model": res_data.get("model", "") if isinstance(res_data, dict) else "",
                    }
                )

                # 4. Attach to AgentTask if provided
                task_id = context.get('task_id')
                if task_id:
                    try:
                        task = AgentTask.objects.filter(id=task_id).first()
                        if task:
                            task.tokens_used = total_tokens
                            task.cost_usd = cost_usd
                            task.output_result = res_data if isinstance(res_data, dict) else {"raw": str(res_data)}
                            task.status = "completed"
                            task.completed_at = timezone.now()
                            task.save(update_fields=['tokens_used', 'cost_usd', 'output_result', 'status', 'completed_at'])
                    except Exception:
                        pass

                return {
                    "status": "dispatched",
                    "http_status": resp.status_code,
                    "response": res_data,
                    "deliverable": assistant_deliverable,
                    "tokens_used": total_tokens,
                    "cost_usd": cost_usd,
                    "budget_status": budget_status,
                    "attempts": attempt + 1,
                }
            if resp.status_code not in (502, 503, 504):
                break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            last_exc = exc

        if attempt < max_retries:
            time.sleep(1 * (2 ** attempt))

    if last_exc and not last_resp:
        return {
            "status": "error",
            "error": str(last_exc),
            "gateway_url": gateway_url,
            "attempts": max_retries + 1,
        }

    status_code = last_resp.status_code if last_resp else 500
    res_data = last_resp.json() if last_resp and last_resp.headers.get("content-type", "").startswith("application/json") else (last_resp.text[:300] if last_resp else "")
    err_detail = ""
    if isinstance(res_data, dict):
        err_detail = res_data.get("error", {}).get("message") or str(res_data.get("error")) or f"HTTP {status_code}"
    else:
        err_detail = str(res_data)

    return {
        "status": "error",
        "http_status": status_code,
        "response": res_data,
        "error": err_detail,
        "attempts": max_retries + 1,
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
    Action Handler: Dispatches an outbound webhook with automatic retries on transient errors.
    """
    url = context.get('url')
    if not url:
        raise ValueError("Missing 'url' in generic_webhook context.")

    payload = context.get('payload', {})
    headers = context.get('headers', {"Content-Type": "application/json"})
    max_retries = int(context.get('max_retries', 2))

    last_resp = None
    last_exc = None

    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            last_resp = resp
            if resp.status_code < 400:
                return {
                    "status": "success",
                    "status_code": resp.status_code,
                    "response_text": resp.text[:300],
                    "attempts": attempt + 1,
                }
            if resp.status_code not in (502, 503, 504):
                break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            last_exc = exc

        if attempt < max_retries:
            time.sleep(1 * (2 ** attempt))

    if last_exc and not last_resp:
        return {
            "status": "failed",
            "error": str(last_exc),
            "attempts": max_retries + 1,
        }

    status_code = last_resp.status_code if last_resp else 500
    return {
        "status": "success" if status_code < 400 else "failed",
        "status_code": status_code,
        "response_text": last_resp.text[:300] if last_resp else "",
        "attempts": max_retries + 1,
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


@register_action(
    name="send_notification",
    category="notifications",
    description="Dispatches multi-channel notification to a target user recipient",
    schema={
        "recipient_username": "Username of target user (e.g. {{username}} or admin)",
        "title": "Notification title (e.g. Task {{task_name}} Completed)",
        "message": "Notification message body",
        "level": "Level: info, success, warning, or error (default: info)",
        "action_url": "Optional action URL link",
    },
    presets=[
        {
            "name": "🔔 Send System Notification to Trigger User",
            "description": "Sends notification alert to the user in trigger context.",
            "params": {
                "recipient_username": "{{username}}",
                "title": "System Alert",
                "message": "Action executed successfully for record {{pk}}.",
                "level": "info",
                "action_url": ""
            }
        }
    ]
)
def send_notification_action(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Action Handler: Send Multi-Channel Notification.
    """
    from apps.notifications.dispatcher import NotificationDispatcher
    from apps.notifications.models import Notification

    recipient_username = context.get('recipient_username') or context.get('username')
    user = None
    if recipient_username:
        user = User.objects.filter(username=recipient_username).first()
    if not user and context.get('created_by_id'):
        user = User.objects.filter(pk=context.get('created_by_id')).first()
    if not user and context.get('user_id'):
        user = User.objects.filter(pk=context.get('user_id')).first()

    if not user:
        raise ValueError(f"Could not resolve recipient user for context: {context}")

    title = context.get('title') or "System Notification"
    message = context.get('message') or "An automated system action was executed."
    level = context.get('level') or Notification.LEVEL_INFO
    action_url = context.get('action_url') or ""

    results = NotificationDispatcher.send(
        recipient=user,
        title=title,
        message=message,
        level=level,
        action_url=action_url,
        extra_data=context,
    )
    return {
        "status": "success",
        "recipient": user.username,
        "results": results,
    }


