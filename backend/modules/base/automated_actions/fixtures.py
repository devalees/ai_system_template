"""Default seed automated actions and workflow rules for new tenant companies."""

import uuid
import logging
from typing import Dict, Any, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from modules.base.automated_actions.models import AutomatedAction

logger = logging.getLogger("sovereign.automated_actions.fixtures")

DEFAULT_AUTOMATED_ACTIONS: List[Dict[str, Any]] = [
    {
        "name": "Send Welcome Verification Email on Signup",
        "description": "Automatically enqueue welcome verification email when a new human user registers.",
        "target_model": "User",
        "trigger_type": "on_create",
        "watched_fields": None,
        "condition_tree": {
            "logic": "AND",
            "filters": [
                {"field": "user_type", "operator": "eq", "value": "human"},
            ],
        },
        "action_type": "send_email",
        "action_config": {
            "template_code": "WELCOME_VERIFICATION",
            "recipient_field": "email",
        },
        "execution_mode": "async_celery",
        "sequence": 10,
        "is_active": True,
    },
    {
        "name": "Audit Security Notice on Superuser Grant",
        "description": "Post an automated security log note to chatter when a user is granted superuser privileges.",
        "target_model": "User",
        "trigger_type": "on_update",
        "watched_fields": ["is_superuser"],
        "condition_tree": {
            "logic": "AND",
            "filters": [
                {"field": "is_superuser", "operator": "eq", "value": True},
            ],
        },
        "action_type": "post_chatter",
        "action_config": {
            "body_template": "Security Notice: User {{ record.username }} was elevated to Superuser status.",
            "message_type": "notification",
            "author_type": "system",
        },
        "execution_mode": "sync",
        "sequence": 20,
        "is_active": True,
    },
]


async def seed_default_automated_actions(db: AsyncSession, company_id: uuid.UUID) -> int:
    """Idempotently seed default automation rules for a tenant company."""
    seeded_count = 0
    for data in DEFAULT_AUTOMATED_ACTIONS:
        stmt = select(AutomatedAction).where(
            AutomatedAction.company_id == company_id,
            AutomatedAction.name == data["name"],
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if not existing:
            action = AutomatedAction(
                company_id=company_id,
                name=data["name"],
                description=data.get("description"),
                target_model=data["target_model"],
                trigger_type=data["trigger_type"],
                watched_fields=data.get("watched_fields"),
                condition_tree=data.get("condition_tree"),
                action_type=data["action_type"],
                action_config=data.get("action_config", {}),
                execution_mode=data.get("execution_mode", "async_celery"),
                sequence=data.get("sequence", 10),
                is_active=data.get("is_active", True),
            )
            db.add(action)
            seeded_count += 1

    if seeded_count > 0:
        await db.commit()
        logger.info(f"Seeded {seeded_count} default automated action rules for company {company_id}")

    return seeded_count
