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
        Index("ix_ui_views_model_template", "company_id", "res_model", "view_type", "template_code"),
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
    template_code: Mapped[str] = mapped_column(
        String(50),
        default="standard",
        nullable=False,
        index=True,
        doc="Unique identifier for template variant, e.g. 'standard', 'quick_entry', 'executive'",
    )
    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        doc="Human-readable title for this view (e.g. 'Default Sales Order Form')",
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(255),
        default=None,
        nullable=True,
        doc="Short explanation of when to use this template variant",
    )
    target_role_ids: Mapped[Optional[List[uuid.UUID]]] = mapped_column(
        JSONB,
        default=None,
        nullable=True,
        doc="Optional list of RBAC group/role IDs for role-based auto-routing",
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
    active_template_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        default=None,
        nullable=True,
        doc="User's currently selected active template variant",
    )
    theme_override: Mapped[Optional[str]] = mapped_column(
        String(50),
        default=None,
        nullable=True,
        doc="User personal visual theme override ('sovereign-dark', 'enterprise-light', 'high-density-erp')",
    )
    density_override: Mapped[Optional[str]] = mapped_column(
        String(20),
        default=None,
        nullable=True,
        doc="User table/form density preference ('compact', 'comfortable')",
    )


class MenuItem(
    Base,
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    AuditActorMixin,
    ExtensibleModelMixin,
    SoftDeleteMixin,
    ArchivableMixin,
    OptimisticLockingMixin,
):
    """Hierarchical navigation menu item for application launcher and module sub-navigation."""
    __tablename__ = "ui_menus"
    __table_args__ = (
        Index("ix_ui_menus_company_code", "company_id", "code"),
        Index("ix_ui_menus_parent", "company_id", "parent_id", "sequence"),
        Index("ix_ui_menus_module", "company_id", "module_name"),
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        doc="Human-readable translatable menu label (e.g. 'Quotations', 'Invoices')",
    )
    code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        doc="Unique menu identifier (e.g. 'sales.root', 'sales.orders.quotations')",
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ui_menus.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Parent menu item ID forming a recursive multi-level navigation tree",
    )
    sequence: Mapped[int] = mapped_column(
        Integer,
        default=10,
        nullable=False,
        doc="Display order sequence (lower numbers appear first)",
    )
    icon: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        doc="Lucide icon identifier (e.g. 'shopping-bag', 'receipt', 'settings')",
    )
    module_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        doc="Module namespace defining ownership (e.g. 'sales', 'accounting', 'purchases')",
    )
    res_model: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        index=True,
        doc="Target resource model to open (e.g. 'SaleOrder', 'AccountMove', 'Product')",
    )
    action_type: Mapped[str] = mapped_column(
        String(32),
        default="window",
        nullable=False,
        doc="Action type: 'window' (standard model view), 'url' (external link), 'client' (custom view)",
    )
    default_view: Mapped[str] = mapped_column(
        String(32),
        default="list",
        nullable=False,
        doc="Default landing view type: 'list', 'kanban', 'form', 'report', 'dashboard'",
    )
    route_path: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Optional client-side route path (e.g. '/sales/quotations', '/settings/general')",
    )
    domain_filter: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        default=None,
        nullable=True,
        doc="Optional JSONB query filter applied upon opening (e.g. {'state': 'draft'})",
    )
    target_role_ids: Mapped[Optional[List[uuid.UUID]]] = mapped_column(
        JSONB,
        default=None,
        nullable=True,
        doc="Optional list of role UUIDs required to access this menu item",
    )
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Tenant organization association (NULL for global platform defaults)",
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Boolean identifying immutable platform fixtures vs tenant studio customizations",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Operational visibility toggle",
    )

    children = relationship(
        "MenuItem",
        cascade="all, delete-orphan",
        order_by="MenuItem.sequence",
    )

