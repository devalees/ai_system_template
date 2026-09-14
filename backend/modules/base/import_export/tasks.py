"""Celery background tasks for asynchronous bulk data import and export jobs."""

import logging
import asyncio
from celery_app import celery

logger = logging.getLogger("sovereign.import_export.tasks")


@celery.task(name="import_export.process_job", bind=True, max_retries=1)
def process_import_export_job_task(self, job_id: str) -> dict:
    """Asynchronously execute bulk import/export processing."""
    logger.info(f"Executing Celery task import_export.process_job for job_id={job_id}")
    try:
        from modules.base.import_export.service import ImportExportService
        return asyncio.run(ImportExportService.process_job_by_id(job_id))
    except Exception as exc:
        logger.error(f"Failed processing import/export job {job_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc)
