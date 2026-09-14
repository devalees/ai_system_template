"""API routes for backup generation, archive listing, file downloads, and integrity verification."""

import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.exceptions import NotFoundException
from modules.base.identity_rbac.dependencies import get_current_user
from modules.base.identity_rbac.models import User
from modules.base.backup.models import BackupRecord
from modules.base.backup.schemas import (
    BackupRecordRead,
    CreateBackupRequest,
    CreateBackupResponse,
    BackupVerifyResponse,
)
from modules.base.backup.service import BackupService

router = APIRouter()


@router.post(
    "/create",
    response_model=CreateBackupResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Backup & Archive Engine"],
    summary="Trigger atomic backup archive generation",
)
async def create_backup(
    req: CreateBackupRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CreateBackupResponse:
    """Trigger packaging of database dump, filestore blobs, and manifest into a .tar.gz bundle."""
    record = await BackupService.create_backup(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        backup_type=req.backup_type,
        includes_filestore=req.includes_filestore,
        async_run=req.async_run,
    )

    return CreateBackupResponse(
        backup_id=record.id,
        status=record.status,
        message="Backup archive generation successfully initiated",
    )


@router.get(
    "/list",
    response_model=List[BackupRecordRead],
    tags=["Backup & Archive Engine"],
    summary="List tenant backup archives",
)
async def list_backups(
    status_filter: Optional[str] = Query(None, description="Filter by status: completed, generating, failed"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[BackupRecord]:
    """Retrieve historical backup archives for the authenticated company."""
    query = (
        select(BackupRecord)
        .where(BackupRecord.company_id == current_user.company_id)
        .order_by(BackupRecord.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if status_filter:
        query = query.where(BackupRecord.status == status_filter)

    res = await db.execute(query)
    return list(res.scalars().all())


@router.get(
    "/{backup_id}",
    response_model=BackupRecordRead,
    tags=["Backup & Archive Engine"],
    summary="Get backup archive metadata and status",
)
async def get_backup_details(
    backup_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BackupRecord:
    """Retrieve detailed telemetry and checksums for a backup archive."""
    stmt = select(BackupRecord).where(
        BackupRecord.id == backup_id,
        BackupRecord.company_id == current_user.company_id,
    )
    res = await db.execute(stmt)
    record = res.scalar_one_or_none()
    if not record:
        raise NotFoundException(f"Backup '{backup_id}' not found")
    return record


@router.get(
    "/{backup_id}/download",
    tags=["Backup & Archive Engine"],
    summary="Download compressed backup bundle (.tar.gz)",
)
async def download_backup(
    backup_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stream binary .tar.gz backup archive to client."""
    stmt = select(BackupRecord).where(
        BackupRecord.id == backup_id,
        BackupRecord.company_id == current_user.company_id,
    )
    res = await db.execute(stmt)
    record = res.scalar_one_or_none()
    if not record:
        raise NotFoundException(f"Backup '{backup_id}' not found")

    if not record.storage_path or not os.path.exists(record.storage_path):
        raise NotFoundException("Physical backup archive file is missing from storage")

    return FileResponse(
        path=record.storage_path,
        media_type="application/gzip",
        filename=record.file_name,
    )


@router.post(
    "/{backup_id}/verify",
    response_model=BackupVerifyResponse,
    tags=["Backup & Archive Engine"],
    summary="Verify cryptographic integrity of backup archive",
)
async def verify_backup(
    backup_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BackupVerifyResponse:
    """Verify SHA-256 checksum and internal structure (manifest.json and dump.sql)."""
    stmt = select(BackupRecord).where(
        BackupRecord.id == backup_id,
        BackupRecord.company_id == current_user.company_id,
    )
    res = await db.execute(stmt)
    record = res.scalar_one_or_none()
    if not record:
        raise NotFoundException(f"Backup '{backup_id}' not found")

    result = BackupService.verify_backup_record(record)
    return BackupVerifyResponse(**result)


@router.delete(
    "/{backup_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Backup & Archive Engine"],
    summary="Delete backup archive",
)
async def delete_backup(
    backup_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete backup database record and remove physical file from disk."""
    stmt = select(BackupRecord).where(
        BackupRecord.id == backup_id,
        BackupRecord.company_id == current_user.company_id,
    )
    res = await db.execute(stmt)
    record = res.scalar_one_or_none()
    if not record:
        raise NotFoundException(f"Backup '{backup_id}' not found")

    if record.storage_path and os.path.exists(record.storage_path):
        try:
            os.remove(record.storage_path)
        except OSError:
            pass

    await db.delete(record)
    await db.commit()
