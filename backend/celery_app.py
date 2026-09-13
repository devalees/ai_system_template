"""Celery application and task worker configuration."""

from celery import Celery
from core.config import settings

celery = Celery(
    "sovereign_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    broker_connection_retry_on_startup=True,
    imports=[
        "modules.base.mail_gateway.tasks",
    ],
)


@celery.task(name="ping")
def ping() -> str:
    """Worker health check task."""
    return "pong"
