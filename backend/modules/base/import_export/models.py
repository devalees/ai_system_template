"""Database models for bulk import and export job tracking."""

from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.base_models import BaseModel


class ImportExportJob(BaseModel):
    """Job tracking record for bulk data operations."""
    __tablename__ = "import_export_jobs"

    job_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # import | export
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # target model name
    file_format: Mapped[str] = mapped_column(String(10), default="csv", nullable=False)  # csv | xlsx | json
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)  # pending | processing | completed | failed
    total_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    storage_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    field_mapping: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    filter_criteria: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    error_log: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
