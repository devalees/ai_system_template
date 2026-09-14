"""Backup service orchestrating database extraction, filestore aggregation, and archive management."""

import os
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from core.event_bus import event_bus
from core.exceptions import NotFoundException
from modules.base.backup.models import BackupRecord
from modules.base.backup.engine import BackupEngine
from modules.base.documents.models import DocumentAttachment

logger = logging.getLogger("sovereign.backup.service")

BACKUP_DIR = Path("/tmp/sovereign_backups")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


class BackupService:
    """Service orchestrating atomic archive generation, storage, and integrity checks."""

    @classmethod
    async def create_backup(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        backup_type: str = "full",
        includes_filestore: bool = True,
        async_run: bool = True,
    ) -> BackupRecord:
        """Initialize backup record and trigger generation."""
        backup_id = uuid.uuid4()
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        file_name = f"sovereign_backup_{str(company_id)[:8]}_{timestamp_str}.tar.gz"
        storage_path = str(BACKUP_DIR / file_name)

        record = BackupRecord(
            id=backup_id,
            company_id=company_id,
            created_by_id=user_id,
            file_name=file_name,
            file_size=0,
            storage_path=storage_path,
            checksum_sha256="",
            status="generating" if not async_run else "pending",
            backup_type=backup_type,
            includes_filestore=includes_filestore,
            details={},
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)

        if async_run:
            try:
                from modules.base.backup.tasks import generate_backup_task
                generate_backup_task.delay(str(record.id))
            except Exception as exc:
                logger.warning(f"Celery dispatch failed (running synchronously): {exc}")
                await cls.execute_backup(db, record)
        else:
            await cls.execute_backup(db, record)

        return record

    @classmethod
    async def execute_backup(cls, db: AsyncSession, record: BackupRecord) -> BackupRecord:
        """Perform database dump extraction, filestore aggregation, and archive compression."""
        record.status = "generating"
        await db.commit()

        try:
            # 1. Extract SQL Dump
            sql_dump = ""
            if record.backup_type in ("full", "database_only"):
                sql_dump = await BackupEngine.extract_tenant_sql_dump(db, record.company_id)

            # 2. Gather Filestore Attachments
            filestore_files: List[Tuple[str, str]] = []
            if record.includes_filestore and record.backup_type in ("full", "filestore_only"):
                att_stmt = select(DocumentAttachment).where(
                    DocumentAttachment.company_id == record.company_id
                )
                att_res = await db.execute(att_stmt)
                attachments = att_res.scalars().all()
                for att in attachments:
                    from modules.base.documents.storage import StorageEngine
                    full_path = str(StorageEngine.STORAGE_DIR / att.storage_path)
                    filestore_files.append((full_path, att.storage_path))

            # 3. Assemble Manifest
            manifest = {
                "manifest_version": "1.0.0",
                "sovereign_version": "1.0.0",
                "company_id": str(record.company_id),
                "backup_id": str(record.id),
                "backup_type": record.backup_type,
                "includes_filestore": record.includes_filestore,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "filestore_file_count": len(filestore_files),
            }

            # 4. Create Compressed Tarball
            file_size, checksum = BackupEngine.create_tar_archive(
                output_path=record.storage_path,
                sql_dump=sql_dump,
                filestore_files=filestore_files,
                manifest_data=manifest,
            )

            record.file_size = file_size
            record.checksum_sha256 = checksum
            record.status = "completed"
            record.completed_at = datetime.now(timezone.utc)
            record.details = manifest
            await db.commit()
            await db.refresh(record)

            await event_bus.publish(
                "backup.completed",
                {
                    "backup_id": str(record.id),
                    "company_id": str(record.company_id),
                    "file_name": record.file_name,
                    "checksum": record.checksum_sha256,
                },
            )
            return record
        except Exception as exc:
            logger.error(f"Backup generation failed for record {record.id}: {exc}", exc_info=True)
            record.status = "failed"
            record.details = {"error": str(exc)}
            await db.commit()
            await db.refresh(record)
            raise

    @classmethod
    def verify_backup_record(cls, record: BackupRecord) -> Dict[str, Any]:
        """Cryptographically inspect and verify an archived backup package."""
        if not os.path.exists(record.storage_path):
            raise NotFoundException("Physical archive file is missing from storage")

        verification = BackupEngine.verify_archive(record.storage_path)
        if verification["checksum_sha256"] != record.checksum_sha256:
            verification["valid"] = False
            verification["mismatch"] = True

        return verification

    @classmethod
    async def execute_backup_by_id(cls, backup_id: str) -> Dict[str, Any]:
        """Standalone entrypoint for Celery worker processing."""
        async with AsyncSessionLocal() as session:
            stmt = select(BackupRecord).where(BackupRecord.id == uuid.UUID(backup_id))
            res = await session.execute(stmt)
            record = res.scalar_one_or_none()
            if not record:
                logger.error(f"BackupRecord {backup_id} not found.")
                return {"status": "not_found"}

            await cls.execute_backup(session, record)
            return {"status": record.status, "checksum": record.checksum_sha256}
