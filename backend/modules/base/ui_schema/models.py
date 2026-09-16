"""Declarative models for View Definitions, UI Schemas, and User Personalization Preferences."""

import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_models import (
    Base,
    BaseModel,
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    AuditActorMixin,
    ExtensibleModelMixin,
    SoftDeleteMixin,
    ArchivableMixin,
    OptimisticLockingMixin,
)


class ViewDefinition(
    Base,
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    AuditActorMixin,
    ExtensibleModelMixin,
    SoftDeleteMixin,
    ArchivableMixin,
    OptimisticLockingMixin,
):
    """Declarative UI View specification defining layout, fields, and widgets for a resource model."""
    __tablename__ = "ui_views"
    __table_args__ = (
        Index("ix_ui_views_model_type", "company_id", "res_model", "view_type"),
    )

    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        doc="Tenant organization association (NULL for global system default views)",
    )
    res_model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        doc="Target resource model name (e.g. 'SaleOrder', 'AccountMove', 'Product')",
    )
    view_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        doc="View classification: 'form', 'list', 'kanban', 'pivot', 'calendar', 'dashboard'",
    )
    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        doc="Human-readable title for this view (e.g. 'Default Sales Order Form')",
    )
    layout_template: Mapped[str] = mapped_column(
        String(50),
        default="split_chatter_right",
        nullable=False,
        doc="Screen layout archetype: 'full_width', 'split_chatter_right', 'split_chatter_bottom', 'master_detail'",
    )
    default_split_ratio: Mapped[float] = mapped_column(
        Float,
        default=65.0,
        nullable=False,
        doc="Initial percentage width allocated to the primary panel in split layouts (e.g. 65.0%)",
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        default=10,
        nullable=False,
        doc="Resolution weight: higher values take precedence when resolving active view",
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Indicates whether this is the designated primary fallback view for the model/type",
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Flag identifying built-in platform fixtures vs tenant studio customizations",
    )
    schema: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Complete declarative JSON layout specification (tabs, sections, columns, widgets, rules)",
    )


class UserViewPreference(BaseModel):
    """User-specific personal view configuration (column order, widths, split ratios, collapsed lanes)."""
    __tablename__ = "ui_user_view_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "res_model", "view_type", "company_id", name="uq_user_view_pref"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="User holding this workspace customization preference",
    )
    res_model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        doc="Target resource model name",
    )
    view_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        doc="View type: 'form', 'list', 'kanban', etc.",
    )
    visible_columns: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        default=None,
        nullable=True,
        doc="Explicit list of visible column field keys in tabular views",
    )
    column_order: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        default=None,
        nullable=True,
        doc="User-customized column sequence order",
    )
    column_widths: Mapped[Optional[Dict[str, int]]] = mapped_column(
        JSONB,
        default=None,
        nullable=True,
        doc="Persisted column widths in pixels: {'name': 250, 'state': 120}",
    )
    preferred_layout: Mapped[Optional[str]] = mapped_column(
        String(50),
        default=None,
        nullable=True,
        doc="User preference override for layout template ('full_width', 'split_chatter_right')",
    )
    preferred_split_ratio: Mapped[Optional[float]] = mapped_column(
        Float,
        default=None,
        nullable=True,
        doc="User's custom dragged panel split percentage (e.g. 72.5%)",
    )
    kanban_collapsed_lanes: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        default=None,
        nullable=True,
        doc="List of Kanban lane identifiers collapsed by the user",
    )
