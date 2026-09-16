"""Pydantic schemas modeling the Declarative UI grammar, View Layouts, and Studio Customizations."""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# 1. Declarative Field & Widget Schemas
# ============================================================================

class FieldWidgetSchema(BaseModel):
    """Schema descriptor for an individual field widget in forms and tables."""
    model_config = ConfigDict(extra="ignore")

    field_name: str = Field(..., description="Model attribute key name")
    label: str = Field(..., description="Human-readable display label")
    widget_type: str = Field("text", description="UI rendering component: text, number, currency, date, datetime, boolean_switch, many2one_select, one2many_grid, badge, tag_chips, progress_bar, json_editor, avatar, file_upload")
    placeholder: Optional[str] = Field(None, description="Optional placeholder hint text")
    required: bool = Field(False, description="Whether the field is mandatory for submission")
    readonly: bool = Field(False, description="Whether user is forbidden from editing this field (enforced by FLAC or logic)")
    options: Optional[List[Dict[str, Any]]] = Field(None, description="Select choices: [{'value': 'draft', 'label': 'Draft'}]")
    target_model: Optional[str] = Field(None, description="Related model name for relational foreign keys (e.g. 'Party')")
    help_text: Optional[str] = Field(None, description="Tooltip or helper explanation")
    conditional_visibility: Optional[str] = Field(None, description="Frontend expression governing visibility (e.g. 'state == draft')")
    col_span: int = Field(1, ge=1, le=4, description="Grid column span in form layout (1 to 4)")


# ============================================================================
# 2. Form View Schemas & Resizable Sidebar Configuration
# ============================================================================

class FormRowSchema(BaseModel):
    """A row inside a form section holding one or more field columns."""
    model_config = ConfigDict(extra="ignore")
    fields: List[FieldWidgetSchema] = Field(default_factory=list)


class FormSectionSchema(BaseModel):
    """A visual grouping box inside a form tab."""
    model_config = ConfigDict(extra="ignore")
    title: Optional[str] = Field(None, description="Section heading")
    rows: List[FormRowSchema] = Field(default_factory=list)


class FormTabSchema(BaseModel):
    """A tab container in the form body (e.g. 'Order Lines', 'Accounting Defaults')."""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(..., description="Unique tab identifier")
    label: str = Field(..., description="Tab display title")
    sections: List[FormSectionSchema] = Field(default_factory=list)
    subgrid_relationship: Optional[str] = Field(None, description="1:M relationship key if tab hosts child grid (e.g. 'lines')")
    subgrid_columns: Optional[List[FieldWidgetSchema]] = Field(None, description="Column definitions for the 1:M child grid")


class HeaderActionSchema(BaseModel):
    """Action button rendered in the form or list action bar."""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(..., description="Unique action key (e.g. 'confirm', 'cancel')")
    label: str = Field(..., description="Button caption")
    action_type: str = Field("api_call", description="'api_call', 'navigate', 'open_wizard'")
    endpoint: Optional[str] = Field(None, description="REST API route path to execute")
    method: str = Field("POST", description="HTTP method: POST, PUT, DELETE")
    variant: str = Field("secondary", description="Visual styling: 'primary', 'secondary', 'destructive', 'outline'")
    visible_states: Optional[List[str]] = Field(None, description="States where this action is enabled")


class StatusBarSchema(BaseModel):
    """Horizontal clickable state pipeline at the top of a form."""
    model_config = ConfigDict(extra="ignore")
    field_name: str = Field("state", description="State tracking attribute name")
    stages: List[Dict[str, str]] = Field(default_factory=list, description="Ordered stages: [{'value': 'draft', 'label': 'Quotation'}, ...]")
    clickable: bool = Field(False, description="Whether users can click stages directly to transition")


class SidebarConfigSchema(BaseModel):
    """Configuration for docked side-panels (Chatter, Activity timeline, Audit diffs)."""
    model_config = ConfigDict(extra="ignore")
    chatter_enabled: bool = Field(True, description="Enable polymorphic message and note thread")
    activities_enabled: bool = Field(True, description="Enable scheduled tasks and activity tracking")
    audit_trail_enabled: bool = Field(True, description="Enable field modification history and diff viewer")
    dock_position: str = Field("right", description="'right' (split pane) or 'bottom'")
    min_split_ratio: float = Field(35.0, description="Minimum percentage allowed for primary form panel")
    max_split_ratio: float = Field(85.0, description="Maximum percentage allowed for primary form panel")
    collapsible: bool = Field(True, description="Allows collapsing sidebar completely to full width")


class FormViewSchema(BaseModel):
    """Complete declarative Form View specification."""
    model_config = ConfigDict(extra="ignore")
    title_field: Optional[str] = Field("name", description="Model field mapped to the prominent top title")
    subtitle_field: Optional[str] = Field(None, description="Optional secondary identifier field (e.g. 'order_number')")
    status_bar: Optional[StatusBarSchema] = None
    header_actions: List[HeaderActionSchema] = Field(default_factory=list)
    tabs: List[FormTabSchema] = Field(default_factory=list)
    sidebar: SidebarConfigSchema = Field(default_factory=SidebarConfigSchema)


