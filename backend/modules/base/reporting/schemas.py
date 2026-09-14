"""Pydantic v2 schemas for Reporting & Document Engine."""

import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


# ---------------- Catalog & Execution Schemas ----------------
class ReportCatalogItem(BaseModel):
    """Metadata summary of an available report."""
    code: str = Field(..., description="Unique report code")
    name: str = Field(..., description="Human-friendly report name")
    description: Optional[str] = Field(None, description="Report description")
    target_model: Optional[str] = Field(None, description="Primary ORM model if applicable")
    supported_formats: List[str] = Field(default=["json", "csv", "xlsx", "pdf"], description="Allowed export formats")
    params_schema: Optional[Dict[str, Any]] = Field(None, description="JSON schema specification for query parameters")
    is_dynamic: bool = Field(default=False, description="True if report is user-defined in database")


class ReportDataResponse(BaseModel):
    """Structured response containing aggregated report data rows and totals."""
    report_code: str
    report_name: str
    target_model: Optional[str] = None
    columns: List[Dict[str, Any]]
    rows: List[Dict[str, Any]]
    aggregates: Dict[str, Any] = {}
    total_rows: int
    generated_at: str
    company_info: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class ReportExportRequest(BaseModel):
    """Payload to trigger report data extraction and binary document generation."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "format": "pdf",
                "template_id": None,
                "params": {},
                "save_to_documents": True,
                "res_model": None,
                "res_id": None
            }
        }
    )

    format: str = Field(default="pdf", description="Export format: 'json', 'csv', 'xlsx', or 'pdf'")
    template_id: Optional[uuid.UUID] = Field(None, description="Optional styling template UUID override")
    params: Dict[str, Any] = Field(default_factory=dict, description="Report-specific parameters and filters")
    save_to_documents: bool = Field(default=False, description="Whether to persist generated file in DocumentAttachment")
    res_model: Optional[str] = Field(None, description="Target model to attach document to if save_to_documents=True")
    res_id: Optional[uuid.UUID] = Field(None, description="Target record UUID if save_to_documents=True")


# ---------------- Report Template Schemas ----------------
class ReportTemplateBase(BaseModel):
    name: str = Field(..., description="Template title")
    code: str = Field(..., description="Unique template identifier")
    target_model: Optional[str] = Field(None, description="Target model scope")
    orientation: str = Field(default="portrait", description="'portrait' or 'landscape'")
    primary_color: str = Field(default="#1E3A8A", description="Primary brand hex color")
    show_company_logo: bool = Field(default=True)
    show_page_numbers: bool = Field(default=True)
    header_text: Optional[str] = Field(None)
    footer_text: Optional[str] = Field(None)
    is_default: bool = Field(default=False)
    description: Optional[str] = Field(None)


class ReportTemplateCreate(ReportTemplateBase):
    pass


class ReportTemplateUpdate(BaseModel):
    name: Optional[str] = None
    orientation: Optional[str] = None
    primary_color: Optional[str] = None
    show_company_logo: Optional[bool] = None
    show_page_numbers: Optional[bool] = None
    header_text: Optional[str] = None
    footer_text: Optional[str] = None
    is_default: Optional[bool] = None
    description: Optional[str] = None


class ReportTemplateRead(ReportTemplateBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# ---------------- Dynamic Report Definition Schemas ----------------
class ReportDefinitionBase(BaseModel):
    name: str = Field(..., description="Report display title")
    code: str = Field(..., description="Unique report code (e.g. 'sales_by_country')")
    description: Optional[str] = Field(None)
    target_model: str = Field(..., description="Target ORM model name to query")
    selected_fields: List[str] = Field(default_factory=list, description="Fields to project in tabular output")
    filters: Optional[Dict[str, Any]] = Field(None, description="AST filter tree")
    group_by: Optional[List[str]] = Field(None, description="Fields to group rows by")
    aggregations: Optional[Dict[str, str]] = Field(None, description="Aggregations mapping: {field: 'sum'|'count'|'avg'|'min'|'max'}")
    order_by: Optional[List[str]] = Field(None, description="Order specifications: ['field asc', 'field desc']")
    template_id: Optional[uuid.UUID] = Field(None, description="Default ReportTemplate ID")
    report_type: str = Field(default="tabular", description="Report layout type: 'tabular' or 'document'")
    document_title: Optional[str] = Field(None, description="Formal document title (e.g. 'Tax Invoice', 'Sales Order')")
    header_fields: Optional[List[str]] = Field(None, description="Header card fields (e.g. ['order_date', 'status'])")
    recipient_fields: Optional[List[str]] = Field(None, description="Recipient card fields (e.g. ['partner.name', 'partner.city.name'])")
    lines_relationship: Optional[str] = Field(None, description="1:M relationship attribute name for document lines")
    lines_fields: Optional[List[str]] = Field(None, description="Fields projected for each line item")


class ReportDefinitionCreate(ReportDefinitionBase):
    pass


class ReportDefinitionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    selected_fields: Optional[List[str]] = None
    filters: Optional[Dict[str, Any]] = None
    group_by: Optional[List[str]] = None
    aggregations: Optional[Dict[str, str]] = None
    order_by: Optional[List[str]] = None
    template_id: Optional[uuid.UUID] = None
    report_type: Optional[str] = None
    document_title: Optional[str] = None
    header_fields: Optional[List[str]] = None
    recipient_fields: Optional[List[str]] = None
    lines_relationship: Optional[str] = None
    lines_fields: Optional[List[str]] = None


class ReportDefinitionRead(ReportDefinitionBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    is_system: bool
    created_at: datetime
    updated_at: datetime
    template: Optional[ReportTemplateRead] = None
