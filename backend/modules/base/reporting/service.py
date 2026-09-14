"""Report service executing standard and dynamic reports and orchestrating multi-format rendering."""

import uuid
import logging
from typing import Dict, Any, Optional, Tuple, Union
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.base.identity_rbac.models import Company
from modules.base.documents.service import DocumentService
from modules.base.reporting.models import ReportTemplate, ReportDefinition
from modules.base.reporting.registry import report_registry, ReportDataResult
from modules.base.reporting.engine.dynamic_builder import DynamicReportQueryEngine
from modules.base.reporting.renderers.json_renderer import JSONReportRenderer
from modules.base.reporting.renderers.csv_renderer import CSVReportRenderer
from modules.base.reporting.renderers.excel_renderer import ExcelReportRenderer
from modules.base.reporting.renderers.pdf_renderer import PDFReportRenderer

logger = logging.getLogger("sovereign.reporting.service")


class ReportService:
    """Core service for executing reports and rendering multi-format document artifacts."""

    @classmethod
    async def get_company_info(cls, db: AsyncSession, company_id: uuid.UUID) -> Dict[str, Any]:
        """Fetch company branding metadata for report headers."""
        stmt = select(Company).where(Company.id == company_id)
        comp = (await db.execute(stmt)).scalar_one_or_none()
        if not comp:
            return {"name": "Sovereign Platform", "currency": "USD"}
        return {
            "name": comp.name,
            "code": comp.code,
            "currency": getattr(comp, "currency_code", "USD"),
            "vat_id": getattr(comp, "vat_id", None),
        }

    @classmethod
    async def run_report(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        report_code: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> ReportDataResult:
        """Execute either a standard Python report or a dynamic database ReportDefinition."""
        query_params = params or {}

        # 1. Check Standard Report Registry
        std_report = report_registry.get(report_code)
        if std_report:
            result = await std_report.get_data(db, company_id, query_params)
            result.company_info = await cls.get_company_info(db, company_id)
            return result

        # 2. Check Dynamic Database Report Definitions
        stmt = select(ReportDefinition).where(
            ReportDefinition.company_id == company_id,
            ReportDefinition.code == report_code,
            ReportDefinition.deleted_at.is_(None),
        )
        dyn_def = (await db.execute(stmt)).scalar_one_or_none()
        if not dyn_def:
            raise ValueError(f"Report '{report_code}' is not registered as standard or dynamic report.")

        rec_id_raw = query_params.get("record_id") or query_params.get("id")
        if dyn_def.report_type == "document" and rec_id_raw:
            rec_id = uuid.UUID(str(rec_id_raw))
            result = await DynamicReportQueryEngine.execute_document_query(
                db=db,
                company_id=company_id,
                target_model=dyn_def.target_model,
                record_id=rec_id,
                header_fields=dyn_def.header_fields,
                recipient_fields=dyn_def.recipient_fields,
                lines_relationship=dyn_def.lines_relationship,
                lines_fields=dyn_def.lines_fields,
                document_title=dyn_def.document_title or dyn_def.name,
            )
        else:
            result = await DynamicReportQueryEngine.execute_query(
                db=db,
                company_id=company_id,
                target_model=dyn_def.target_model,
                selected_fields=dyn_def.selected_fields,
                filters=dyn_def.filters,
                group_by=dyn_def.group_by,
                aggregations=dyn_def.aggregations,
                order_by=dyn_def.order_by,
            )
        result.report_name = dyn_def.document_title or dyn_def.name
        result.company_info = await cls.get_company_info(db, company_id)
        return result

    @classmethod
    async def resolve_template(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        template_id: Optional[uuid.UUID] = None,
        target_model: Optional[str] = None,
    ) -> Optional[ReportTemplate]:
        """Resolve specific styling template or fall back to default company template."""
        if template_id:
            stmt = select(ReportTemplate).where(
                ReportTemplate.id == template_id,
                ReportTemplate.company_id == company_id,
                ReportTemplate.deleted_at.is_(None),
            )
            tpl = (await db.execute(stmt)).scalar_one_or_none()
            if tpl:
                return tpl

        # Fall back to default template
        stmt = select(ReportTemplate).where(
            ReportTemplate.company_id == company_id,
            ReportTemplate.is_default == True,
            ReportTemplate.deleted_at.is_(None),
        )
        tpl = (await db.execute(stmt)).scalar_one_or_none()
        if tpl:
            return tpl

        # In-memory default fallback template if company has not seeded templates yet
        return ReportTemplate(
            company_id=company_id,
            name="Standard Clean Layout",
            code="standard_clean",
            orientation="portrait",
            primary_color="#1E3A8A",
            show_company_logo=True,
            show_page_numbers=True,
            is_default=True,
        )


    @classmethod
    async def render_report(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        report_code: str,
        output_format: str = "pdf",
        params: Optional[Dict[str, Any]] = None,
        template_id: Optional[uuid.UUID] = None,
    ) -> Tuple[Union[Dict[str, Any], bytes], str, str]:
        """Render report into target format. Returns (payload, mime_type, filename)."""
        data = await cls.run_report(db, company_id, report_code, params)
        template = await cls.resolve_template(db, company_id, template_id, data.target_model)

        safe_code = report_code.replace(".", "_").replace("/", "_")
        timestamp_slug = data.generated_at[:10]

        fmt = output_format.lower()
        if fmt == "json":
            payload = JSONReportRenderer.render(data)
            return payload, "application/json", f"{safe_code}_{timestamp_slug}.json"

        elif fmt == "csv":
            csv_bytes = CSVReportRenderer.render(data)
            return csv_bytes, "text/csv", f"{safe_code}_{timestamp_slug}.csv"

        elif fmt == "xlsx":
            excel_bytes = ExcelReportRenderer.render(data, template)
            return (
                excel_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                f"{safe_code}_{timestamp_slug}.xlsx",
            )

        elif fmt == "pdf":
            pdf_bytes = PDFReportRenderer.render(data, template)
            return pdf_bytes, "application/pdf", f"{safe_code}_{timestamp_slug}.pdf"

        else:
            raise ValueError(f"Unsupported report export format: '{output_format}'")

    @classmethod
    async def export_and_attach(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        report_code: str,
        output_format: str = "pdf",
        params: Optional[Dict[str, Any]] = None,
        template_id: Optional[uuid.UUID] = None,
        res_model: Optional[str] = None,
        res_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """Render binary report document and persist directly into DocumentAttachment."""
        rendered, mime_type, filename = await cls.render_report(
            db=db,
            company_id=company_id,
            report_code=report_code,
            output_format=output_format,
            params=params,
            template_id=template_id,
        )

        if isinstance(rendered, dict):
            import json
            raw_bytes = json.dumps(rendered).encode("utf-8")
        else:
            raw_bytes = rendered

        # Store into DocumentAttachment
        attachment = await DocumentService.create_attachment(
            db=db,
            name=filename,
            content=raw_bytes,
            mime_type=mime_type,
            company_id=company_id,
            res_model=res_model,
            res_id=res_id,
            description=f"Generated report artifact for '{report_code}'",
        )

        return {
            "status": "attached",
            "attachment_id": str(attachment.id),
            "file_name": attachment.name,
            "file_size": attachment.file_size,
            "mime_type": attachment.mime_type,
            "res_model": attachment.res_model,
            "res_id": str(attachment.res_id) if attachment.res_id else None,
        }
