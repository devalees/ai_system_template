"""Dynamic UI Schema generation, view resolution, FLAC filtering, and user preferences service."""

import copy
import uuid
import logging
from typing import Dict, Any, List, Optional, Set
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from core.context import get_active_company_id
from modules.base.identity_rbac.models import User, UserGroupLink
from modules.base.identity_rbac.flac_service import FLACService, get_guarded_fields
from modules.base.settings.service import SettingsService
from modules.base.ui_schema.settings import UIThemeSettings
from modules.base.automated_actions.introspection import (
    find_model_class,
    get_model_fields,
    _humanize_name,
    AUTO_MANAGED_FIELDS,
    READ_ONLY_FIELDS,
)
from modules.base.ui_schema.models import ViewDefinition, UserViewPreference
from modules.base.ui_schema.schemas import (
    FieldWidgetSchema,
    FormRowSchema,
    FormSectionSchema,
    FormTabSchema,
    StatusBarSchema,
    HeaderActionSchema,
    SidebarConfigSchema,
    FormViewSchema,
    ListColumnSchema,
    QuickFilterSchema,
    ListViewSchema,
    KanbanLaneSchema,
    KanbanCardBadgeSchema,
    KanbanCardSchema,
    KanbanViewSchema,
    ViewDefinitionCreate,
    ViewDefinitionUpdate,
    ViewDefinitionRead,
    TemplateSummaryRead,
    CloneTemplatePayload,
    UserViewPreferencePayload,
    UserViewPreferenceRead,
    UIThemeSettingsSchema,
    UserThemePreferencePayload,
    UserThemePreferenceRead,
    ResolvedModelViewBundle,
)

logger = logging.getLogger("sovereign.ui_schema.service")

# Internal technical attributes omitted from default dynamic views
INTERNAL_EXCLUDED_FIELDS: Set[str] = {
    "deleted_at",
    "deleted_by_id",
    "created_by_id",
    "updated_by_id",
    "version_id",
    "custom_fields",
    "company_id",
}

NUMERIC_MONEY_KEYWORDS = {"amount", "price", "cost", "total", "subtotal", "tax", "balance", "discount"}


