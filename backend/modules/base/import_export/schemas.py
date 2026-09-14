"""Pydantic schemas for import and export job requests, telemetry, and execution."""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


class ImportExportJobRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "j0000000-0000-0000-0000-000000000001",
                "company_id": "a0000000-0000-0000-0000-000000000001",
                "job_type": "import",
                "model_name": "lookups.country",
                "file_format": "csv",
                "status": "completed",
                "total_records": 150,
                "processed_records": 150,
                "failed_records": 0,
                "file_name": "iso_countries.csv",
                "file_size": 14200,
                "field_mapping": {"ISO_Code": "code", "Country_Name": "name"},
                "error_log": [],
                "completed_at": "2026-09-14T02:45:00Z",
                "created_at": "2026-09-14T02:44:55Z"
            }
        }
    )

    id: uuid.UUID
    company_id: uuid.UUID
    job_type: str
    model_name: str
    file_format: str
    status: str
    total_records: int
    processed_records: int
    failed_records: int
    file_name: Optional[str]
    file_size: Optional[int]
    field_mapping: Dict[str, Any]
    error_log: List[Dict[str, Any]]
    completed_at: Optional[datetime]
    created_at: datetime


class ExportRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "model_name": "lookups.country",
                "file_format": "csv",
                "fields": ["code", "name", "phone_code"],
                "filter_criteria": {},
                "async_job": True
            }
        }
    )

    model_name: str = Field(..., description="Target entity model name (e.g. lookups.country)")
    file_format: str = Field("csv", description="Export format: csv, xlsx, json")
    fields: Optional[List[str]] = Field(None, description="Subset of fields to include in export")
    filter_criteria: Dict[str, Any] = Field(default_factory=dict, description="Filter criteria AST")
    async_job: bool = Field(True, description="Whether to run in Celery background or return immediate stream")


class ImportJobResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "j0000000-0000-0000-0000-000000000001",
                "status": "processing",
                "message": "Import job queued successfully"
            }
        }
    )

    job_id: uuid.UUID
    status: str
    message: str


class ExportJobResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "j0000000-0000-0000-0000-000000000001",
                "status": "completed",
                "download_url": "/api/v1/import_export/jobs/j0000000-0000-0000-0000-000000000001/download"
            }
        }
    )

    job_id: uuid.UUID
    status: str
    download_url: Optional[str] = None
