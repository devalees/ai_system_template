"""Pydantic schemas for backup archive creation, telemetry, and integrity verification."""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


class BackupRecordRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "b0000000-0000-0000-0000-000000000001",
                "company_id": "a0000000-0000-0000-0000-000000000001",
                "file_name": "sovereign_backup_20260914_024500.tar.gz",
                "file_size": 1572864,
                "checksum_sha256": "8f4e27e8a93e3d4f107f9c7e0c4f8b9e1d2c3b4a5f6e7d8c9b0a1f2e3d4c5b6a",
                "status": "completed",
                "backup_type": "full",
                "includes_filestore": True,
                "details": {"table_count": 12, "blob_count": 4},
                "completed_at": "2026-09-14T02:45:15Z",
                "created_at": "2026-09-14T02:45:00Z"
            }
        }
    )

    id: uuid.UUID
    company_id: uuid.UUID
    file_name: str
    file_size: int
    checksum_sha256: str
    status: str
    backup_type: str
    includes_filestore: bool
    details: Dict[str, Any]
    completed_at: Optional[datetime]
    created_at: datetime


class CreateBackupRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "backup_type": "full",
                "includes_filestore": True,
                "async_run": True
            }
        }
    )

    backup_type: str = Field("full", description="Type of backup: full, database_only, filestore_only")
    includes_filestore: bool = Field(True, description="Whether to include content-addressable storage attachments")
    async_run: bool = Field(True, description="Whether to generate archive in Celery background or synchronously")


class CreateBackupResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "backup_id": "b0000000-0000-0000-0000-000000000001",
                "status": "generating",
                "message": "Backup generation task queued successfully"
            }
        }
    )

    backup_id: uuid.UUID
    status: str
    message: str


class BackupVerifyResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "valid": True,
                "checksum_sha256": "8f4e27e8a93e3d4f107f9c7e0c4f8b9e1d2c3b4a5f6e7d8c9b0a1f2e3d4c5b6a",
                "total_files": 15,
                "archive_size": 1572864,
                "manifest": {
                    "sovereign_version": "1.0.0",
                    "backup_type": "full",
                    "timestamp": "2026-09-14T02:45:00Z"
                }
            }
        }
    )

    valid: bool
    checksum_sha256: str
    total_files: int
    archive_size: int
    manifest: Dict[str, Any]
