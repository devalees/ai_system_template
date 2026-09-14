"""Action handler for dispatching external HTTP webhooks with JSON payloads."""

import json
import logging
from typing import Optional, Dict, Any
from jinja2 import Template
import httpx
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from modules.base.automated_actions.handlers.base import BaseActionHandler, ActionContext

logger = logging.getLogger("sovereign.automated_actions.webhook")


class InvokeWebhookActionConfig(BaseModel):
    """Configuration schema for Invoke Webhook action."""
    url: str = Field(..., description="Target external HTTP/HTTPS webhook URL")
    method: str = Field("POST", description="HTTP method: 'POST', 'PUT', 'PATCH'")
    headers: Dict[str, str] = Field(default_factory=dict, description="Custom HTTP request headers")
    payload_template: Optional[Dict[str, Any]] = Field(None, description="Custom JSON payload template (defaults to record data + event context)")
    timeout_seconds: float = Field(10.0, ge=1.0, le=60.0, description="Request timeout in seconds")
    secret_token: Optional[str] = Field(None, description="Optional secret/bearer token injected into Authorization header")


class InvokeWebhookActionHandler(BaseActionHandler):
    """Action handler that dispatches external webhooks via HTTP client."""

    action_type = "invoke_webhook"
    title = "Invoke External Webhook"
    description = "Dispatch HTTP POST/PUT webhook with JSON payload and optional token to external third-party services."
    config_schema = InvokeWebhookActionConfig

    async def execute(
        self,
        db: AsyncSession,
        context: ActionContext,
        config: InvokeWebhookActionConfig,
    ) -> Dict[str, Any]:
        template_vars = {
            "record": context.record_data,
            "diff": context.diff or {},
            "company_id": str(context.company_id),
            "target_model": context.target_model,
            "target_id": str(context.target_id),
            "trigger_type": context.trigger_type,
        }

        # Render URL if dynamic
        target_url = Template(config.url).render(**template_vars)

        # Prepare payload
        if config.payload_template:
            rendered_payload = {}
            for k, v in config.payload_template.items():
                if isinstance(v, str) and "{{" in v:
                    v = Template(v).render(**template_vars)
                rendered_payload[k] = v
        else:
            rendered_payload = {
                "event": f"{context.target_model.lower()}.{context.trigger_type}",
                "company_id": str(context.company_id),
                "target_model": context.target_model,
                "target_id": str(context.target_id),
                "record": context.record_data,
                "diff": context.diff or {},
            }

        headers = {"Content-Type": "application/json", "User-Agent": "Sovereign-Platform/1.0", **config.headers}
        if config.secret_token:
            headers["Authorization"] = f"Bearer {config.secret_token}"

        try:
            async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
                resp = await client.request(
                    method=config.method.upper(),
                    url=target_url,
                    json=rendered_payload,
                    headers=headers,
                )
                return {
                    "status": "delivered" if resp.is_success else "http_error",
                    "http_status": resp.status_code,
                    "url": target_url,
                    "response_snippet": resp.text[:200] if resp.text else "",
                }
        except Exception as exc:
            logger.error(f"Webhook dispatch failed to {target_url}: {exc}")
            return {
                "status": "failed",
                "error": str(exc),
                "url": target_url,
            }
