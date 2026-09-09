"""
Hermes Model & Provider Catalog Service.

Dynamically fetches modern model catalogs, context windows, and token pricing ($/1M tokens)
using models.dev (the official multi-provider registry powering Hermes Agent) and OpenRouter.
Includes persistent disk caching, noise filtering, and canonical provider resolution.
"""

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# Canonical providers matching Hermes CLI
CANONICAL_PROVIDERS = [
    {"slug": "openrouter", "name": "OpenRouter (400+ Models Aggregator)"},
    {"slug": "anthropic", "name": "Anthropic (Claude Sonnet 4.6, Opus 5, Haiku 4.5)"},
    {"slug": "openai-api", "name": "OpenAI API (GPT-5, GPT-5.6 Sol, Codex)"},
    {"slug": "openai", "name": "OpenAI Direct (ChatGPT / GPT-5)"},
    {"slug": "gemini", "name": "Google Gemini (Gemini 3.1 Pro, 3.6 Flash)"},
    {"slug": "groq", "name": "Groq (LPU Ultra-Fast Inference)"},
    {"slug": "deepseek", "name": "DeepSeek (V4 Pro, V4 Flash)"},
    {"slug": "xai", "name": "xAI (Grok 4.6, Grok 4.3)"},
    {"slug": "nous", "name": "Nous Portal (Hermes Models)"},
    {"slug": "alibaba", "name": "Alibaba Cloud (Qwen 3.8, Qwen 3.7)"},
    {"slug": "minimax", "name": "MiniMax (M3, M2.5)"},
    {"slug": "zai", "name": "Z.AI / GLM (GLM-5.3, GLM-4.7)"},
    {"slug": "mistral", "name": "Mistral AI (Mistral Small, Devstral)"},
    {"slug": "fireworks", "name": "Fireworks AI"},
    {"slug": "novita", "name": "Novita AI"},
    {"slug": "ollama", "name": "Ollama (Local / Cloud)"},
    {"slug": "custom", "name": "Custom / Self-Hosted Endpoint"},
]

# Mapping from Hermes provider slugs to models.dev provider keys
PROVIDER_TO_MODELS_DEV = {
    "openrouter": "openrouter",
    "anthropic": "anthropic",
    "openai-api": "openai",
    "openai": "openai",
    "gemini": "google",
    "google": "google",
    "groq": "groq",
    "deepseek": "deepseek",
    "xai": "xai",
    "xai-oauth": "xai",
    "alibaba": "alibaba",
    "minimax": "minimax",
    "minimax-oauth": "minimax",
    "zai": "zai",
    "mistral": "mistral",
    "fireworks": "fireworks-ai",
    "novita": "novita-ai",
    "ollama": "ollama-cloud",
}

# Patterns to filter non-agentic noise (TTS, embeddings, live-stream, image-only)
_NOISE_PATTERNS = re.compile(
    r"-tts\b|embedding|live-|-(preview|exp)-\d{2,4}[-_]|"
    r"-image\b|-image-preview\b|-customtools\b",
    re.IGNORECASE,
)

# Stale or low-quota Google models excluded in Hermes Agent
_GOOGLE_HIDDEN_MODELS = frozenset({
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-1.5-flash-8b",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemma-3-1b",
    "gemma-3-2b",
    "gemma-3-4b",
    "gemma-3-12b",
    "gemma-3-27b",
})

# Specialized Nous Portal models (curated directly from Hermes manifest)
_NOUS_MODELS = [
    {
        "id": "anthropic/claude-fable-5.1",
        "name": "Claude Fable 5.1 (Nous Portal)",
        "context_length": 1000000,
        "cost_input_per_1m": 3.00,
        "cost_output_per_1m": 15.00,
        "supports_reasoning": True,
        "description": "Nous Portal flagship agent reasoning model.",
    },
    {
        "id": "anthropic/claude-fable-5",
        "name": "Claude Fable 5 (Nous Portal)",
        "context_length": 1000000,
        "cost_input_per_1m": 3.00,
        "cost_output_per_1m": 15.00,
        "supports_reasoning": True,
        "description": "High-throughput Nous Portal reasoning model.",
    },
    {
        "id": "anthropic/claude-opus-5",
        "name": "Claude Opus 5 (Nous Portal)",
        "context_length": 1000000,
        "cost_input_per_1m": 5.00,
        "cost_output_per_1m": 25.00,
        "supports_reasoning": True,
        "description": "Ultra-large frontier reasoning model.",
    },
    {
        "id": "anthropic/claude-opus-4.8",
        "name": "Claude Opus 4.8 (Nous Portal)",
        "context_length": 500000,
        "cost_input_per_1m": 4.50,
        "cost_output_per_1m": 22.50,
        "supports_reasoning": True,
        "description": "Frontier agent model on Nous infrastructure.",
    },
    {
        "id": "anthropic/claude-sonnet-5",
        "name": "Claude Sonnet 5 (Nous Portal)",
        "context_length": 1000000,
        "cost_input_per_1m": 2.80,
        "cost_output_per_1m": 14.00,
        "supports_reasoning": True,
        "description": "High-speed multimodal coding and agent operations.",
    },
    {
        "id": "nousresearch/hermes-3-llama-3.1-405b",
        "name": "Hermes 3 405B (Nous Native)",
        "context_length": 131072,
        "cost_input_per_1m": 1.50,
        "cost_output_per_1m": 3.50,
        "supports_reasoning": True,
        "description": "Nous Research flagship open-weight agent model.",
    },
]

