"""Action handler for dispatching automated agent reasoning tasks to Sovereign Hermes AI Gateway."""

import json
import uuid
import time
import base64
import logging
from typing import Optional, Dict, Any
from jinja2 import Template
import httpx
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from modules.base.automated_actions.handlers.base import BaseActionHandler, ActionContext
from modules.base.chatter.service import ChatterService

logger = logging.getLogger("sovereign.automated_actions.ai_agent")


class AIAgentActionConfig(BaseModel):
    """Configuration schema for Invoke Sovereign AI Agent action."""

    agent_profile: str = Field(
        default="orchestrator",
        description="Target agent profile persona or model name (e.g., 'orchestrator', 'qa_auditor', 'cost_controller', 'security_guard')",
    )
    prompt_template: str = Field(
        ...,
        description="Jinja2 template for the prompt dispatched to the AI agent. Interpolates record, diff, company_id, target_model, target_id.",
    )
    system_prompt: Optional[str] = Field(
        default=None,
        description="Optional system instruction establishing specialist role boundaries and formatting constraints.",
    )
    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for LLM reasoning.",
    )
    max_tokens: int = Field(
        default=1024,
        ge=64,
        le=8192,
        description="Maximum completion token budget.",
    )
    post_to_chatter: bool = Field(
        default=True,
        description="Whether to automatically post the agent's findings and verdict into the target record's Chatter timeline.",
    )
    chatter_title: Optional[str] = Field(
        default=None,
        description="Optional title prefix for the Chatter note (e.g., '🤖 Pre-Flight Financial Audit').",
    )
    tag: Optional[str] = Field(
        default="ai_audit",
        description="Categorical metadata tag attached to chatter note and telemetry traces.",
    )
    timeout_seconds: float = Field(
        default=30.0,
        ge=2.0,
        le=180.0,
        description="HTTP request timeout when invoking Hermes Gateway in seconds.",
    )
    gateway_url: Optional[str] = Field(
        default=None,
        description="Optional override for Hermes Agent Gateway base URL (defaults to core settings).",
    )
    api_key: Optional[str] = Field(
        default=None,
        description="Optional override for Hermes Bearer authentication API key.",
    )


