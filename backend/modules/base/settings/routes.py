"""API Routes for Multi-Tenant Module Settings Management."""

import uuid
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from modules.base.identity_rbac.dependencies import get_current_user
from modules.base.identity_rbac.models import User
from modules.base.settings.models import ModuleSettings
from modules.base.settings.schemas import ModuleSettingsUpdate, ModuleSettingsRead, ModuleSettingsResponse
from modules.base.settings.service import SettingsService

router = APIRouter()


@router.get(
    "/",
    response_model=List[ModuleSettingsRead],
    tags=["Settings"],
    summary="List all module settings for the active tenant company",
)
async def list_company_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ModuleSettingsRead]:
    """Retrieve all configured module settings records for current company."""
    stmt = select(ModuleSettings).where(ModuleSettings.company_id == current_user.company_id)
    result = await db.execute(stmt)
    records = result.scalars().all()
    return [
        ModuleSettingsRead(
            module_name=r.module_name,
            company_id=r.company_id,
            settings_data=r.settings_data or {},
            fields=SettingsService.get_module_schema(r.module_name),
        )
        for r in records
    ]


@router.get(
    "/{module_name}",
    response_model=ModuleSettingsResponse,
    tags=["Settings"],
    summary="Get settings configuration for a specific module",
)
async def get_module_settings(
    module_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ModuleSettingsResponse:
    """Fetch cached module settings for the current user's company along with self-describing field schema."""
    data = await SettingsService.get_settings(
        db=db,
        module_name=module_name,
        company_id=current_user.company_id,
    )
    fields = SettingsService.get_module_schema(module_name)
    return ModuleSettingsResponse(
        module_name=module_name,
        company_id=current_user.company_id,
        settings_data=data,
        fields=fields,
    )


@router.patch(
    "/{module_name}",
    response_model=ModuleSettingsResponse,
    tags=["Settings"],
    summary="Update or merge configuration settings for a specific module",
)
async def update_module_settings(
    module_name: str,
    payload: ModuleSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ModuleSettingsResponse:
    """Merge and update key-value JSONB settings for the specified module and invalidate cache."""
    data = await SettingsService.update_settings(
        db=db,
        module_name=module_name,
        company_id=current_user.company_id,
        new_data=payload.settings_data,
    )
    fields = SettingsService.get_module_schema(module_name)
    return ModuleSettingsResponse(
        module_name=module_name,
        company_id=current_user.company_id,
        settings_data=data,
        fields=fields,
    )

