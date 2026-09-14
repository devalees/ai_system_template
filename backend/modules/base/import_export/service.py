"""Service orchestrating bulk data imports, schema mapping, and streaming exports."""

import os
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List, Type

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.base_models import Base
from core.database import AsyncSessionLocal
from core.exceptions import NotFoundException, ValidationException
from modules.base.import_export.models import ImportExportJob
from modules.base.import_export.schemas import ExportRequest
from modules.base.import_export.processor import DataProcessor

logger = logging.getLogger("sovereign.import_export.service")

STORAGE_DIR = Path("/tmp/sovereign_jobs")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


class ImportExportService:
    """Service executing schema validation, entity mapping, and file conversion."""

    @classmethod
    def resolve_model(cls, model_name: str) -> Type[Any]:
        """Resolve a string model identifier to its registered SQLAlchemy declarative class."""
        clean_name = model_name.strip().lower()
        parts = clean_name.split(".")
        target_name = parts[-1]

        for mapper in Base.registry.mappers:
            model_cls = mapper.class_
            table_name = getattr(model_cls, "__tablename__", "").lower()
            class_name = model_cls.__name__.lower()

            if clean_name in (table_name, class_name):
                return model_cls
            if target_name in (table_name, class_name):
                return model_cls

        raise ValidationException(
            f"Entity model '{model_name}' is not recognized or not registered in the micro-kernel."
        )

    @classmethod
    async def create_import_job(
        cls,
        db: AsyncSession,
        content: bytes,
        file_name: str,
        file_format: str,
        model_name: str,
        field_mapping: Dict[str, Any],
        company_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        async_run: bool = True,
    ) -> ImportExportJob:
        """Create and initiate a bulk import job."""
        # Validate model
        cls.resolve_model(model_name)

        job_id = uuid.uuid4()
        storage_path = str(STORAGE_DIR / f"import_{job_id}_{file_name}")
        with open(storage_path, "wb") as f:
            f.write(content)

        # Parse records
        records = DataProcessor.parse_file(file_format, content)

        job = ImportExportJob(
            id=job_id,
            company_id=company_id,
            created_by_id=user_id,
            job_type="import",
            model_name=model_name,
            file_format=file_format.lower().lstrip("."),
            status="processing" if not async_run else "pending",
            total_records=len(records),
            processed_records=0,
            failed_records=0,
            file_name=file_name,
            file_size=len(content),
            storage_path=storage_path,
            field_mapping=field_mapping or {},
            filter_criteria={},
            error_log=[],
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        if async_run:
            try:
                from modules.base.import_export.tasks import process_import_export_job_task
                process_import_export_job_task.delay(str(job.id))
            except Exception as exc:
                logger.warning(f"Celery dispatch failed (running synchronously): {exc}")
                await cls.execute_import_processing(db, job, records)
        else:
            await cls.execute_import_processing(db, job, records)

        return job

    @classmethod
    async def execute_import_processing(
        cls, db: AsyncSession, job: ImportExportJob, records: List[Dict[str, Any]]
    ) -> ImportExportJob:
        """Execute rows insertion with dynamic field mapping and failure tracking."""
        model_cls = cls.resolve_model(job.model_name)
        mapping = job.field_mapping or {}

        processed = 0
        failed = 0
        errors = []

        for idx, row in enumerate(records, start=1):
            try:
                # Apply header mapping
                entity_data: Dict[str, Any] = {}
                for file_col, model_attr in mapping.items():
                    if file_col in row:
                        entity_data[model_attr] = row[file_col]

                # Fallback to direct key matching if mapping is empty or incomplete
                for key, val in row.items():
                    if key not in mapping and hasattr(model_cls, key):
                        entity_data[key] = val

                entity_data["company_id"] = job.company_id
                entity_data["created_by_id"] = job.created_by_id

                instance = model_cls(**entity_data)
                db.add(instance)
                processed += 1
            except Exception as exc:
                failed += 1
                errors.append({"row": idx, "error": str(exc), "data": row})

        try:
            await db.commit()
        except Exception as exc:
            logger.error(f"Commit failed during import {job.id}: {exc}")
            errors.append({"row": "commit", "error": str(exc)})
            failed += processed
            processed = 0

        job.processed_records = processed
        job.failed_records = failed
        job.error_log = errors
        job.status = "completed" if processed > 0 else "failed"
        job.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(job)
        return job

    @classmethod
    async def create_export_job(
        cls,
        db: AsyncSession,
        req: ExportRequest,
        company_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> ImportExportJob:
        """Create and trigger a bulk export job."""
        cls.resolve_model(req.model_name)

        job_id = uuid.uuid4()
        clean_format = req.file_format.lower().lstrip(".")
        file_name = f"export_{req.model_name.replace('.', '_')}_{job_id.hex[:8]}.{clean_format}"
        storage_path = str(STORAGE_DIR / file_name)

        job = ImportExportJob(
            id=job_id,
            company_id=company_id,
            created_by_id=user_id,
            job_type="export",
            model_name=req.model_name,
            file_format=clean_format,
            status="pending",
            total_records=0,
            processed_records=0,
            failed_records=0,
            file_name=file_name,
            file_size=0,
            storage_path=storage_path,
            field_mapping={"fields": req.fields} if req.fields else {},
            filter_criteria=req.filter_criteria,
            error_log=[],
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        if req.async_job:
            try:
                from modules.base.import_export.tasks import process_import_export_job_task
                process_import_export_job_task.delay(str(job.id))
            except Exception as exc:
                logger.warning(f"Celery dispatch failed (running synchronously): {exc}")
                await cls.execute_export_processing(db, job)
        else:
            await cls.execute_export_processing(db, job)

        return job

    @classmethod
    async def execute_export_processing(
        cls, db: AsyncSession, job: ImportExportJob
    ) -> ImportExportJob:
        """Fetch records from database, serialize to requested format, and save."""
        model_cls = cls.resolve_model(job.model_name)
        stmt = select(model_cls).where(model_cls.company_id == job.company_id)
        res = await db.execute(stmt)
        instances = res.scalars().all()

        fields = (job.field_mapping or {}).get("fields")
        rows: List[Dict[str, Any]] = []

        for inst in instances:
            if hasattr(inst, "to_dict"):
                item_dict = inst.to_dict()
            else:
                item_dict = {col.name: getattr(inst, col.name) for col in inst.__table__.columns}

            if fields:
                filtered_item = {f: item_dict.get(f) for f in fields if f in item_dict}
                rows.append(filtered_item)
            else:
                rows.append(item_dict)

        file_bytes = DataProcessor.generate_file(
            file_format=job.file_format,
            rows=rows,
            fieldnames=fields,
        )

        with open(job.storage_path, "wb") as f:
            f.write(file_bytes)

        job.total_records = len(rows)
        job.processed_records = len(rows)
        job.file_size = len(file_bytes)
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(job)
        return job

    @classmethod
    async def process_job_by_id(cls, job_id: str) -> Dict[str, Any]:
        """Standalone entrypoint for Celery background execution."""
        async with AsyncSessionLocal() as session:
            stmt = select(ImportExportJob).where(ImportExportJob.id == uuid.UUID(job_id))
            res = await session.execute(stmt)
            job = res.scalar_one_or_none()
            if not job:
                logger.error(f"Job {job_id} not found.")
                return {"status": "not_found"}

            if job.job_type == "import":
                if job.storage_path and os.path.exists(job.storage_path):
                    with open(job.storage_path, "rb") as f:
                        content = f.read()
                    records = DataProcessor.parse_file(job.file_format, content)
                    await cls.execute_import_processing(session, job, records)
            elif job.job_type == "export":
                await cls.execute_export_processing(session, job)

            return {"status": job.status, "processed": job.processed_records}
