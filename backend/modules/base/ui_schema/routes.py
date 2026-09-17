"""REST API routes for Metadata-Driven Dynamic UI Engine, Views Registry, and Preferences."""

import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.context import get_active_company_id
from core.exceptions import ValidationException, EntityNotFoundException
from modules.base.identity_rbac.models import User
from modules.base.identity_rbac.dependencies import get_current_user
from modules.base.automated_actions.introspection import get_registered_models, find_model_class
from modules.base.ui_schema.service import UISchemaService
from modules.base.ui_schema.schemas import (
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
    MenuItemCreate,
    MenuItemUpdate,
    MenuItemRead,
    MenuItemNode,
)

router = APIRouter(prefix="", tags=["Dynamic UI Schema & View Engine"])


def _resolve_company_id(user: User) -> uuid.UUID:
    """Resolve active tenant company ID from context or user profile."""
    cid = get_active_company_id() or user.company_id
    if not cid:
        raise ValidationException("Active company context is required.")
    return cid


# ============================================================================
# 1. Navigation & Model Introspection Catalogs
# ============================================================================

@router.get(
    "/models",
    summary="List introspectable models with supported UI views",
    response_model=List[Dict[str, Any]],
)
async def list_ui_models(
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """List all registered ORM business entities with UI rendering support."""
    registered = get_registered_models()
    result = []
    for m in registered:
        result.append({
            "model_name": m["model_name"],
            "title": m["title"],
            "module_name": m["module_name"],
            "table_name": m["table_name"],
            "description": m["description"],
            "supported_views": ["form", "list", "kanban"],
        })
    return result


# ============================================================================
# 2. View Resolution & Model Bundles
# ============================================================================

@router.get(
    "/views/{res_model}",
    summary="Fetch all active view schemas (bundle) for a model",
    response_model=ResolvedModelViewBundle,
)
async def get_model_view_bundle(
    res_model: str = Path(..., description="Target model name, e.g. 'SaleOrder'"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResolvedModelViewBundle:
    """Fetch complete resolved views (Form, List, Kanban) and preferences for a resource model."""
    company_id = _resolve_company_id(current_user)
    return await UISchemaService.get_resolved_view_bundle(
        res_model=res_model,
        user=current_user,
        db=db,
        company_id=company_id,
    )


@router.get(
    "/views/{res_model}/{view_type}",
    summary="Fetch single resolved view schema for a model and view type",
    response_model=Dict[str, Any],
)
async def get_single_resolved_view(
    res_model: str = Path(..., description="Target model name, e.g. 'SaleOrder'"),
    view_type: str = Path(..., description="View type, e.g. 'form', 'list', 'kanban'"),
    template_code: Optional[str] = Query(None, description="Optional specific template variant code"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Fetch resolved schema with FLAC security pruning and personal preference overlays."""
    company_id = _resolve_company_id(current_user)
    return await UISchemaService.get_resolved_view_schema(
        res_model=res_model,
        view_type=view_type,
        user=current_user,
        db=db,
        company_id=company_id,
        template_code=template_code,
    )


@router.get(
    "/views/{res_model}/{view_type}/templates",
    summary="List available view layout templates for a model and view type",
    response_model=List[TemplateSummaryRead],
)
async def list_model_templates(
    res_model: str = Path(..., description="Target model name, e.g. 'SaleOrder'"),
    view_type: str = Path(..., description="View type, e.g. 'form', 'list', 'kanban'"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[TemplateSummaryRead]:
    """List all available layout templates for a screen accessible by the caller."""
    company_id = _resolve_company_id(current_user)
    return await UISchemaService.list_available_templates(
        res_model=res_model,
        view_type=view_type,
        user=current_user,
        db=db,
        company_id=company_id,
    )


@router.get(
    "/views/{res_model}/{view_type}/templates/{template_code}",
    summary="Fetch specific view layout template schema",
    response_model=Dict[str, Any],
)
async def get_specific_template_view(
    res_model: str = Path(..., description="Target model name, e.g. 'SaleOrder'"),
    view_type: str = Path(..., description="View type, e.g. 'form', 'list', 'kanban'"),
    template_code: str = Path(..., description="Template variant code, e.g. 'quick_entry', 'executive'"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Fetch specific layout template variant applying FLAC pruning and personal preferences."""
    company_id = _resolve_company_id(current_user)
    return await UISchemaService.get_resolved_view_schema(
        res_model=res_model,
        view_type=view_type,
        user=current_user,
        db=db,
        company_id=company_id,
        template_code=template_code,
    )


# ============================================================================
# 3. View Definition Studio Persistence & Cloning
# ============================================================================

@router.post(
    "/views/{view_id}/clone",
    summary="Clone view template into a new custom template (Studio Mode)",
    response_model=ViewDefinitionRead,
    status_code=status.HTTP_201_CREATED,
)
async def clone_custom_view_template(
    view_id: uuid.UUID = Path(..., description="Source view definition ID to clone"),
    payload: CloneTemplatePayload = ...,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ViewDefinitionRead:
    """Clone an existing template into a customized preset with a new unique template code."""
    company_id = _resolve_company_id(current_user)
    try:
        view = await UISchemaService.clone_template(
            view_id=view_id,
            payload=payload,
            user=current_user,
            db=db,
            company_id=company_id,
        )
        return ViewDefinitionRead.model_validate(view)
    except ValueError as exc:
        raise ValidationException(str(exc))

@router.post(
    "/views",
    summary="Create custom view definition (Studio Mode)",
    response_model=ViewDefinitionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_custom_view(
    payload: ViewDefinitionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ViewDefinitionRead:
    """Persist a customized layout definition for a model in the active company."""
    company_id = _resolve_company_id(current_user)
    view = await UISchemaService.create_view_definition(
        payload=payload,
        db=db,
        company_id=company_id,
        is_system=False,
    )
    return ViewDefinitionRead.model_validate(view)


@router.put(
    "/views/{view_id}",
    summary="Update custom view definition",
    response_model=ViewDefinitionRead,
)
async def update_custom_view(
    view_id: uuid.UUID = Path(...),
    payload: ViewDefinitionUpdate = ...,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ViewDefinitionRead:
    """Update field arrangement, sidebar docked settings, or split ratios on a view layout."""
    try:
        view = await UISchemaService.update_view_definition(
            view_id=view_id,
            payload=payload,
            db=db,
        )
        return ViewDefinitionRead.model_validate(view)
    except ValueError as exc:
        raise EntityNotFoundException("ViewDefinition", str(view_id))


@router.delete(
    "/views/{view_id}",
    summary="Delete custom view definition (revert to default)",
    status_code=status.HTTP_200_OK,
)
async def delete_custom_view(
    view_id: uuid.UUID = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Soft-delete a customized view layout to restore platform default layout."""
    deleted = await UISchemaService.delete_view_definition(view_id=view_id, db=db)
    if not deleted:
        raise EntityNotFoundException("ViewDefinition", str(view_id))
    return {"status": "success", "message": "Custom view reverted to default", "view_id": str(view_id)}


# ============================================================================
# 4. User Personal View Preferences
# ============================================================================

@router.get(
    "/preferences/{res_model}/{view_type}",
    summary="Get user personal workspace view preferences",
    response_model=Optional[UserViewPreferenceRead],
)
async def get_user_preference(
    res_model: str = Path(..., description="Target model name"),
    view_type: str = Path(..., description="View type"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Optional[UserViewPreferenceRead]:
    """Retrieve caller's saved column widths, sequence, collapsed lanes, or panel split ratio."""
    company_id = _resolve_company_id(current_user)
    from sqlalchemy import select
    from modules.base.ui_schema.models import UserViewPreference

    stmt = select(UserViewPreference).where(
        UserViewPreference.user_id == current_user.id,
        UserViewPreference.res_model.ilike(res_model),
        UserViewPreference.view_type == view_type,
        UserViewPreference.company_id == company_id,
        UserViewPreference.deleted_at.is_(None),
    )
    pref = (await db.execute(stmt)).scalar_one_or_none()
    if not pref:
        return None
    return UserViewPreferenceRead.model_validate(pref)


@router.put(
    "/preferences/{res_model}/{view_type}",
    summary="Save user personal workspace view preferences",
    response_model=UserViewPreferenceRead,
)
async def save_user_preference(
    payload: UserViewPreferencePayload,
    res_model: str = Path(..., description="Target model name"),
    view_type: str = Path(..., description="View type"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserViewPreferenceRead:
    """Save dragged panel split ratio, column ordering, or widths for the authenticated user."""
    company_id = _resolve_company_id(current_user)
    pref = await UISchemaService.save_user_preference(
        user_id=current_user.id,
        res_model=res_model,
        view_type=view_type,
        company_id=company_id,
        payload=payload,
        db=db,
    )
    return UserViewPreferenceRead.model_validate(pref)


@router.put(
    "/preferences/{res_model}/{view_type}/switch-template",
    summary="1-Click runtime template switcher",
    response_model=UserViewPreferenceRead,
)
async def switch_user_active_template(
    res_model: str = Path(..., description="Target model name"),
    view_type: str = Path(..., description="View type"),
    template_code: str = Query(..., min_length=2, max_length=50, description="Template variant code"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserViewPreferenceRead:
    """Persist active template selection for the current user and model view."""
    company_id = _resolve_company_id(current_user)
    pref = await UISchemaService.switch_user_template(
        user_id=current_user.id,
        res_model=res_model,
        view_type=view_type,
        template_code=template_code,
        company_id=company_id,
        db=db,
    )
    return UserViewPreferenceRead.model_validate(pref)


# ============================================================================
# 5. Global Visual Theming & Application Shell Presets
# ============================================================================

@router.get(
    "/theme",
    summary="Fetch resolved visual theme, shell archetype, and density settings",
    response_model=UserThemePreferenceRead,
)
async def get_resolved_theme(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserThemePreferenceRead:
    """Deliver resolved global appearance tokens, active shell archetype, and density mode."""
    company_id = _resolve_company_id(current_user)
    return await UISchemaService.get_resolved_theme(
        user=current_user,
        db=db,
        company_id=company_id,
    )


@router.put(
    "/theme/preference",
    summary="Save user personal visual theme or density override",
    response_model=UserThemePreferenceRead,
)
async def save_user_theme_preference(
    payload: UserThemePreferencePayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserThemePreferenceRead:
    """Update user personal visual theme mode (dark/light) or table density preference."""
    company_id = _resolve_company_id(current_user)
    return await UISchemaService.save_user_theme_preference(
        user_id=current_user.id,
        payload=payload,
        db=db,
        company_id=company_id,
    )


# ============================================================================
# 6. Hierarchical Navigation Menu Engine (Launcher & Sub-Nav)
# ============================================================================

@router.get(
    "/menus",
    summary="Fetch user hierarchical navigation menu tree",
    response_model=List[MenuItemNode],
)
async def get_user_menus(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[MenuItemNode]:
    """Fetch complete hierarchical navigation menu tree for the current user, pruned by FLAC and RBAC."""
    company_id = _resolve_company_id(current_user)
    return await UISchemaService.get_user_menu_tree(
        user=current_user,
        db=db,
        company_id=company_id,
    )


@router.post(
    "/menus",
    summary="Create custom menu item (Studio Mode)",
    response_model=MenuItemRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_menu_item(
    payload: MenuItemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MenuItemRead:
    """Create a new custom menu item within the active tenant."""
    company_id = _resolve_company_id(current_user)
    return await UISchemaService.create_menu_item(
        payload=payload,
        db=db,
        company_id=company_id,
    )


@router.put(
    "/menus/{menu_id}",
    summary="Update menu item or customize system menu (Studio Mode)",
    response_model=MenuItemRead,
)
async def update_menu_item(
    menu_id: uuid.UUID = Path(..., description="Target menu item UUID"),
    payload: MenuItemUpdate = ...,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MenuItemRead:
    """Update custom menu item or clone a system menu item into a tenant override."""
    company_id = _resolve_company_id(current_user)
    return await UISchemaService.update_menu_item(
        menu_id=menu_id,
        payload=payload,
        db=db,
        company_id=company_id,
    )


@router.delete(
    "/menus/{menu_id}",
    summary="Delete custom menu item or revert override",
    response_model=Dict[str, bool],
)
async def delete_menu_item(
    menu_id: uuid.UUID = Path(..., description="Target menu item UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, bool]:
    """Soft-delete a custom menu item or revert tenant override."""
    company_id = _resolve_company_id(current_user)
    success = await UISchemaService.delete_menu_item(
        menu_id=menu_id,
        db=db,
        company_id=company_id,
        is_superuser=current_user.is_superuser,
    )
    return {"success": success}

