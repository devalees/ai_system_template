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
    UserViewPreferencePayload,
    UserViewPreferenceRead,
    ResolvedModelViewBundle,
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
    )


# ============================================================================
# 3. View Definition Studio Persistence
# ============================================================================

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