# ============================================================================
# 3. List / Table View Schemas
# ============================================================================

class ListColumnSchema(BaseModel):
    """Column definition for tabular data grids."""
    model_config = ConfigDict(extra="ignore")
    field_name: str = Field(..., description="Model attribute key")
    label: str = Field(..., description="Column header caption")
    widget_type: str = Field("text", description="Cell renderer type: text, currency, badge, date, datetime, boolean")
    width: Optional[int] = Field(None, description="Default pixel width")
    sortable: bool = Field(True, description="Allows sorting on this column")
    align: str = Field("left", description="'left', 'center', 'right'")
    priority: int = Field(1, description="Responsive column priority (1=always visible)")
    default_visible: bool = Field(True, description="Whether column is shown by default")


class QuickFilterSchema(BaseModel):
    """Pre-configured filter chip for fast search."""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(..., description="Unique filter identifier")
    label: str = Field(..., description="Chip caption")
    filter_expr: Dict[str, Any] = Field(..., description="Filter domain criteria: {'state': 'draft'}")


class ListViewSchema(BaseModel):
    """Complete declarative List / Tree View specification."""
    model_config = ConfigDict(extra="ignore")
    columns: List[ListColumnSchema] = Field(default_factory=list)
    default_sort_field: str = Field("created_at", description="Initial sort column")
    default_sort_order: str = Field("desc", description="'asc' or 'desc'")
    search_fields: List[str] = Field(default_factory=list, description="Fields queried by global search bar")
    quick_filters: List[QuickFilterSchema] = Field(default_factory=list)
    batch_actions: List[HeaderActionSchema] = Field(default_factory=list)


# ============================================================================
# 4. Kanban View Schemas (Drag & Drop)
# ============================================================================

class KanbanCardBadgeSchema(BaseModel):
    """Status chip rendered on a Kanban card."""
    model_config = ConfigDict(extra="ignore")
    field_name: str
    color_map: Optional[Dict[str, str]] = None


class KanbanCardSchema(BaseModel):
    """Card layout template inside Kanban lanes."""
    model_config = ConfigDict(extra="ignore")
    title_field: str = Field("name", description="Prominent header title")
    subtitle_field: Optional[str] = Field(None, description="Sub-header text (e.g. code or order_number)")
    badges: List[KanbanCardBadgeSchema] = Field(default_factory=list)
    numeric_fields: List[str] = Field(default_factory=list, description="KPI values (e.g. ['total_amount'])")
    avatar_field: Optional[str] = Field(None, description="User assignee avatar field")
    tags_field: Optional[str] = Field(None, description="Tag chips field")


class KanbanLaneSchema(BaseModel):
    """A vertical column lane in a Kanban board."""
    model_config = ConfigDict(extra="ignore")
    value: str = Field(..., description="State or stage value")
    label: str = Field(..., description="Column header caption")
    color: Optional[str] = Field(None, description="Optional accent color")
    is_folded: bool = Field(False, description="Default folded/collapsed state")


class KanbanViewSchema(BaseModel):
    """Complete declarative Kanban View specification."""
    model_config = ConfigDict(extra="ignore")
    group_by_field: str = Field("state", description="Model attribute partitioning cards into lanes")
    lanes: List[KanbanLaneSchema] = Field(default_factory=list)
    card: KanbanCardSchema = Field(default_factory=KanbanCardSchema)
    drag_drop_enabled: bool = Field(True, description="Enable dragging cards between lanes to update state")
    transition_action: Optional[str] = Field(None, description="Optional transition hook executed upon card drop")


# ============================================================================
# 5. View Definition CRUD Schemas
# ============================================================================

class ViewDefinitionCreate(BaseModel):
    """Schema to create a new UI view layout."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    res_model: str = Field(..., min_length=2, max_length=100)
    view_type: str = Field(..., min_length=2, max_length=30)
    template_code: str = Field("standard", min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=150)
    description: Optional[str] = Field(None, max_length=255)
    target_role_ids: Optional[List[uuid.UUID]] = None
    layout_template: str = Field("split_chatter_right", max_length=50)
    default_split_ratio: float = Field(65.0, ge=20.0, le=100.0)
    priority: int = Field(10, ge=1, le=100)
    is_default: bool = Field(False)
    schema_definition: Dict[str, Any] = Field(default_factory=dict, alias="schema")

    @property
    def schema(self) -> Dict[str, Any]:
        return self.schema_definition


class ViewDefinitionUpdate(BaseModel):
    """Schema to update an existing UI view layout (Studio save)."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    name: Optional[str] = Field(None, min_length=2, max_length=150)
    template_code: Optional[str] = Field(None, min_length=2, max_length=50)
    description: Optional[str] = Field(None, max_length=255)
    target_role_ids: Optional[List[uuid.UUID]] = None
    layout_template: Optional[str] = Field(None, max_length=50)
    default_split_ratio: Optional[float] = Field(None, ge=20.0, le=100.0)
    priority: Optional[int] = Field(None, ge=1, le=100)
    is_default: Optional[bool] = None
    schema_definition: Optional[Dict[str, Any]] = Field(None, alias="schema")

    @property
    def schema(self) -> Optional[Dict[str, Any]]:
        return self.schema_definition


