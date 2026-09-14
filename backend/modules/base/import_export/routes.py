"""API routes for streaming import, export, job polling, and artifact downloading."""

import os
import uuid
import json
from typing import List, Optional
from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    Form,
    Response,
    Query,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.exceptions import NotFoundException, ValidationException
from modules.base.identity_rbac.dependencies import get_current_user
from modules.base.identity_rbac.models import User
from modules.base.import_export.models import ImportExportJob
from modules.base.import_export.schemas import (
    ImportExportJobRead,
    ExportRequest,
    ImportJobResponse,
    ExportJobResponse,
)
from modules.base.import_export.service import ImportExportService

router = APIRouter()


@router.post(
    "/import",
    response_model=ImportJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Import/Export Engine"],
    summary="Upload dataset file and trigger bulk import",
)
async def upload_and_import(
    file: UploadFile = File(..., description="CSV, Excel (.xlsx), or JSON file"),
    model_name: str = Form(..., description="Target model name (e.g., lookups.country)"),
    field_mapping: Optional[str] = Form(None, description="Optional JSON mapping of file headers to model fields"),
    async_job: bool = Form(True, description="Whether to process in Celery background or synchronously"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ImportJobResponse:
    """Upload dataset and initiate schema-mapped entity import."""
    content = await file.read()
    file_name = file.filename or "import_data.csv"
    ext = file_name.split(".")[-1].lower()

    mapping_dict = {}
    if field_mapping:
        try:
            mapping_dict = json.loads(field_mapping)
        except Exception as exc:
            raise ValidationException(f"Invalid field_mapping JSON: {exc}")

    job = await ImportExportService.create_import_job(
        db=db,
        content=content,
        file_name=file_name,
        file_format=ext,
        model_name=model_name,
        field_mapping=mapping_dict,
        company_id=current_user.company_id,
        user_id=current_user.id,
        async_run=async_job,
    )

    return ImportJobResponse(
        job_id=job.id,
        status=job.status,
        message="Import dataset successfully received and queued for processing",
    )


@router.post(
    "/export",
    response_model=ExportJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Import/Export Engine"],
    summary="Trigger bulk model export",
)
async def trigger_export(
    export_req: ExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExportJobResponse:
    """Trigger background or direct export of entity records to CSV, Excel, or JSON."""
    job = await ImportExportService.create_export_job(
        db=db,
        req=export_req,
        company_id=current_user.company_id,
        user_id=current_user.id,
    )

    return ExportJobResponse(
        job_id=job.id,
        status=job.status,
        download_url=f"/api/v1/import_export/jobs/{job.id}/download" if job.status == "completed" else None,
    )


@router.get(
    "/jobs",
    response_model=List[ImportExportJobRead],
    tags=["Import/Export Engine"],
    summary="List tenant import/export jobs",
)
async def list_jobs(
    job_type: Optional[str] = Query(None, description="Filter by job_type: import or export"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ImportExportJob]:
    """List recent bulk import and export jobs for the current tenant."""
    query = (
        select(ImportExportJob)
        .where(ImportExportJob.company_id == current_user.company_id)
        .order_by(ImportExportJob.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if job_type:
        query = query.where(ImportExportJob.job_type == job_type)

    res = await db.execute(query)
    return list(res.scalars().all())


@router.get(
    "/jobs/{job_id}",
    response_model=ImportExportJobRead,
    tags=["Import/Export Engine"],
    summary="Get job execution telemetry and progress",
)
async def get_job_details(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ImportExportJob:
    """Retrieve detailed progress, row counts, and error telemetry for a job."""
    stmt = select(ImportExportJob).where(
        ImportExportJob.id == job_id,
        ImportExportJob.company_id == current_user.company_id,
    )
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise NotFoundException(f"Job '{job_id}' not found")
    return job


@router.get(
    "/jobs/{job_id}/download",
    tags=["Import/Export Engine"],
    summary="Download generated export file",
)
async def download_export_file(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stream exported CSV, Excel, or JSON file to client."""
    stmt = select(ImportExportJob).where(
        ImportExportJob.id == job_id,
        ImportExportJob.company_id == current_user.company_id,
    )
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise NotFoundException(f"Job '{job_id}' not found")

    if not job.storage_path or not os.path.exists(job.storage_path):
        raise NotFoundException("Exported file is not available on disk")

    media_type = "application/octet-stream"
    if job.file_format == "csv":
        media_type = "text/csv"
    elif job.file_format in ("xlsx", "excel"):
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif job.file_format == "json":
        media_type = "application/json"

    filename = job.file_name or f"export_{job.id}.{job.file_format}"
    return FileResponse(
        path=job.storage_path,
        media_type=media_type,
        filename=filename,
    )
