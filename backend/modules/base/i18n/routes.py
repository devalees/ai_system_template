"""API routes for translation catalogs, locale detection, and multi-lingual terms."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.context import get_active_locale
from core.database import get_db
from core.exceptions import NotFoundException
from modules.base.identity_rbac.dependencies import get_current_user
from modules.base.identity_rbac.models import User
from modules.base.i18n.models import TranslationTerm
from modules.base.i18n.schemas import (
    LocaleInfo,
    TranslationTermRead,
    TranslationTermCreate,
    TranslationTermUpdate,
    TranslateRequest,
    TranslateResponse,
    CatalogResponse,
)
from modules.base.i18n.service import I18nService

router = APIRouter()


@router.get(
    "/locales",
    response_model=List[LocaleInfo],
    tags=["Internationalization (i18n)"],
    summary="List supported system locales and script directions",
)
async def list_supported_locales() -> List[LocaleInfo]:
    """Retrieve supported system languages and layout directions (LTR/RTL)."""
    return I18nService.get_supported_locales()


@router.get(
    "/catalog",
    response_model=CatalogResponse,
    tags=["Internationalization (i18n)"],
    summary="Retrieve translation catalog for active or requested locale",
)
async def get_translation_catalog(
    locale: Optional[str] = Query(None, description="ISO locale code (defaults to Accept-Language or en)"),
    module_name: Optional[str] = Query(None, description="Optional module namespace filter"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CatalogResponse:
    """Compile dictionary of UI strings for the active or requested language."""
    target_locale = locale or get_active_locale() or "en"
    return await I18nService.get_catalog(
        db=db,
        target_locale=target_locale,
        company_id=current_user.company_id,
        module_name=module_name,
    )


@router.post(
    "/translate",
    response_model=TranslateResponse,
    tags=["Internationalization (i18n)"],
    summary="Translate string into target locale",
)
async def translate_text(
    req: TranslateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TranslateResponse:
    """Dynamically look up translation for a single term."""
    translated = await I18nService.translate_term(
        db=db,
        source_text=req.text,
        target_locale=req.target_locale,
        company_id=current_user.company_id,
        module_name=req.module_name,
    )
    return TranslateResponse(
        source_text=req.text,
        translated_text=translated,
        locale=req.target_locale,
    )


@router.get(
    "/terms",
    response_model=List[TranslationTermRead],
    tags=["Internationalization (i18n)"],
    summary="List custom tenant translation terms",
)
async def list_translation_terms(
    module_name: Optional[str] = Query(None, description="Filter by module"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[TranslationTerm]:
    """Retrieve registered custom translation terms for the active company."""
    query = (
        select(TranslationTerm)
        .where(
            TranslationTerm.company_id == current_user.company_id,
            TranslationTerm.deleted_at.is_(None),
        )
        .order_by(TranslationTerm.source_text.asc())
    )
    if module_name:
        query = query.where(TranslationTerm.module_name == module_name)

    res = await db.execute(query)
    return list(res.scalars().all())


@router.post(
    "/terms",
    response_model=TranslationTermRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Internationalization (i18n)"],
    summary="Create or override a translation term",
)
async def create_translation_term(
    term_in: TranslationTermCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TranslationTerm:
    """Add or customize a localized term for the active tenant."""
    term = TranslationTerm(
        company_id=current_user.company_id,
        created_by_id=current_user.id,
        **term_in.model_dump(),
    )
    db.add(term)
    await db.commit()
    await db.refresh(term)
    return term


@router.get(
    "/terms/{term_id}",
    response_model=TranslationTermRead,
    tags=["Internationalization (i18n)"],
    summary="Get translation term details",
)
async def get_translation_term(
    term_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TranslationTerm:
    """Retrieve details for a specific translation term."""
    stmt = select(TranslationTerm).where(
        TranslationTerm.id == term_id,
        TranslationTerm.company_id == current_user.company_id,
        TranslationTerm.deleted_at.is_(None),
    )
    res = await db.execute(stmt)
    term = res.scalar_one_or_none()
    if not term:
        raise NotFoundException(f"Translation term '{term_id}' not found")
    return term


@router.patch(
    "/terms/{term_id}",
    response_model=TranslationTermRead,
    tags=["Internationalization (i18n)"],
    summary="Update translation term",
)
async def update_translation_term(
    term_id: uuid.UUID,
    term_in: TranslationTermUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TranslationTerm:
    """Update translations or metadata for a custom term."""
    stmt = select(TranslationTerm).where(
        TranslationTerm.id == term_id,
        TranslationTerm.company_id == current_user.company_id,
        TranslationTerm.deleted_at.is_(None),
    )
    res = await db.execute(stmt)
    term = res.scalar_one_or_none()
    if not term:
        raise NotFoundException(f"Translation term '{term_id}' not found")

    for field, value in term_in.model_dump(exclude_unset=True).items():
        setattr(term, field, value)

    term.updated_by_id = current_user.id
    await db.commit()
    await db.refresh(term)
    return term


@router.delete(
    "/terms/{term_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Internationalization (i18n)"],
    summary="Delete translation term",
)
async def delete_translation_term(
    term_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft delete a translation term."""
    stmt = select(TranslationTerm).where(
        TranslationTerm.id == term_id,
        TranslationTerm.company_id == current_user.company_id,
        TranslationTerm.deleted_at.is_(None),
    )
    res = await db.execute(stmt)
    term = res.scalar_one_or_none()
    if not term:
        raise NotFoundException(f"Translation term '{term_id}' not found")

    await term.soft_delete(current_user.id)
    await db.commit()