class UISchemaService:
    """Service orchestrating dynamic schema generation, security pruning, and view resolution."""

    # ========================================================================
    # 1. Dynamic Default Schema Generation (Introspection Engine)
    # ========================================================================

    @classmethod
    def generate_dynamic_default_schema(cls, res_model: str, view_type: str) -> Dict[str, Any]:
        """Generate a complete, sensible default view schema on the fly using model introspection."""
        meta = get_model_fields(res_model, depth=1)
        if not meta:
            raise ValueError(f"Target model '{res_model}' was not found in the ORM registry.")

        fields = meta.get("fields", [])
        relationships = meta.get("relationships", [])

        if view_type == "form":
            return cls._build_dynamic_form_schema(res_model, fields, relationships)
        elif view_type == "list":
            return cls._build_dynamic_list_schema(res_model, fields)
        elif view_type == "kanban":
            return cls._build_dynamic_kanban_schema(res_model, fields)
        else:
            raise ValueError(f"Unsupported dynamic view type: '{view_type}'")

    @classmethod
    def _map_field_to_widget(cls, f: Dict[str, Any]) -> FieldWidgetSchema:
        """Map field metadata to a declarative FieldWidgetSchema descriptor."""
        col_name = f["name"]
        col_type = f["type"]
        is_rel = f.get("is_relation", False)
        target_model = f.get("foreign_model")
        choices = f.get("choices")

        widget = "text"
        if is_rel:
            widget = "many2one_select"
        elif choices:
            widget = "badge" if col_name in ("state", "status") else "many2one_select"
        elif col_type in ("integer", "float"):
            if any(kw in col_name.lower() for kw in NUMERIC_MONEY_KEYWORDS):
                widget = "currency"
            else:
                widget = "number"
        elif col_type == "boolean":
            widget = "boolean_switch"
        elif col_type == "date":
            widget = "date"
        elif col_type == "datetime":
            widget = "datetime"
        elif col_type == "json":
            widget = "json_editor"

        return FieldWidgetSchema(
            field_name=col_name,
            label=f["title"],
            widget_type=widget,
            required=f.get("required", False),
            readonly=f.get("read_only", False),
            options=choices,
            target_model=target_model,
            col_span=1,
        )

    @classmethod
    def _build_dynamic_form_schema(
        cls,
        res_model: str,
        fields: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Construct a full FormViewSchema dictionary with status bar, tabs, and resizable split sidebar."""
        # Detect prominent title field
        field_names = [f["name"] for f in fields]
        title_field = "name" if "name" in field_names else (field_names[0] if field_names else "id")
        subtitle_field = "code" if "code" in field_names else ("number" if "number" in field_names else None)

        # Detect state pipeline
        status_bar = None
        state_field = next((f for f in fields if f["name"] in ("state", "status")), None)
        if state_field:
            stages = state_field.get("choices") or [
                {"value": "draft", "label": "Draft"},
                {"value": "confirmed", "label": "Confirmed"},
                {"value": "done", "label": "Done"},
            ]
            status_bar = StatusBarSchema(
                field_name=state_field["name"],
                stages=stages,
                clickable=False,
            )

        # Standard header actions
        header_actions = [
            HeaderActionSchema(id="save", label="Save", action_type="api_call", method="PUT", variant="primary"),
            HeaderActionSchema(id="discard", label="Discard", action_type="navigate", variant="outline"),
        ]

        # Filter candidate fields for the general tab
        active_fields = [
            f for f in fields
            if f["name"] not in INTERNAL_EXCLUDED_FIELDS
            and f["name"] not in ("id", "state", "status")
        ]

        # Group fields into rows of 2 columns each
        rows: List[FormRowSchema] = []
        for i in range(0, len(active_fields), 2):
            chunk = active_fields[i:i + 2]
            row_widgets = [cls._map_field_to_widget(f) for f in chunk]
            rows.append(FormRowSchema(fields=row_widgets))

        general_tab = FormTabSchema(
            id="general",
            label="General Information",
            sections=[
                FormSectionSchema(title="Details", rows=rows),
            ],
        )

        tabs: List[FormTabSchema] = [general_tab]

        # If model has 1:M relationships (e.g. lines, items), create child grid tabs
        for rel in relationships:
            if rel.get("is_collection", False) and rel.get("name") not in ("messages", "activities"):
                sub_cols = []
                if rel.get("fields"):
                    for sub_f in rel["fields"][:6]:
                        if sub_f["name"] not in INTERNAL_EXCLUDED_FIELDS:
                            sub_cols.append(cls._map_field_to_widget(sub_f))
                tabs.append(
                    FormTabSchema(
                        id=f"tab_{rel['name']}",
                        label=rel["title"],
                        subgrid_relationship=rel["name"],
                        subgrid_columns=sub_cols if sub_cols else None,
                    )
                )

        form_schema = FormViewSchema(
            title_field=title_field,
            subtitle_field=subtitle_field,
            status_bar=status_bar,
            header_actions=header_actions,
            tabs=tabs,
            sidebar=SidebarConfigSchema(
                chatter_enabled=True,
                activities_enabled=True,
                audit_trail_enabled=True,
                dock_position="right",
                min_split_ratio=35.0,
                max_split_ratio=85.0,
                collapsible=True,
            ),
        )
        return form_schema.model_dump()

    @classmethod
    def _build_dynamic_list_schema(cls, res_model: str, fields: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Construct a ListViewSchema dictionary with sensible visible columns and sorting."""
        candidate_fields = [
            f for f in fields
            if f["name"] not in INTERNAL_EXCLUDED_FIELDS and f["name"] != "id"
        ]

        columns: List[ListColumnSchema] = []
        search_fields: List[str] = []

        for idx, f in enumerate(candidate_fields):
            widget = cls._map_field_to_widget(f)
            is_visible = idx < 7  # First 7 columns visible by default
            col_schema = ListColumnSchema(
                field_name=f["name"],
                label=f["title"],
                widget_type=widget.widget_type,
                sortable=True,
                align="right" if widget.widget_type in ("number", "currency") else "left",
                priority=1 if idx < 3 else (2 if idx < 6 else 3),
                default_visible=is_visible,
            )
            columns.append(col_schema)

            if f["type"] == "string" and len(search_fields) < 4:
                search_fields.append(f["name"])

        # Quick filters if state or is_active exists
        quick_filters: List[QuickFilterSchema] = []
        has_active = any(f["name"] == "is_active" for f in fields)
        if has_active:
            quick_filters.append(QuickFilterSchema(id="active_only", label="Active", filter_expr={"is_active": True}))

        state_field = next((f for f in fields if f["name"] in ("state", "status")), None)
        if state_field and state_field.get("choices"):
            first_choice = state_field["choices"][0]["value"]
            quick_filters.append(
                QuickFilterSchema(
                    id=f"filter_{first_choice}",
                    label=state_field["choices"][0]["label"],
                    filter_expr={state_field["name"]: first_choice},
                )
            )

        list_schema = ListViewSchema(
            columns=columns,
            default_sort_field="created_at" if any(f["name"] == "created_at" for f in fields) else "id",
            default_sort_order="desc",
            search_fields=search_fields,
            quick_filters=quick_filters,
        )
        return list_schema.model_dump()

    @classmethod
    def _build_dynamic_kanban_schema(cls, res_model: str, fields: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Construct a KanbanViewSchema dictionary with grouped lanes and card badges."""
        field_names = [f["name"] for f in fields]
        state_field = next((f for f in fields if f["name"] in ("state", "status")), None)
        group_by = state_field["name"] if state_field else ("is_active" if "is_active" in field_names else "id")

        lanes: List[KanbanLaneSchema] = []
        if state_field and state_field.get("choices"):
            for c in state_field["choices"]:
                lanes.append(KanbanLaneSchema(value=str(c["value"]), label=c["label"]))
        elif group_by == "is_active":
            lanes = [
                KanbanLaneSchema(value="true", label="Active"),
                KanbanLaneSchema(value="false", label="Archived", is_folded=True),
            ]
        else:
            lanes = [
                KanbanLaneSchema(value="default", label="All Records"),
            ]

        title_field = "name" if "name" in field_names else (field_names[0] if field_names else "id")
        subtitle_field = "code" if "code" in field_names else ("number" if "number" in field_names else None)

        badges = []
        if state_field:
            badges.append(KanbanCardBadgeSchema(field_name=state_field["name"]))

        numeric_fields = [
            f["name"] for f in fields
            if any(kw in f["name"].lower() for kw in NUMERIC_MONEY_KEYWORDS)
        ][:2]

        kanban_schema = KanbanViewSchema(
            group_by_field=group_by,
            lanes=lanes,
            card=KanbanCardSchema(
                title_field=title_field,
                subtitle_field=subtitle_field,
                badges=badges,
                numeric_fields=numeric_fields,
            ),
            drag_drop_enabled=True,
        )
        return kanban_schema.model_dump()

    # ========================================================================
    # 2. FLAC Security Pruning & Readonly Enforcement
    # ========================================================================

    @classmethod
    async def apply_flac_to_schema(
        cls,
        schema: Dict[str, Any],
        res_model: str,
        user: User,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Sanitize view schema according to caller's effective permissions.
        
        - If field is guarded and caller lacks read permission -> completely purged from schema.
        - If field is guarded and caller lacks write permission -> stamped with readonly: True.
        """
        if user.is_superuser:
            return schema

        guarded = get_guarded_fields(res_model.lower())
        if not guarded:
            return schema

        perms = await FLACService.get_effective_permissions(user, db)
        effective_codes = set(perms.all_effective_codes)
        norm_res = res_model.lower()

        forbidden_read_fields: Set[str] = set()
        readonly_fields: Set[str] = set()

        for f_name in guarded:
            has_read = any(
                f".{norm_res}.{f_name}:read" in c
                or c.endswith(f"{norm_res}.{f_name}:read")
                or c == f"{norm_res}.{f_name}:read"
                for c in effective_codes
            )
            has_write = any(
                f".{norm_res}.{f_name}:write" in c
                or c.endswith(f"{norm_res}.{f_name}:write")
                or c == f"{norm_res}.{f_name}:write"
                for c in effective_codes
            )

            if not has_read:
                forbidden_read_fields.add(f_name)
            elif not has_write:
                readonly_fields.add(f_name)

        if not forbidden_read_fields and not readonly_fields:
            return schema

        sanitized = copy.deepcopy(schema)

        # 1. Prune / mark readonly in Form Tabs & Rows
        if "tabs" in sanitized and isinstance(sanitized["tabs"], list):
            for tab in sanitized["tabs"]:
                for section in tab.get("sections", []):
                    new_rows = []
                    for row in section.get("rows", []):
                        filtered_fields = []
                        for f_widget in row.get("fields", []):
                            fname = f_widget.get("field_name")
                            if fname in forbidden_read_fields:
                                continue
                            if fname in readonly_fields:
                                f_widget["readonly"] = True
                            filtered_fields.append(f_widget)
                        if filtered_fields:
                            row["fields"] = filtered_fields
                            new_rows.append(row)
                    section["rows"] = new_rows

        # 2. Prune in List Columns
        if "columns" in sanitized and isinstance(sanitized["columns"], list):
            sanitized["columns"] = [
                col for col in sanitized["columns"]
                if col.get("field_name") not in forbidden_read_fields
            ]

        # 3. Prune in Kanban Cards
        if "card" in sanitized and isinstance(sanitized["card"], dict):
            card = sanitized["card"]
            if "badges" in card and isinstance(card["badges"], list):
                card["badges"] = [
                    b for b in card["badges"]
                    if b.get("field_name") not in forbidden_read_fields
                ]
            if "numeric_fields" in card and isinstance(card["numeric_fields"], list):
                card["numeric_fields"] = [
                    nf for nf in card["numeric_fields"]
                    if nf not in forbidden_read_fields
                ]

        return sanitized

    # ========================================================================
    # 3. View Resolution Engine (User Prefs + Custom + System + Fallback)
    # ========================================================================

    @classmethod
    async def get_resolved_view_schema(
        cls,
        res_model: str,
        view_type: str,
        user: User,
        db: AsyncSession,
        company_id: Optional[uuid.UUID] = None,
        template_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resolve active view layout applying multi-tier resolution hierarchy, user preferences, and FLAC.

        Resolution Hierarchy:
        1. Explicitly requested or User Personal active_template_code (Tenant -> System).
        2. Role-based matching (target_role_ids overlapping with caller's assigned roles).
        3. Tenant default view (company_id == target_company_id, is_default == True).
        4. Platform system default view (is_system == True, is_default == True).
        5. Any available matching view (Tenant -> System).
        6. Dynamic Introspection Fallback.
        """
        target_company_id = company_id or get_active_company_id()

        # Step 0: Query user personal preference
        user_pref = None
        if target_company_id:
            stmt_pref = select(UserViewPreference).where(
                UserViewPreference.user_id == user.id,
                UserViewPreference.res_model.ilike(res_model),
                UserViewPreference.view_type == view_type,
                UserViewPreference.company_id == target_company_id,
                UserViewPreference.deleted_at.is_(None),
            )
            user_pref = (await db.execute(stmt_pref)).scalar_one_or_none()

        desired_template = template_code or (user_pref.active_template_code if user_pref else None)

        custom_view: Optional[ViewDefinition] = None

        # Tier 1: Explicit Template Code (Tenant override -> System preset)
        if desired_template:
            if target_company_id:
                stmt_tpl_custom = (
                    select(ViewDefinition)
                    .where(
                        ViewDefinition.res_model.ilike(res_model),
                        ViewDefinition.view_type == view_type,
                        ViewDefinition.template_code == desired_template,
                        ViewDefinition.company_id == target_company_id,
                        ViewDefinition.deleted_at.is_(None),
                    )
                    .order_by(ViewDefinition.priority.desc())
                )
                custom_view = (await db.execute(stmt_tpl_custom)).scalar_one_or_none()

            if not custom_view:
                stmt_tpl_sys = (
                    select(ViewDefinition)
                    .where(
                        ViewDefinition.res_model.ilike(res_model),
                        ViewDefinition.view_type == view_type,
                        ViewDefinition.template_code == desired_template,
                        ViewDefinition.is_system == True,
                        ViewDefinition.deleted_at.is_(None),
                    )
                    .order_by(ViewDefinition.priority.desc())
                )
                custom_view = (await db.execute(stmt_tpl_sys)).scalar_one_or_none()

        # Tier 2: Role-Based Assignment (target_role_ids)
        if not custom_view:
            user_group_ids: Set[str] = set()
            if not user.is_superuser:
                stmt_groups = select(UserGroupLink.group_id).where(UserGroupLink.user_id == user.id).execution_options(ignore_tenant=True)
                user_group_ids = {str(gid) for gid in (await db.execute(stmt_groups)).scalars().all()}

            if user_group_ids:
                stmt_roles = (
                    select(ViewDefinition)
                    .where(
                        ViewDefinition.res_model.ilike(res_model),
                        ViewDefinition.view_type == view_type,
                        ViewDefinition.target_role_ids.is_not(None),
                        ViewDefinition.deleted_at.is_(None),
                        (ViewDefinition.company_id == target_company_id) | (ViewDefinition.is_system == True),
                    )
                    .order_by(ViewDefinition.priority.desc())
                )
                role_candidates = (await db.execute(stmt_roles)).scalars().all()
                for rc in role_candidates:
                    if rc.target_role_ids:
                        rc_role_strs = {str(rid) for rid in rc.target_role_ids}
                        if rc_role_strs.intersection(user_group_ids):
                            custom_view = rc
                            break

        # Tier 3: Tenant Default View
        if not custom_view and target_company_id:
            stmt_tenant_def = (
                select(ViewDefinition)
                .where(
                    ViewDefinition.res_model.ilike(res_model),
                    ViewDefinition.view_type == view_type,
                    ViewDefinition.company_id == target_company_id,
                    ViewDefinition.is_default == True,
                    ViewDefinition.deleted_at.is_(None),
                )
                .order_by(ViewDefinition.priority.desc())
            )
            custom_view = (await db.execute(stmt_tenant_def)).scalar_one_or_none()

        # Tier 4: System Default View
        if not custom_view:
            stmt_sys_def = (
                select(ViewDefinition)
                .where(
                    ViewDefinition.res_model.ilike(res_model),
                    ViewDefinition.view_type == view_type,
                    ViewDefinition.is_system == True,
                    ViewDefinition.is_default == True,
                    ViewDefinition.deleted_at.is_(None),
                )
                .order_by(ViewDefinition.priority.desc())
            )
            custom_view = (await db.execute(stmt_sys_def)).scalar_one_or_none()

        # Tier 5: Any Available View (fallback before introspection)
        if not custom_view:
            stmt_any = (
                select(ViewDefinition)
                .where(
                    ViewDefinition.res_model.ilike(res_model),
                    ViewDefinition.view_type == view_type,
                    ViewDefinition.deleted_at.is_(None),
                    (ViewDefinition.company_id == target_company_id) | (ViewDefinition.is_system == True),
                )
                .order_by(ViewDefinition.priority.desc())
            )
            custom_view = (await db.execute(stmt_any)).scalars().first()

        # Step 3: Determine raw schema & layout properties
        if custom_view:
            raw_schema = copy.deepcopy(custom_view.schema)
            layout_template = custom_view.layout_template
            split_ratio = custom_view.default_split_ratio
            view_id = str(custom_view.id)
            is_system = custom_view.is_system
            view_name = custom_view.name
            view_description = custom_view.description
            resolved_template_code = custom_view.template_code
        else:
            raw_schema = cls.generate_dynamic_default_schema(res_model, view_type)
            layout_template = "split_chatter_right" if view_type == "form" else "full_width"
            split_ratio = 65.0
            view_id = None
            is_system = True
            view_name = f"Default {res_model} {_humanize_name(view_type)}"
            view_description = None
            resolved_template_code = "standard"

        # Step 4: Apply FLAC security pruning
        secure_schema = await cls.apply_flac_to_schema(raw_schema, res_model, user, db)

        # Step 5: Overlay user preferences onto layout and schema
        is_inspecting_alternate_template = (
            template_code is not None
            and (user_pref is None or (user_pref.active_template_code or "standard") != template_code)
        )

        if user_pref and not is_inspecting_alternate_template:
            if user_pref.preferred_split_ratio is not None and layout_template != "full_width":
                split_ratio = user_pref.preferred_split_ratio
            if user_pref.preferred_layout is not None:
                layout_template = user_pref.preferred_layout

            # List view column ordering and visibility overlay
            if view_type == "list" and "columns" in secure_schema:
                cols_by_name = {c["field_name"]: c for c in secure_schema["columns"]}
                ordered_cols = []
                if user_pref.column_order:
                    for col_key in user_pref.column_order:
                        if col_key in cols_by_name:
                            ordered_cols.append(cols_by_name.pop(col_key))
                # Append remaining columns not explicitly ordered
                ordered_cols.extend(cols_by_name.values())

                if user_pref.visible_columns:
                    for col in ordered_cols:
                        col["default_visible"] = col["field_name"] in user_pref.visible_columns

                if user_pref.column_widths:
                    for col in ordered_cols:
                        if col["field_name"] in user_pref.column_widths:
                            col["width"] = user_pref.column_widths[col["field_name"]]

                secure_schema["columns"] = ordered_cols

            # Kanban view folded lanes overlay
            if view_type == "kanban" and "lanes" in secure_schema and user_pref.kanban_collapsed_lanes:
                for lane in secure_schema["lanes"]:
                    if lane.get("value") in user_pref.kanban_collapsed_lanes:
                        lane["is_folded"] = True

        return {
            "view_id": view_id,
            "res_model": res_model,
            "view_type": view_type,
            "template_code": resolved_template_code,
            "name": view_name,
            "description": view_description,
            "layout_template": layout_template,
            "default_split_ratio": split_ratio,
            "is_system": is_system,
            "schema": secure_schema,
            "user_preference": UserViewPreferenceRead.model_validate(user_pref) if user_pref else None,
        }

    @classmethod
    async def get_resolved_view_bundle(
        cls,
        res_model: str,
        user: User,
        db: AsyncSession,
        company_id: Optional[uuid.UUID] = None,
    ) -> ResolvedModelViewBundle:
        """Fetch full bundle of all active views (form, list, kanban) for a given model."""
        target_company_id = company_id or get_active_company_id()
        model_cls = find_model_class(res_model)
        model_title = _humanize_name(model_cls.__name__) if model_cls else _humanize_name(res_model)

        views_map: Dict[str, Any] = {}
        for vt in ("form", "list", "kanban"):
            try:
                resolved = await cls.get_resolved_view_schema(
                    res_model=res_model,
                    view_type=vt,
                    user=user,
                    db=db,
                    company_id=target_company_id,
                )
                views_map[vt] = resolved
            except Exception as exc:
                logger.warning(f"Could not resolve '{vt}' view for '{res_model}': {exc}")

        # Get list preference as primary default if exists
        pref_stmt = select(UserViewPreference).where(
            UserViewPreference.user_id == user.id,
            UserViewPreference.res_model.ilike(res_model),
            UserViewPreference.company_id == target_company_id,
            UserViewPreference.deleted_at.is_(None),
        ).limit(1)
        latest_pref = (await db.execute(pref_stmt)).scalar_one_or_none()

        return ResolvedModelViewBundle(
            res_model=res_model,
            model_title=model_title,
            default_view_type="list",
            available_view_types=list(views_map.keys()),
            views=views_map,
            user_preferences=UserViewPreferenceRead.model_validate(latest_pref) if latest_pref else None,
        )

    # ========================================================================
    # 4. View Definition CRUD & Multi-Template Management
    # ========================================================================

    @classmethod
    async def list_available_templates(
        cls,
        res_model: str,
        view_type: str,
        user: User,
        db: AsyncSession,
        company_id: Optional[uuid.UUID] = None,
    ) -> List[TemplateSummaryRead]:
        """List all available layout templates for a screen accessible by the caller."""
        target_company_id = company_id or get_active_company_id()

        user_group_ids: Set[str] = set()
        if not user.is_superuser:
            stmt_groups = (
                select(UserGroupLink.group_id)
                .where(UserGroupLink.user_id == user.id)
                .execution_options(ignore_tenant=True)
            )
            user_group_ids = {str(gid) for gid in (await db.execute(stmt_groups)).scalars().all()}

        stmt = (
            select(ViewDefinition)
            .where(
                ViewDefinition.res_model.ilike(res_model),
                ViewDefinition.view_type == view_type,
                ViewDefinition.deleted_at.is_(None),
                (ViewDefinition.company_id == target_company_id) | (ViewDefinition.is_system == True),
            )
            .order_by(ViewDefinition.priority.desc(), ViewDefinition.created_at.desc())
        )
        all_views = (await db.execute(stmt)).scalars().all()

        # Deduplicate by template_code: tenant custom views override system presets
        seen_codes: Dict[str, ViewDefinition] = {}
        for v in all_views:
            # Check role-based targeting
            if v.target_role_ids and not user.is_superuser:
                role_ids = {str(r) for r in v.target_role_ids}
                if not role_ids.intersection(user_group_ids):
                    continue

            if v.template_code not in seen_codes:
                seen_codes[v.template_code] = v
            elif not seen_codes[v.template_code].company_id and v.company_id:
                seen_codes[v.template_code] = v

        return [TemplateSummaryRead.model_validate(v) for v in seen_codes.values()]

    @classmethod
    async def clone_template(
        cls,
        view_id: uuid.UUID,
        payload: CloneTemplatePayload,
        user: User,
        db: AsyncSession,
        company_id: Optional[uuid.UUID] = None,
    ) -> ViewDefinition:
        """Clone an existing view definition into a new custom template variant for Studio."""
        target_company_id = company_id or get_active_company_id()
        stmt = select(ViewDefinition).where(ViewDefinition.id == view_id, ViewDefinition.deleted_at.is_(None))
        source = (await db.execute(stmt)).scalar_one_or_none()
        if not source:
            raise ValueError(f"Source view definition '{view_id}' not found.")

        # Ensure new_template_code uniqueness for this model & view_type in the tenant
        stmt_check = select(ViewDefinition).where(
            ViewDefinition.res_model.ilike(source.res_model),
            ViewDefinition.view_type == source.view_type,
            ViewDefinition.template_code == payload.new_template_code,
            ViewDefinition.company_id == target_company_id,
            ViewDefinition.deleted_at.is_(None),
        )
        existing = (await db.execute(stmt_check)).scalar_one_or_none()
        if existing:
            raise ValueError(
                f"Template code '{payload.new_template_code}' already exists for {source.res_model} {source.view_type}."
            )

        cloned = ViewDefinition(
            company_id=target_company_id,
            res_model=source.res_model,
            view_type=source.view_type,
            template_code=payload.new_template_code,
            name=payload.new_name,
            description=payload.new_description or f"Cloned from {source.name}",
            layout_template=source.layout_template,
            default_split_ratio=source.default_split_ratio,
            priority=20,
            is_default=False,
            is_system=False,
            schema=copy.deepcopy(source.schema),
        )
        db.add(cloned)
        await db.commit()
        await db.refresh(cloned)
        return cloned

    @classmethod
    async def create_view_definition(
        cls,
        payload: ViewDefinitionCreate,
        db: AsyncSession,
        company_id: Optional[uuid.UUID] = None,
        is_system: bool = False,
    ) -> ViewDefinition:
        """Create and persist a custom or system ViewDefinition."""
        target_company_id = company_id or get_active_company_id()
        view = ViewDefinition(
            company_id=None if is_system else target_company_id,
            res_model=payload.res_model,
            view_type=payload.view_type,
            template_code=payload.template_code,
            name=payload.name,
            description=payload.description,
            target_role_ids=payload.target_role_ids,
            layout_template=payload.layout_template,
            default_split_ratio=payload.default_split_ratio,
            priority=payload.priority,
            is_default=payload.is_default,
            is_system=is_system,
            schema=payload.schema,
        )
        db.add(view)
        await db.commit()
        await db.refresh(view)
        return view

    @classmethod
    async def update_view_definition(
        cls,
        view_id: uuid.UUID,
        payload: ViewDefinitionUpdate,
        db: AsyncSession,
    ) -> ViewDefinition:
        """Update an existing ViewDefinition (e.g. from Studio editor)."""
        stmt = select(ViewDefinition).where(ViewDefinition.id == view_id, ViewDefinition.deleted_at.is_(None))
        view = (await db.execute(stmt)).scalar_one_or_none()
        if not view:
            raise ValueError(f"View definition '{view_id}' not found.")

        if payload.name is not None:
            view.name = payload.name
        if payload.template_code is not None:
            view.template_code = payload.template_code
        if payload.description is not None:
            view.description = payload.description
        if payload.target_role_ids is not None:
            view.target_role_ids = payload.target_role_ids
        if payload.layout_template is not None:
            view.layout_template = payload.layout_template
        if payload.default_split_ratio is not None:
            view.default_split_ratio = payload.default_split_ratio
        if payload.priority is not None:
            view.priority = payload.priority
        if payload.is_default is not None:
            view.is_default = payload.is_default
        if payload.schema is not None:
            view.schema = payload.schema

        await db.commit()
        await db.refresh(view)
        return view

    @classmethod
    async def delete_view_definition(cls, view_id: uuid.UUID, db: AsyncSession) -> bool:
        """Soft-delete a custom ViewDefinition, reverting back to system defaults."""
        stmt = select(ViewDefinition).where(ViewDefinition.id == view_id, ViewDefinition.deleted_at.is_(None))
        view = (await db.execute(stmt)).scalar_one_or_none()
        if not view:
            return False
        view.soft_delete()
        await db.commit()
        return True

    # ========================================================================
    # 5. User Personal View Preferences & Template Switcher
    # ========================================================================

    @classmethod
    async def switch_user_template(
        cls,
        user_id: uuid.UUID,
        res_model: str,
        view_type: str,
        template_code: str,
        company_id: uuid.UUID,
        db: AsyncSession,
    ) -> UserViewPreference:
        """Switch user's active template variant for a specific view."""
        stmt = select(UserViewPreference).where(
            UserViewPreference.user_id == user_id,
            UserViewPreference.res_model.ilike(res_model),
            UserViewPreference.view_type == view_type,
            UserViewPreference.company_id == company_id,
            UserViewPreference.deleted_at.is_(None),
        )
        pref = (await db.execute(stmt)).scalar_one_or_none()
        if not pref:
            pref = UserViewPreference(
                user_id=user_id,
                res_model=res_model,
                view_type=view_type,
                company_id=company_id,
            )
            db.add(pref)

        pref.active_template_code = template_code
        pref.preferred_layout = None
        pref.preferred_split_ratio = None
        await db.commit()
        await db.refresh(pref)
        return pref

    @classmethod
    async def save_user_preference(
        cls,
        user_id: uuid.UUID,
        res_model: str,
        view_type: str,
        company_id: uuid.UUID,
        payload: UserViewPreferencePayload,
        db: AsyncSession,
    ) -> UserViewPreference:
        """Save or update user personal view preferences (splitter ratio, column widths, collapsed lanes)."""
        stmt = select(UserViewPreference).where(
            UserViewPreference.user_id == user_id,
            UserViewPreference.res_model.ilike(res_model),
            UserViewPreference.view_type == view_type,
            UserViewPreference.company_id == company_id,
            UserViewPreference.deleted_at.is_(None),
        )
        pref = (await db.execute(stmt)).scalar_one_or_none()

        if not pref:
            pref = UserViewPreference(
                user_id=user_id,
                res_model=res_model,
                view_type=view_type,
                company_id=company_id,
            )
            db.add(pref)

        if payload.visible_columns is not None:
            pref.visible_columns = payload.visible_columns
        if payload.column_order is not None:
            pref.column_order = payload.column_order
        if payload.column_widths is not None:
            pref.column_widths = payload.column_widths
        if payload.preferred_layout is not None:
            pref.preferred_layout = payload.preferred_layout
        if payload.preferred_split_ratio is not None:
            pref.preferred_split_ratio = payload.preferred_split_ratio
        if payload.kanban_collapsed_lanes is not None:
            pref.kanban_collapsed_lanes = payload.kanban_collapsed_lanes
        if payload.active_template_code is not None:
            pref.active_template_code = payload.active_template_code
        if payload.theme_override is not None:
            pref.theme_override = payload.theme_override
        if payload.density_override is not None:
            pref.density_override = payload.density_override

        await db.commit()
        await db.refresh(pref)
        return pref

    # ========================================================================
    # 6. Global Visual Theming & Application Shell Settings
    # ========================================================================

    @classmethod
    async def get_resolved_theme(
        cls,
        user: User,
        db: AsyncSession,
        company_id: Optional[uuid.UUID] = None,
    ) -> UserThemePreferenceRead:
        """Resolve global visual styling, theme preset, and shell archetype for the client."""
        target_company_id = company_id or get_active_company_id()

        # 1. Retrieve company-level ModuleSettings
        settings_dict: Dict[str, Any] = {}
        if target_company_id:
            try:
                settings_dict = await SettingsService.get_settings(
                    db=db,
                    module_name="ui_schema",
                    company_id=target_company_id,
                )
            except Exception as exc:
                logger.warning(f"Could not load UI theme settings: {exc}")

        if not settings_dict:
            settings_dict = SettingsService.get_default_settings("ui_schema")

        default_theme = settings_dict.get("default_visual_theme", "sovereign-dark")
        default_shell = settings_dict.get("default_shell_archetype", "collapsible_sidebar")
        default_density = settings_dict.get("default_density", "comfortable")
        brand_color = settings_dict.get("primary_brand_color", "#0ea5e9")
        font_family = settings_dict.get("font_family", "Inter, system-ui, sans-serif")
        allow_override = settings_dict.get("allow_user_theme_override", True)

        active_theme = default_theme
        active_density = default_density

        # 2. Check personal user preference override
        if allow_override and target_company_id:
            stmt_pref = select(UserViewPreference).where(
                UserViewPreference.user_id == user.id,
                UserViewPreference.res_model == "__global__",
                UserViewPreference.view_type == "__global__",
                UserViewPreference.company_id == target_company_id,
                UserViewPreference.deleted_at.is_(None),
            )
            user_pref = (await db.execute(stmt_pref)).scalar_one_or_none()
            if user_pref:
                if user_pref.theme_override:
                    active_theme = user_pref.theme_override
                if user_pref.density_override:
                    active_density = user_pref.density_override

        return UserThemePreferenceRead(
            active_theme=active_theme,
            active_shell=default_shell,
            density=active_density,
            primary_brand_color=brand_color,
            font_family=font_family,
            allow_user_override=allow_override,
        )

    @classmethod
    async def save_user_theme_preference(
        cls,
        user_id: uuid.UUID,
        payload: UserThemePreferencePayload,
        db: AsyncSession,
        company_id: uuid.UUID,
    ) -> UserThemePreferenceRead:
        """Save user personal theme or density mode preference."""
        stmt = select(UserViewPreference).where(
            UserViewPreference.user_id == user_id,
            UserViewPreference.res_model == "__global__",
            UserViewPreference.view_type == "__global__",
            UserViewPreference.company_id == company_id,
            UserViewPreference.deleted_at.is_(None),
        )
        pref = (await db.execute(stmt)).scalar_one_or_none()
        if not pref:
            pref = UserViewPreference(
                user_id=user_id,
                res_model="__global__",
                view_type="__global__",
                company_id=company_id,
            )
            db.add(pref)

        if payload.theme_override is not None:
            pref.theme_override = payload.theme_override
        if payload.density_override is not None:
            pref.density_override = payload.density_override

        await db.commit()
        await db.refresh(pref)

        # Retrieve user object to return resolved theme
        user_stmt = select(User).where(User.id == user_id)
        user = (await db.execute(user_stmt)).scalar_one()
        return await cls.get_resolved_theme(user=user, db=db, company_id=company_id)

