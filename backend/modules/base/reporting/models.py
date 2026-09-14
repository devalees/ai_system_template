"""Database models for Report Templates and Dynamic Report Definitions."""

import uuid
from typing import Optional, Dict, Any, List
from sqlalchemy import String, Text, Boolean, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_models import BaseModel


class ReportTemplate(BaseModel):
    """Visual document styling and layout template for reports."""
    __tablename__ = "report_templates"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    orientation: Mapped[str] = mapped_column(String(20), default="portrait", nullable=False)
    primary_color: Mapped[str] = mapped_column(String(20), default="#1e3a8a", nullable=False)
    show_company_logo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_page_numbers: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    header_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    footer_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ReportDefinition(BaseModel):
    """Dynamic user-defined or system-defined report configuration."""
    __tablename__ = "report_definitions"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    selected_fields: Mapped[List[str]] = mapped_column(JSONB, default=list, nullable=False)
    filters: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    group_by: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    aggregations: Mapped[Optional[Dict[str, str]]] = mapped_column(JSONB, nullable=True)
    order_by: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    report_type: Mapped[str] = mapped_column(String(20), default="tabular", nullable=False)
    document_title: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    header_fields: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    recipient_fields: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    lines_relationship: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    lines_fields: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("report_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    template: Mapped[Optional[ReportTemplate]] = relationship("ReportTemplate", lazy="joined")

