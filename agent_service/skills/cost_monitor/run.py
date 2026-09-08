#!/usr/bin/env python3
"""
Cost Monitor Skill Runner.

Scans Hermes SQLite databases (`state.db`) across all profiles and the root environment
to aggregate LLM token usage, calculate estimated expenditure, and enforce budget thresholds.
"""

import argparse
import glob
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


# Default pricing per 1M tokens if estimated_cost_usd is missing or zero
DEFAULT_PRICING = {
    "google/gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "anthropic/claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "anthropic/claude-opus": {"input": 15.00, "output": 75.00},
    "openai/gpt-4o": {"input": 2.50, "output": 10.00},
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "default": {"input": 0.50, "output": 1.50},
}


def find_state_databases(hermes_root: Path) -> list[tuple[str, Path]]:
    """Discovers all state.db files across default and named profiles."""
    dbs = []
    # 1. Default profile state.db
    root_db = hermes_root / "state.db"
    if root_db.exists():
        dbs.append(("default", root_db))

    # 2. Named profiles state.db
    profiles_dir = hermes_root / "profiles"
    if profiles_dir.exists():
        for p_dir in profiles_dir.iterdir():
            if p_dir.is_dir():
                p_db = p_dir / "state.db"
                if p_db.exists():
                    dbs.append((p_dir.name, p_db))
    return dbs


def collect_metrics(hermes_root: Path) -> dict:
    """Queries session_model_usage across all discovered state.db files."""
    dbs = find_state_databases(hermes_root)
    total_calls = 0
    total_input = 0
    total_output = 0
    total_cost = 0.0
    profiles_breakdown = {}
    models_breakdown = {}

    for profile_name, db_path in dbs:
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cur = conn.cursor()
            cur.execute("""
                SELECT model, billing_provider, api_call_count, input_tokens,
                       output_tokens, estimated_cost_usd, actual_cost_usd
                FROM session_model_usage
            """)
            rows = cur.fetchall()
            conn.close()

            p_tokens = 0
            p_cost = 0.0

            for model, provider, calls, in_toks, out_toks, est_cost, act_cost in rows:
                cost = act_cost if act_cost > 0 else est_cost
                if cost == 0.0:
                    pricing = DEFAULT_PRICING.get(model, DEFAULT_PRICING["default"])
                    cost = (in_toks / 1_000_000 * pricing["input"]) + (out_toks / 1_000_000 * pricing["output"])

                total_calls += calls
                total_input += in_toks
                total_output += out_toks
                total_cost += cost

                p_tokens += (in_toks + out_toks)
                p_cost += cost

                if model not in models_breakdown:
                    models_breakdown[model] = {
                        "api_calls": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "cost_usd": 0.0
                    }
                models_breakdown[model]["api_calls"] += calls
                models_breakdown[model]["input_tokens"] += in_toks
                models_breakdown[model]["output_tokens"] += out_toks
                models_breakdown[model]["cost_usd"] += round(cost, 6)

            profiles_breakdown[profile_name] = {
                "total_tokens": p_tokens,
                "cost_usd": round(p_cost, 6)
            }
        except Exception as exc:
            profiles_breakdown[profile_name] = {"error": str(exc)}

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_api_calls": total_calls,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_input + total_output,
        "total_cost_usd": round(total_cost, 6),
        "profiles": profiles_breakdown,
        "models": models_breakdown,
    }


def main():
    parser = argparse.ArgumentParser(description="Audit Hermes token spend and costs.")
    parser.add_argument("--daily-budget", type=float, default=10.00, help="Daily budget limit in USD.")
    parser.add_argument("--hermes-root", type=str, default="/root/.hermes", help="Path to Hermes root directory.")
    parser.add_argument("--json", action="store_true", help="Output raw JSON.")
    args = parser.parse_args()

    hermes_root = Path(args.hermes_root)
    if not hermes_root.exists():
        # Fallback for host execution
        host_fallback = Path(__file__).resolve().parent.parent.parent / "data"
        if host_fallback.exists():
            hermes_root = host_fallback

    metrics = collect_metrics(hermes_root)
    metrics["daily_budget_usd"] = args.daily_budget
    metrics["budget_utilization_pct"] = round((metrics["total_cost_usd"] / args.daily_budget) * 100, 2)

    if metrics["total_cost_usd"] > args.daily_budget:
        metrics["budget_status"] = "EXCEEDED"
    elif metrics["total_cost_usd"] > (args.daily_budget * 0.8):
        metrics["budget_status"] = "WARNING"
    else:
        metrics["budget_status"] = "OK"

    if args.json:
        print(json.dumps(metrics, indent=2))
        return

    # Formatted terminal output
    status_color = "\033[92m" if metrics["budget_status"] == "OK" else "\033[91m"
    reset = "\033[0m"
    bold = "\033[1m"

    print(f"\n{bold}═══════════════════════════════════════════════════════════════════{reset}")
    print(f"{bold}        Hermes Cost Controller: Financial Audit Report             {reset}")
    print(f"{bold}═══════════════════════════════════════════════════════════════════{reset}")
    print(f"Timestamp:          {metrics['timestamp']}")
    print(f"Total API Calls:    {metrics['total_api_calls']:,}")
    print(f"Total Tokens:       {metrics['total_tokens']:,} (In: {metrics['total_input_tokens']:,} | Out: {metrics['total_output_tokens']:,})")
    print(f"Total Expenditure:  ${metrics['total_cost_usd']:.4f} USD")
    print(f"Daily Budget Limit: ${metrics['daily_budget_usd']:.2f} USD")
    print(f"Budget Status:      {status_color}{bold}{metrics['budget_status']}{reset} ({metrics['budget_utilization_pct']}% utilized)")
    print(f"───────────────────────────────────────────────────────────────────")
    print(f"{bold}Per-Profile Spend Breakdown:{reset}")
    for p_name, data in metrics["profiles"].items():
        if "error" in data:
            print(f"  • {p_name}: Error ({data['error']})")
        else:
            print(f"  • {p_name:<20}: {data['total_tokens']:>8,} tokens | ${data['cost_usd']:.4f}")

    if metrics["models"]:
        print(f"───────────────────────────────────────────────────────────────────")
        print(f"{bold}Per-Model Consumption:{reset}")
        for m_name, data in metrics["models"].items():
            print(f"  • {m_name:<30}: {data['api_calls']} calls | {data['input_tokens']+data['output_tokens']:,} tokens | ${data['cost_usd']:.4f}")
    print(f"{bold}═══════════════════════════════════════════════════════════════════{reset}\n")


if __name__ == "__main__":
    main()
