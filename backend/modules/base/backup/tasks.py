"""Celery background task for asynchronous backup bundle generation."""

import logging
import asyncio
from celery_app import celery

logger = logging.getLogger("sovereign.backup.tasks")


@celery.task(name="backup.generate_archive", bind=True, max_retries=1)
def generate_backup_task(self, backup_id: str) -> dict:
    """Asynchronously generate database and filestore backup archive."""
    logger.info(f"Executing Celery task backup.generate_archive for backup_id={backup_id}")
    try:
        from modules.base.backup.service import BackupService
        return asyncio.run(BackupService.execute_backup_by_id(backup_id))
    except Exception as exc:
        logger.error(f"Failed generating backup archive {backup_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc)