class ViewDefinitionRead(BaseModel):
    """Serialized representation of a stored UI view."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    company_id: Optional[uuid.UUID] = None
    res_model: str
    view_type: str
    template_code: str = "standard"
    name: str
    description: Optional[str] = None
    target_role_ids: Optional[List[uuid.UUID]] = None
    layout_template: str
    default_split_ratio: float
    priority: int
    is_default: bool
    is_system: bool
    schema_definition: Dict[str, Any] = Field(default_factory=dict, alias="schema")
    created_at: datetime
    updated_at: datetime

    @property
    def schema(self) -> Dict[str, Any]:
        return self.schema_definition


class TemplateSummaryRead(BaseModel):
    """Lightweight descriptor for template switching menus."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    res_model: str
    view_type: str
    template_code: str
    name: str
    description: Optional[str] = None
    layout_template: str
    default_split_ratio: float
    is_default: bool
    is_system: bool
    target_role_ids: Optional[List[uuid.UUID]] = None


class CloneTemplatePayload(BaseModel):
    """Payload to clone an existing template into a new custom preset."""
    new_template_code: str = Field(..., min_length=2, max_length=50)
    new_name: str = Field(..., min_length=2, max_length=150)
    new_description: Optional[str] = Field(None, max_length=255)


# ============================================================================
# 6. User Personal View Preferences & Visual Theming
# ============================================================================

class UserViewPreferencePayload(BaseModel):
    """Payload to save individual user view settings."""
    visible_columns: Optional[List[str]] = None
    column_order: Optional[List[str]] = None
    column_widths: Optional[Dict[str, int]] = None
    preferred_layout: Optional[str] = None
    preferred_split_ratio: Optional[float] = Field(None, ge=20.0, le=100.0)
    kanban_collapsed_lanes: Optional[List[str]] = None
    active_template_code: Optional[str] = None
    theme_override: Optional[str] = None
    density_override: Optional[str] = None


class UserViewPreferenceRead(BaseModel):
    """Serialized user workspace preference."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    company_id: uuid.UUID
    res_model: str
    view_type: str
    visible_columns: Optional[List[str]] = None
    column_order: Optional[List[str]] = None
    column_widths: Optional[Dict[str, int]] = None
    preferred_layout: Optional[str] = None
    preferred_split_ratio: Optional[float] = None
    kanban_collapsed_lanes: Optional[List[str]] = None
    active_template_code: Optional[str] = None
    theme_override: Optional[str] = None
    density_override: Optional[str] = None


class UIThemeSettingsSchema(BaseModel):
    """Company-level theme and branding configuration."""
    default_visual_theme: str = Field("sovereign-dark", description="Visual theme preset: sovereign-dark, enterprise-light, high-density-erp, nordic-minimal")
    default_shell_archetype: str = Field("collapsible_sidebar", description="Shell layout: collapsible_sidebar, top_navbar, master_detail")
    primary_brand_color: str = Field("#0ea5e9", description="Primary brand accent color hex")
    font_family: str = Field("Inter, system-ui, sans-serif", description="Application typography")
    allow_user_theme_override: bool = Field(True, description="Allow individual users to choose personal light/dark/density mode")


class UserThemePreferencePayload(BaseModel):
    """Payload for user to toggle personal theme or density."""
    theme_override: Optional[str] = Field(None, description="'sovereign-dark', 'enterprise-light', 'high-density-erp'")
    density_override: Optional[str] = Field(None, description="'compact', 'comfortable'")


class UserThemePreferenceRead(BaseModel):
    """Resolved visual presentation settings delivered to the frontend client."""
    active_theme: str
    active_shell: str
    density: str
    primary_brand_color: str
    font_family: str
    allow_user_override: bool


# ============================================================================
# 7. Model View Bundle (Delivered to Frontend View Engines)
# ============================================================================

class ResolvedModelViewBundle(BaseModel):
    """Complete bundle returned to the frontend containing all available views and user preferences."""
    res_model: str
    model_title: str
    default_view_type: str
    available_view_types: List[str]
    views: Dict[str, Any] = Field(default_factory=dict, description="Map of view_type -> resolved schema dictionary")
    user_preferences: Optional[UserViewPreferenceRead] = None
