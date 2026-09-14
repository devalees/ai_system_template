"""Standard domain report auditing document storage consumption and MIME type distribution."""

import uuid
import datetime
from typing import Dict, Any, Optional
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from modules.base.documents.models import DocumentAttachment
from modules.base.reporting.registry import BaseReport, ReportDataResult


class StorageAuditReport(BaseReport):
    """Audits company document attachments, content storage sizes, and MIME distribution."""

    report_code = "documents.storage_audit"
    name = "Document Storage & Retention Audit Report"
    description = "Comprehensive audit of uploaded file attachments, content-addressable storage volume, and MIME categories."
    target_model = "DocumentAttachment"
    supported_formats = ["json", "csv", "xlsx", "pdf"]

    async def get_data(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        params: Dict[str, Any],
    ) -> ReportDataResult:
        stmt = (
            sa.select(DocumentAttachment)
            .where(
                DocumentAttachment.company_id == company_id,
                DocumentAttachment.deleted_at.is_(None),
            )
            .order_by(DocumentAttachment.file_size.desc())
            .limit(500)
        )
        records = (await db.execute(stmt)).scalars().all()

        columns = [
            {"name": "name", "title": "Document Name", "type": "string"},
            {"name": "mime_type", "title": "MIME Category", "type": "string"},
            {"name": "file_size_kb", "title": "Size (KB)", "type": "float"},
            {"name": "res_model", "title": "Linked Model", "type": "string"},
            {"name": "created_at", "title": "Upload Date", "type": "datetime"},
        ]

        rows = []
        total_bytes = 0

        for r in records:
            size_kb = round(r.file_size / 1024.0, 2)
            total_bytes += r.file_size
            rows.append({
                "name": r.name,
                "mime_type": r.mime_type,
                "file_size_kb": size_kb,
                "res_model": r.res_model or "Independent",
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "—",
            })

        aggregates = {
            "file_size_kb": round(total_bytes / 1024.0, 2),
        }

        return ReportDataResult(
            report_code=self.report_code,
            report_name=self.name,
            target_model=self.target_model,
            columns=columns,
            rows=rows,
            aggregates=aggregates,
            total_rows=len(rows),
            generated_at=datetime.datetime.utcnow().isoformat(),
        )