class AIAgentActionHandler(BaseActionHandler):
    """Action handler that invokes the Sovereign Hermes AI Agent Gateway and captures audit verdicts."""

    action_type = "invoke_ai_agent"
    title = "Invoke Sovereign AI Agent"
    description = (
        "Asynchronously invokes a Sovereign AI Agent profile via Hermes Gateway with dynamic prompt interpolation, "
        "extracts structured reasoning/verdicts, posts findings to Chatter, and dispatches Langfuse telemetry."
    )
    config_schema = AIAgentActionConfig

    async def execute(
        self,
        db: AsyncSession,
        context: ActionContext,
        config: AIAgentActionConfig,
    ) -> Dict[str, Any]:
        trace_id = str(uuid.uuid4())
        start_time = time.time()

        template_vars = {
            "record": context.record_data or {},
            "old_record": context.old_record_data or {},
            "diff": context.diff or {},
            "company_id": str(context.company_id),
            "target_model": context.target_model,
            "target_id": str(context.target_id),
            "trigger_type": context.trigger_type,
            "depth": context.depth,
            "extra": context.extra_context or {},
        }

        # 1. Render dynamic prompts
        try:
            rendered_prompt = Template(config.prompt_template).render(**template_vars)
            rendered_system = (
                Template(config.system_prompt).render(**template_vars)
                if config.system_prompt
                else None
            )
        except Exception as exc:
            logger.error(f"Failed to render AI Agent prompt template: {exc}")
            return {
                "status": "template_error",
                "error": str(exc),
                "trace_id": trace_id,
            }

        gateway_url = (config.gateway_url or settings.HERMES_GATEWAY_URL).rstrip("/")
        api_key = config.api_key or settings.HERMES_API_KEY
        endpoint = f"{gateway_url}/v1/chat/completions"

        messages = []
        if rendered_system:
            messages.append({"role": "system", "content": rendered_system})
        messages.append({"role": "user", "content": rendered_prompt})

        payload = {
            "model": config.agent_profile or "hermes-agent",
            "messages": messages,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "X-Trace-Id": trace_id,
            "X-Target-Model": context.target_model,
            "X-Target-Id": str(context.target_id),
        }

        # 2. Invoke Hermes Gateway
        agent_reply = ""
        usage: Dict[str, Any] = {}
        http_status = 200

        try:
            async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
                resp = await client.post(endpoint, json=payload, headers=headers)
                http_status = resp.status_code
                if resp.is_success:
                    resp_data = resp.json()
                    choices = resp_data.get("choices", [])
                    if choices:
                        agent_reply = choices[0].get("message", {}).get("content", "")
                    usage = resp_data.get("usage", {})
                else:
                    logger.warning(
                        f"Hermes Gateway returned non-200 HTTP {resp.status_code}: {resp.text[:200]}"
                    )
                    agent_reply = f"[Hermes Gateway HTTP {resp.status_code} Error: {resp.text[:200]}]"
        except httpx.RequestError as exc:
            logger.warning(f"Hermes Gateway invocation network error: {exc}")
            agent_reply = f"[Hermes Gateway Network Notice: {str(exc)}]"
            http_status = 503

        duration_ms = round((time.time() - start_time) * 1000.0, 2)

        # 3. Post Findings to Polymorphic Chatter Thread
        chatter_message_id = None
        if config.post_to_chatter and context.target_model and context.target_id:
            try:
                title = (
                    config.chatter_title
                    or f"🤖 **AI Agent Analysis [{config.agent_profile.upper()}]**"
                )
                formatted_body = f"{title}\n\n{agent_reply}"

                message = await ChatterService.post_message(
                    db=db,
                    res_model=context.target_model,
                    res_id=context.target_id,
                    body=formatted_body,
                    company_id=context.company_id,
                    author_id=context.user_id,
                    author_type="ai_agent",
                    message_type="comment",
                    metadata_info={
                        "automated_action": True,
                        "action_type": self.action_type,
                        "agent_profile": config.agent_profile,
                        "tag": config.tag,
                        "trace_id": trace_id,
                        "duration_ms": duration_ms,
                        "usage": usage,
                    },
                )
                chatter_message_id = str(message.id)
            except Exception as exc:
                logger.error(f"Failed to post AI Agent response to Chatter: {exc}", exc_info=True)

        # 4. Asynchronous Langfuse Telemetry Ingestion Dispatch (Glass-Box Observability)
        await self._dispatch_langfuse_trace(
            trace_id=trace_id,
            profile=config.agent_profile,
            prompt=rendered_prompt,
            output=agent_reply,
            usage=usage,
            duration_ms=duration_ms,
            context=context,
        )

        return {
            "status": "completed" if http_status == 200 else "gateway_error",
            "http_status": http_status,
            "trace_id": trace_id,
            "agent_profile": config.agent_profile,
            "prompt_preview": rendered_prompt[:250],
            "agent_response": agent_reply,
            "usage": usage,
            "duration_ms": duration_ms,
            "chatter_message_id": chatter_message_id,
        }

    async def _dispatch_langfuse_trace(
        self,
        trace_id: str,
        profile: str,
        prompt: str,
        output: str,
        usage: Dict[str, Any],
        duration_ms: float,
        context: ActionContext,
    ) -> None:
        """Dispatches non-blocking execution trace to Langfuse (:3100) if available."""
        langfuse_host = settings.LANGFUSE_HOST.rstrip("/")
        if not langfuse_host:
            return

        ingest_url = f"{langfuse_host}/api/public/ingestion"
        public_key = "pk-lf-sovereign-agent-2026"
        secret_key = "sk-lf-sovereign-agent-2026"
        auth_header = "Basic " + base64.b64encode(f"{public_key}:{secret_key}".encode("utf-8")).decode("utf-8")

        prompt_tokens = usage.get("prompt_tokens", len(prompt.split()))
        comp_tokens = usage.get("completion_tokens", len(output.split()))

        batch_payload = {
            "batch": [
                {
                    "id": str(uuid.uuid4()),
                    "type": "trace-create",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "body": {
                        "id": trace_id,
                        "name": f"TCA: {context.target_model}.{context.trigger_type} -> {profile}",
                        "metadata": {
                            "company_id": str(context.company_id),
                            "target_model": context.target_model,
                            "target_id": str(context.target_id),
                            "agent_profile": profile,
                            "duration_ms": duration_ms,
                            "tokens": {
                                "prompt": prompt_tokens,
                                "completion": comp_tokens,
                                "total": prompt_tokens + comp_tokens,
                            },
                        },
                    },
                }
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                await client.post(
                    ingest_url,
                    json=batch_payload,
                    headers={"Authorization": auth_header, "Content-Type": "application/json"},
                )
        except Exception:
            # Langfuse telemetry is non-blocking
            pass