# Local cache paths and variables
_CACHE_FILE = "/tmp/models_dev_cache.json"
_CACHE_TTL_SECONDS = 4 * 3600  # 4 hours
_MEMORY_CACHE: Optional[Dict[str, Any]] = None
_MEMORY_CACHE_TIME: float = 0.0

_OPENROUTER_CACHE: Optional[List[Dict[str, Any]]] = None
_OPENROUTER_CACHE_TIME: float = 0.0


def get_providers() -> List[Dict[str, str]]:
    """Returns canonical providers list."""
    return CANONICAL_PROVIDERS


def _load_models_dev_catalog(allow_network: bool = True) -> Dict[str, Any]:
    """
    Loads models.dev catalog from memory, disk cache, or remote HTTP.
    Matches Hermes Agent's agent/models_dev.py caching lifecycle.
    """
    global _MEMORY_CACHE, _MEMORY_CACHE_TIME
    now = time.time()

    # 1. Return in-memory cache if still fresh
    if _MEMORY_CACHE and (now - _MEMORY_CACHE_TIME < _CACHE_TTL_SECONDS):
        return _MEMORY_CACHE

    # 2. Check disk cache
    if os.path.exists(_CACHE_FILE):
        try:
            mtime = os.path.getmtime(_CACHE_FILE)
            if (now - mtime < _CACHE_TTL_SECONDS) or not allow_network:
                with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and data:
                        _MEMORY_CACHE = data
                        _MEMORY_CACHE_TIME = mtime
                        return data
        except Exception as exc:
            logger.warning("Error reading disk cache %s: %s", _CACHE_FILE, exc)

    # 3. Perform network fetch if network allowed
    if allow_network:
        try:
            resp = requests.get("https://models.dev/api.json", timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and data:
                    _MEMORY_CACHE = data
                    _MEMORY_CACHE_TIME = now
                    try:
                        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
                            json.dump(data, f)
                    except Exception as write_err:
                        logger.warning("Could not persist disk cache: %s", write_err)
                    return data
        except Exception as net_err:
            logger.warning("Failed to fetch models.dev API: %s", net_err)

    # 4. Fallback: return stale disk cache if present
    if os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass

    return {}


def fetch_openrouter_catalog() -> List[Dict[str, Any]]:
    """Fetches and caches live model catalog with pricing and context from OpenRouter."""
    global _OPENROUTER_CACHE, _OPENROUTER_CACHE_TIME
    now = time.time()

    if _OPENROUTER_CACHE and (now - _OPENROUTER_CACHE_TIME < 3600):
        return _OPENROUTER_CACHE

    try:
        resp = requests.get("https://openrouter.ai/api/v1/models", timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            models_raw = data.get("data", [])
            formatted = []
            for m in models_raw:
                m_id = m.get("id", "")
                name = m.get("name", m_id)
                ctx = m.get("context_length", 128000)
                pricing = m.get("pricing", {})

                try:
                    p_in = float(pricing.get("prompt", 0)) * 1_000_000
                    p_out = float(pricing.get("completion", 0)) * 1_000_000
                except (ValueError, TypeError):
                    p_in = 0.0
                    p_out = 0.0

                params = m.get("supported_parameters", []) or []
                supports_reasoning = (
                    "reasoning" in params or
                    "include_reasoning" in params or
                    any(term in m_id.lower() for term in ["deepseek-r1", "o1", "o3", "thinking", "gemini-2.5", "gemini-3", "sonnet-3.7", "sonnet-4", "opus-5", "fable-5"])
                )

                formatted.append({
                    "id": m_id,
                    "name": name,
                    "context_length": ctx,
                    "cost_input_per_1m": round(p_in, 4),
                    "cost_output_per_1m": round(p_out, 4),
                    "supports_reasoning": supports_reasoning,
                    "description": m.get("description", "")[:120] or "OpenRouter high-performance model.",
                })

            _OPENROUTER_CACHE = formatted
            _OPENROUTER_CACHE_TIME = now
            return formatted
    except Exception as exc:
        logger.warning("Failed to fetch live OpenRouter catalog: %s", exc)

    # Fall back to models.dev for OpenRouter if direct API is unreachable
    mdev_catalog = _load_models_dev_catalog(allow_network=False)
    if "openrouter" in mdev_catalog:
        return _parse_models_dev_provider("openrouter", mdev_catalog["openrouter"])

    return [
        {
            "id": "google/gemini-2.5-flash",
            "name": "Google: Gemini 2.5 Flash",
            "context_length": 1048576,
            "cost_input_per_1m": 0.075,
            "cost_output_per_1m": 0.30,
            "description": "Recommended default for high speed and 1M context.",
        }
    ]


def _parse_models_dev_provider(provider_key: str, provider_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parses models from models.dev provider entry into normalized catalog format."""
    models_raw = provider_data.get("models", {})
    if not isinstance(models_raw, dict):
        return []

    results = []
    for mid, mval in models_raw.items():
        if not isinstance(mval, dict):
            continue

        # Filter noise models
        if _NOISE_PATTERNS.search(mid):
            continue

        # Filter retired / low-quota Google models
        if provider_key == "google" and mid in _GOOGLE_HIDDEN_MODELS:
            continue

        # Require tool call or agentic compatibility
        if not mval.get("tool_call", False) and not mval.get("reasoning", False):
            continue

        limit = mval.get("limit") or {}
        ctx = limit.get("context", 128000)
        try:
            ctx_int = int(ctx) if ctx else 128000
        except (ValueError, TypeError):
            ctx_int = 128000

        cost = mval.get("cost") or {}
        in_c = cost.get("input", 0.0)
        out_c = cost.get("output", 0.0)

        # Handle context-tiered pricing if present
        try:
            in_cost = float(in_c) if in_c is not None else 0.0
            out_cost = float(out_c) if out_c is not None else 0.0
        except (ValueError, TypeError):
            in_cost = 0.0
            out_cost = 0.0

        modalities = mval.get("modalities") or {}
        in_mods = modalities.get("input", ["text"])
        capabilities = []
        if mval.get("reasoning"):
            capabilities.append("Reasoning")
        if mval.get("tool_call"):
            capabilities.append("Tools")
        if "image" in in_mods:
            capabilities.append("Vision")
        if "pdf" in in_mods:
            capabilities.append("PDF")

        cap_str = f"Supports {', '.join(capabilities)}." if capabilities else "Standard LLM inference."
        desc = f"{cap_str} Context: {ctx_int:,} tokens."

        results.append({
            "id": mid,
            "name": mval.get("name", mid),
            "context_length": ctx_int,
            "cost_input_per_1m": round(in_cost, 4),
            "cost_output_per_1m": round(out_cost, 4),
            "supports_reasoning": bool(mval.get("reasoning")),
            "description": desc,
            "_raw_order": mval.get("release_date", ""),
        })

    # Sort: models with release_date or higher versioning first
    results.sort(key=lambda x: (x["cost_output_per_1m"] > 0, x["context_length"] >= 200000, x["_raw_order"]), reverse=True)
    for r in results:
        r.pop("_raw_order", None)

    return results


def get_models_for_provider(provider_slug: str) -> List[Dict[str, Any]]:
    """Returns list of modern models with context length and pricing for given provider."""
    provider_slug = provider_slug.lower().strip()

    # 1. OpenRouter (Direct API or models.dev fallback)
    if provider_slug == "openrouter":
        return fetch_openrouter_catalog()

    # 2. Nous Portal (Hermes-curated models)
    if provider_slug == "nous":
        return _NOUS_MODELS

    # 3. Query models.dev for canonical company providers (Anthropic, OpenAI, Google, Groq, DeepSeek, xAI, etc.)
    mdev_key = PROVIDER_TO_MODELS_DEV.get(provider_slug, provider_slug)
    catalog = _load_models_dev_catalog(allow_network=True)
    if mdev_key in catalog:
        models = _parse_models_dev_provider(mdev_key, catalog[mdev_key])
        if models:
            return models

    # 4. Fallback for offline or uncataloged providers
    return [
        {
            "id": "default",
            "name": f"Default {provider_slug.capitalize()} Model",
            "context_length": 128000,
            "cost_input_per_1m": 0.0,
            "cost_output_per_1m": 0.0,
            "description": "Provider default configuration via Hermes CLI.",
        }
    ]
