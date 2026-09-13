"""Celery background tasks for async email dispatch and retry processing."""

import logging
import asyncio
from celery_app import celery

logger = logging.getLogger("sovereign.mail_gateway.tasks")


@celery.task(name="mail_gateway.send_queued_mail", bind=True, max_retries=3, default_retry_delay=30)
def send_queued_mail_task(self, mail_queue_id: str) -> dict:
    """Asynchronously process and dispatch an outbound email from the queue."""
    logger.info(f"Executing Celery task mail_gateway.send_queued_mail for queue_id={mail_queue_id}")
    try:
        from modules.base.mail_gateway.service import MailService
        result = asyncio.run(MailService.process_queued_mail_by_id(mail_queue_id))
        return result
    except Exception as exc:
        logger.error(f"Error processing mail {mail_queue_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc)
