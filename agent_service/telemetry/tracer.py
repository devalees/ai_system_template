"""
Glass-Box Telemetry & LLMOps Tracer for Sovereign Autonomous Agents.

Captures turn-by-turn thought streams, prompt generations, per-tool latency waterfalls,
and real-time token spend accounting. Dispatches trace events to Langfuse (:3100)
with automatic local JSON persistence fallback.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("agent_service.telemetry")

# Token pricing catalog (USD per 1,000 tokens)
MODEL_PRICING_PER_1K: Dict[str, Dict[str, float]] = {
    "claude-3.5-sonnet": {"prompt": 0.003, "completion": 0.015},
    "anthropic/claude-3.5-sonnet": {"prompt": 0.003, "completion": 0.015},
    "gemini-2.5-flash": {"prompt": 0.000075, "completion": 0.0003},
    "google/gemini-2.5-flash": {"prompt": 0.000075, "completion": 0.0003},
    "gpt-4o": {"prompt": 0.0025, "completion": 0.010},
    "openai/gpt-4o": {"prompt": 0.0025, "completion": 0.010},
    "default": {"prompt": 0.002, "completion": 0.008},
}


def compute_token_cost(prompt_tokens: int, completion_tokens: int, model: str) -> float:
    """
    Calculates estimated dollar cost in USD for a generation.

    Args:
        prompt_tokens: Number of prompt / context input tokens.
        completion_tokens: Number of generated output tokens.
        model: Model identifier string.

    Returns:
        float: Estimated cost in USD rounded to 6 decimal places.
    """
    pricing = MODEL_PRICING_PER_1K.get(model.lower())
    if not pricing:
        # Match substring
        for k, v in MODEL_PRICING_PER_1K.items():
            if k in model.lower():
                pricing = v
                break
    if not pricing:
        pricing = MODEL_PRICING_PER_1K["default"]

    cost = (prompt_tokens / 1000.0) * pricing["prompt"] + (completion_tokens / 1000.0) * pricing["completion"]
    return round(cost, 6)


@dataclass
class TraceGeneration:
    """Represents an LLM generation span."""
    id: str
    model: str
    prompt: str
    output: str
    thinking: Optional[str]
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    duration_ms: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class TraceToolCall:
    """Represents an MCP tool execution span."""
    id: str
    tool_name: str
    arguments: Dict[str, Any]
    result: Any
    status: str
    duration_ms: float
    timestamp: float = field(default_factory=time.time)


class TelemetryTracer:
    """
    Sovereign LLMOps tracer providing glass-box visibility into agent reasoning,
    tool execution, and token expenditures.
    """

    def __init__(
        self,
        task_id: Optional[str] = None,
        profile_name: str = "orchestrator",
        objective: str = "",
        reasoning_effort: str = "none",
        host: Optional[str] = None,
        public_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        traces_dir: Optional[str | Path] = None,
    ) -> None:
        """
        Initializes an active telemetry trace context.

        Args:
            task_id: Unique task identifier (auto-generated UUID if omitted).
            profile_name: Name of active specialist profile.
            objective: High-level task objective.
            reasoning_effort: Configured reasoning level ('none', 'low', 'high').
            host: Langfuse server URL (defaults to LANGFUSE_HOST or 'http://localhost:3100').
            public_key: Langfuse public API key.
            secret_key: Langfuse secret API key.
            traces_dir: Directory path for local JSON fallback persistence.
        """
        self.task_id = task_id or str(uuid.uuid4())
        self.profile_name = profile_name
        self.objective = objective
        self.reasoning_effort = reasoning_effort
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.status = "active"

        self.generations: List[TraceGeneration] = []
        self.tool_calls: List[TraceToolCall] = []

        self.host = (host or os.getenv("LANGFUSE_HOST") or "http://localhost:3100").rstrip("/")
        self.public_key = public_key or os.getenv("LANGFUSE_PUBLIC_KEY") or "pk-lf-sovereign-agent-2026"
        self.secret_key = secret_key or os.getenv("LANGFUSE_SECRET_KEY") or "sk-lf-sovereign-agent-2026"

        if traces_dir:
            self.traces_dir = Path(traces_dir)
        else:
            self.traces_dir = Path(__file__).resolve().parent.parent / "data" / "traces"
        self.traces_dir.mkdir(parents=True, exist_ok=True)

    def record_generation(
        self,
        prompt: str,
        output: str,
        prompt_tokens: int,
        completion_tokens: int,
        model: str = "anthropic/claude-3.5-sonnet",
        thinking: Optional[str] = None,
        duration_ms: float = 0.0,
    ) -> TraceGeneration:
        """
        Records an LLM generation event with exact token calculation and dollar costing.

        Args:
            prompt: User/system input prompt text.
            output: Assistant completion text.
            prompt_tokens: Number of prompt tokens.
            completion_tokens: Number of completion tokens.
            model: Model name string.
            thinking: Optional intermediate thinking/reasoning stream.
            duration_ms: Inference duration in milliseconds.

        Returns:
            TraceGeneration: Recorded generation span.
        """
        cost = compute_token_cost(prompt_tokens, completion_tokens, model)
        gen = TraceGeneration(
            id=str(uuid.uuid4()),
            model=model,
            prompt=prompt,
            output=output,
            thinking=thinking,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost,
            duration_ms=duration_ms,
        )
        self.generations.append(gen)
        return gen

    def record_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
        status: str = "success",
        duration_ms: float = 0.0,
    ) -> TraceToolCall:
        """
        Records an MCP tool execution span.

        Args:
            tool_name: FastMCP tool name (e.g. 'decompose_task_dag').
            arguments: Input arguments dictionary.
            result: Tool return payload or serialized model.
            status: Execution exit status ('success', 'error', 'timeout').
            duration_ms: Execution duration in milliseconds.

        Returns:
            TraceToolCall: Recorded tool call span.
        """
        # Serialize result if needed
        serialized_result = result
        if hasattr(result, "model_dump"):
            serialized_result = result.model_dump()

        tc = TraceToolCall(
            id=str(uuid.uuid4()),
            tool_name=tool_name,
            arguments=arguments,
            result=serialized_result,
            status=status,
            duration_ms=duration_ms,
        )
        self.tool_calls.append(tc)
        return tc

    def end_task(self, status: str = "completed") -> Dict[str, Any]:
        """
        Concludes the active trace, aggregates token totals, and persists records.

        Args:
            status: Final status ('completed', 'failed', 'aborted').

        Returns:
            Dict[str, Any]: Complete serialized trace summary.
        """
        self.end_time = time.time()
        self.status = status

        total_prompt = sum(g.prompt_tokens for g in self.generations)
        total_comp = sum(g.completion_tokens for g in self.generations)
        total_cost = round(sum(g.cost_usd for g in self.generations), 6)
        total_duration_ms = round((self.end_time - self.start_time) * 1000.0, 2)

        payload = {
            "task_id": self.task_id,
            "profile_name": self.profile_name,
            "objective": self.objective,
            "reasoning_effort": self.reasoning_effort,
            "status": self.status,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": total_duration_ms,
            "metrics": {
                "total_prompt_tokens": total_prompt,
                "total_completion_tokens": total_comp,
                "total_tokens": total_prompt + total_comp,
                "total_cost_usd": total_cost,
                "generation_count": len(self.generations),
                "tool_call_count": len(self.tool_calls),
            },
            "generations": [asdict(g) for g in self.generations],
            "tool_calls": [asdict(t) for t in self.tool_calls],
        }

        # 1. Local JSON Persistence
        trace_file = self.traces_dir / f"{self.task_id}.json"
        try:
            with open(trace_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.warning("Failed to write local trace file: %s", exc)

        # 2. Asynchronous / Non-blocking Langfuse Ingestion Dispatch
        self._dispatch_to_langfuse(payload)

        return payload

    def _dispatch_to_langfuse(self, payload: Dict[str, Any]) -> None:
        """Dispatches trace payload to Langfuse REST API if accessible."""
        ingest_url = f"{self.host}/api/public/ingestion"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Basic " + base64.b64encode(f"{self.public_key}:{self.secret_key}".encode("utf-8")).decode("utf-8"),
        }

        # Construct standard Langfuse v2 event batch
        event_batch = {
            "batch": [
                {
                    "id": str(uuid.uuid4()),
                    "type": "trace-create",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.start_time)),
                    "body": {
                        "id": self.task_id,
                        "name": f"{self.profile_name}: {self.objective[:50]}",
                        "metadata": {
                            "profile": self.profile_name,
                            "reasoning_effort": self.reasoning_effort,
                            "metrics": payload["metrics"],
                        },
                    },
                }
            ]
        }

        try:
            req = urllib.request.Request(
                ingest_url,
                data=json.dumps(event_batch).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status in (200, 201, 207):
                    logger.debug("Successfully ingested trace %s to Langfuse", self.task_id)
        except Exception:
            # Langfuse ingestion is non-blocking; fallback is already saved locally
            pass

    def get_metrics(self) -> Dict[str, Any]:
        """Calculates current accumulated metrics for the active session."""
        total_prompt = sum(g.prompt_tokens for g in self.generations)
        total_comp = sum(g.completion_tokens for g in self.generations)
        total_cost = round(sum(g.cost_usd for g in self.generations), 6)
        return {
            "task_id": self.task_id,
            "status": self.status,
            "total_tokens": total_prompt + total_comp,
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_comp,
            "total_cost_usd": total_cost,
            "generations": len(self.generations),
            "tool_calls": len(self.tool_calls),
        }
