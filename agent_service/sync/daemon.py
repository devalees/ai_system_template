"""
Daemon & CLI Runner for Automated Knowledge & Skill Synchronization.

Usage:
  # One-shot manual execution (e.g. for cron):
  python -m agent_service.sync.daemon --once

  # Continuous background daemon (e.g. Docker background service):
  python -m agent_service.sync.daemon --interval-hours 24
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Add project root to sys.path
_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from agent_service.sync.knowledge_sync import KnowledgeSyncEngine

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("agent_service.sync.daemon")


def run_sync_once(engine: KnowledgeSyncEngine) -> int:
    """Runs a single synchronization cycle and logs output."""
    logger.info("Initiating single knowledge synchronization cycle...")
    result = engine.execute_sync_cycle()
    if result.success:
        logger.info("✓ %s", result.message)
        if result.commit_hash:
            logger.info("Commit: %s", result.commit_hash)
        return 0
    else:
        logger.error("✗ Sync failed: %s (Errors: %s)", result.message, result.errors)
        return 1


def run_daemon_loop(engine: KnowledgeSyncEngine, interval_hours: float) -> None:
    """Runs persistent background synchronization loop."""
    interval_seconds = max(interval_hours * 3600.0, 60.0)
    logger.info(
        "Starting Sovereign Knowledge Sync Daemon (Interval: %.1f hours / %.0f seconds)...",
        interval_hours,
        interval_seconds,
    )

    while True:
        try:
            run_sync_once(engine)
        except Exception as e:
            logger.error("Unexpected error in daemon cycle: %s", e, exc_info=True)

        logger.info("Sleeping for %.1f hours until next sync cycle...", interval_hours)
        time.sleep(interval_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sovereign AI Workforce - Automated Knowledge & Skill Sync Engine"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Execute a single synchronization cycle and exit.",
    )
    parser.add_argument(
        "--interval-hours",
        type=float,
        default=24.0,
        help="Daemon interval in hours between sync cycles (default: 24.0).",
    )
    parser.add_argument(
        "--repo-url",
        type=str,
        default=None,
        help="Override CENTRAL_KNOWLEDGE_REPO_URL from environment.",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="Override KNOWLEDGE_HUB_AUTH_TOKEN from environment.",
    )

    args = parser.parse_args()
    engine = KnowledgeSyncEngine(
        repo_url=args.repo_url,
        auth_token=args.token,
    )

    if args.once:
        return run_sync_once(engine)
    else:
        run_daemon_loop(engine, interval_hours=args.interval_hours)
        return 0


if __name__ == "__main__":
    sys.exit(main())
