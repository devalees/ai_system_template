"""REST API endpoints for Reporting & Document Engine."""

import io
import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from modules.base.identity_rbac.dependencies import get_current_user
from modules.base.identity_rbac.models import User
from modules.base.reporting.models import ReportTemplate, ReportDefinition
from modules.base.reporting.registry import report_registry
from modules.base.reporting.service import ReportService
from modules.base.reporting.schemas import (
    ReportCatalogItem,
    ReportDataResponse,
    ReportExportRequest,
    ReportTemplateCreate,
    ReportTemplateUpdate,
    ReportTemplateRead,
    ReportDefinitionCreate,
    ReportDefinitionUpdate,
    ReportDefinitionRead,
)

router = APIRouter()


# ---------------- Report Catalog ----------------
@router.get("/catalog", response_model=List[ReportCatalogItem], tags=["Reporting - Catalog"])
async def list_report_catalog(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Retrieve all available standard and user-defined dynamic reports."""
    # 1. Standard reports from registry
    catalog = report_registry.get_catalog()

    # 2. Dynamic report definitions from database
    stmt = (
        select(ReportDefinition)
        .where(
            ReportDefinition.company_id == current_user.company_id,
            ReportDefinition.deleted_at.is_(None),
        )
        .order_by(ReportDefinition.name.asc())
    )
    dyn_defs = (await db.execute(stmt)).scalars().all()

    for d in dyn_defs:
        catalog.append({
            "code": d.code,
            "name": d.name,
            "description": d.description,
            "target_model": d.target_model,
            "supported_formats": ["json", "csv", "xlsx", "pdf"],
            "params_schema": None,
            "is_dynamic": True,
        })

    return catalog


# ---------------- Report Data & Export ----------------
@router.post("/{report_code}/data", response_model=ReportDataResponse, tags=["Reporting - Execution"])
async def get_report_data(
    report_code: str,
    params: Dict[str, Any] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportDataResponse:
    """Execute report and return pure structured data, rows, and computed metric aggregates."""
    try:
        data = await ReportService.run_report(
            db=db,
            company_id=current_user.company_id,
            report_code=report_code,
            params=params or {},
        )
        return ReportDataResponse(**data.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Report execution failed: {str(exc)}")


@router.post("/{report_code}/export", tags=["Reporting - Execution"])
async def export_report(
    report_code: str,
    payload: ReportExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Render report into requested format (PDF, Excel, CSV) with binary stream or DocumentAttachment persistence."""
    try:
        if payload.save_to_documents:
            attachment_info = await ReportService.export_and_attach(
                db=db,
                company_id=current_user.company_id,
                user_id=current_user.id,
                report_code=report_code,
                output_format=payload.format,
                params=payload.params,
                template_id=payload.template_id,
                res_model=payload.res_model,
                res_id=payload.res_id,
            )
            return attachment_info

        rendered, mime_type, filename = await ReportService.render_report(
            db=db,
            company_id=current_user.company_id,
            report_code=report_code,
            output_format=payload.format,
            params=payload.params,
            template_id=payload.template_id,
        )

        if isinstance(rendered, dict):
            return rendered

        return StreamingResponse(
            io.BytesIO(rendered),
            media_type=mime_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Report render failed: {str(exc)}")


# ---------------- Report Templates CRUD ----------------
@router.get("/templates", response_model=List[ReportTemplateRead], tags=["Reporting - Templates"])
async def list_report_templates(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ReportTemplate]:
    """List document styling templates configured for active tenant company."""
    stmt = (
        select(ReportTemplate)
        .where(
            ReportTemplate.company_id == current_user.company_id,
            ReportTemplate.deleted_at.is_(None),
        )
        .order_by(ReportTemplate.is_default.desc(), ReportTemplate.name.asc())
    )
    return (await db.execute(stmt)).scalars().all()


@router.post("/templates", response_model=ReportTemplateRead, status_code=status.HTTP_201_CREATED, tags=["Reporting - Templates"])
async def create_report_template(
    payload: ReportTemplateCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportTemplate:
    """Create a new report styling template."""
    template = ReportTemplate(
        company_id=current_user.company_id,
        name=payload.name,
        code=payload.code,
        target_model=payload.target_model,
        orientation=payload.orientation,
        primary_color=payload.primary_color,
        show_company_logo=payload.show_company_logo,
        show_page_numbers=payload.show_page_numbers,
        header_text=payload.header_text,
        footer_text=payload.footer_text,
        is_default=payload.is_default,
        description=payload.description,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


@router.get("/templates/{id}", response_model=ReportTemplateRead, tags=["Reporting - Templates"])
async def get_report_template(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportTemplate:
    """Get single report template by ID."""
    stmt = select(ReportTemplate).where(
        ReportTemplate.id == id,
        ReportTemplate.company_id == current_user.company_id,
        ReportTemplate.deleted_at.is_(None),
    )
    template = (await db.execute(stmt)).scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report template not found.")
    return template


@router.patch("/templates/{id}", response_model=ReportTemplateRead, tags=["Reporting - Templates"])
async def update_report_template(
    id: uuid.UUID,
    payload: ReportTemplateUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportTemplate:
    """Update styling template attributes."""
    stmt = select(ReportTemplate).where(
        ReportTemplate.id == id,
        ReportTemplate.company_id == current_user.company_id,
        ReportTemplate.deleted_at.is_(None),
    )
    template = (await db.execute(stmt)).scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report template not found.")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(template, k, v)

    template.updated_by_id = current_user.id
    await db.commit()
    await db.refresh(template)
    return template


@router.delete("/templates/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Reporting - Templates"])
async def delete_report_template(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a report template."""
    stmt = select(ReportTemplate).where(
        ReportTemplate.id == id,
        ReportTemplate.company_id == current_user.company_id,
        ReportTemplate.deleted_at.is_(None),
    )
    template = (await db.execute(stmt)).scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report template not found.")

    template.soft_delete(current_user.id)
    await db.commit()
    return None


# ---------------- Dynamic Report Definitions CRUD ----------------
@router.get("/definitions", response_model=List[ReportDefinitionRead], tags=["Reporting - Definitions"])
async def list_report_definitions(
    target_model: Optional[str] = Query(None, description="Filter by target model"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ReportDefinition]:
    """List dynamic report definitions configured for active tenant company."""
    stmt = (
        select(ReportDefinition)
        .where(
            ReportDefinition.company_id == current_user.company_id,
            ReportDefinition.deleted_at.is_(None),
        )
        .order_by(ReportDefinition.name.asc())
    )
    if target_model:
        stmt = stmt.where(ReportDefinition.target_model.ilike(target_model))

    return (await db.execute(stmt)).scalars().all()


@router.post("/definitions", response_model=ReportDefinitionRead, status_code=status.HTTP_201_CREATED, tags=["Reporting - Definitions"])
async def create_report_definition(
    payload: ReportDefinitionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportDefinition:
    """Create a new dynamic report definition."""
    report_def = ReportDefinition(
        company_id=current_user.company_id,
        name=payload.name,
        code=payload.code,
        description=payload.description,
        target_model=payload.target_model,
        selected_fields=payload.selected_fields,
        filters=payload.filters,
        group_by=payload.group_by,
        aggregations=payload.aggregations,
        order_by=payload.order_by,
        template_id=payload.template_id,
    )
    db.add(report_def)
    await db.commit()
    await db.refresh(report_def)
    return report_def


@router.get("/definitions/{id}", response_model=ReportDefinitionRead, tags=["Reporting - Definitions"])
async def get_report_definition(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportDefinition:
    """Get single dynamic report definition by ID."""
    stmt = select(ReportDefinition).where(
        ReportDefinition.id == id,
        ReportDefinition.company_id == current_user.company_id,
        ReportDefinition.deleted_at.is_(None),
    )
    report_def = (await db.execute(stmt)).scalar_one_or_none()
    if not report_def:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report definition not found.")
    return report_def


@router.patch("/definitions/{id}", response_model=ReportDefinitionRead, tags=["Reporting - Definitions"])
async def update_report_definition(
    id: uuid.UUID,
    payload: ReportDefinitionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportDefinition:
    """Update dynamic report definition."""
    stmt = select(ReportDefinition).where(
        ReportDefinition.id == id,
        ReportDefinition.company_id == current_user.company_id,
        ReportDefinition.deleted_at.is_(None),
    )
    report_def = (await db.execute(stmt)).scalar_one_or_none()
    if not report_def:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report definition not found.")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(report_def, k, v)

    report_def.updated_by_id = current_user.id
    await db.commit()
    await db.refresh(report_def)
    return report_def


@router.delete("/definitions/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Reporting - Definitions"])
async def delete_report_definition(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete dynamic report definition."""
    stmt = select(ReportDefinition).where(
        ReportDefinition.id == id,
        ReportDefinition.company_id == current_user.company_id,
        ReportDefinition.deleted_at.is_(None),
    )
    report_def = (await db.execute(stmt)).scalar_one_or_none()
    if not report_def:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report definition not found.")

    report_def.soft_delete(current_user.id)
    await db.commit()
    return None
