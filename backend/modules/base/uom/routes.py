"""FastAPI route endpoints for Unit of Measure & Conversion Matrix."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.context import get_active_company_id
from core.exceptions import ValidationException
from modules.base.identity_rbac.models import User
from modules.base.identity_rbac.dependencies import get_current_user

from modules.base.uom.service import UOMService
from modules.base.uom.schemas import (
    UOMCategoryCreate,
    UOMCategoryUpdate,
    UOMCategoryResponse,
    UOMUnitCreate,
    UOMUnitUpdate,
    UOMUnitResponse,
    UOMConversionRuleCreate,
    UOMConversionRuleResponse,
    UOMConvertRequest,
    UOMConvertResponse,
)

router = APIRouter(prefix="", tags=["Unit of Measure & Conversion Matrix"])


def _resolve_company_id(user: User) -> uuid.UUID:
    """Resolve active company tenant context."""
    cid = get_active_company_id() or user.company_id
    if not cid:
        raise ValidationException("Active company context (X-Company-ID) is required.")
    return cid


# ---------------------------------------------------------------------------
# Category Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/categories",
    response_model=UOMCategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create UOM Category",
    description="Registers a new measurement category (e.g. Weight, Volume, Length, Count, Time).",
)
async def create_category(
    payload: UOMCategoryCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UOMCategoryResponse:
    company_id = _resolve_company_id(user)
    cat = await UOMService.create_category(db, company_id, payload)
    return UOMCategoryResponse.model_validate(cat)


@router.get(
    "/categories",
    response_model=List[UOMCategoryResponse],
    summary="List UOM Categories",
    description="Lists all measurement categories for the active company tenant.",
)
async def list_categories(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[UOMCategoryResponse]:
    company_id = _resolve_company_id(user)
    cats = await UOMService.list_categories(db, company_id)
    return [UOMCategoryResponse.model_validate(c) for c in cats]


@router.get(
    "/categories/{category_id}",
    response_model=UOMCategoryResponse,
    summary="Get UOM Category",
    description="Retrieves a specific UOM Category by ID.",
)
async def get_category(
    category_id: uuid.UUID = Path(..., description="Category ID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UOMCategoryResponse:
    company_id = _resolve_company_id(user)
    cat = await UOMService.get_category(db, company_id, category_id)
    return UOMCategoryResponse.model_validate(cat)


@router.put(
    "/categories/{category_id}",
    response_model=UOMCategoryResponse,
    summary="Update UOM Category",
    description="Updates name or description of a UOM Category.",
)
async def update_category(
    category_id: uuid.UUID = Path(..., description="Category ID"),
    payload: UOMCategoryUpdate = ...,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UOMCategoryResponse:
    company_id = _resolve_company_id(user)
    cat = await UOMService.update_category(db, company_id, category_id, payload)
    return UOMCategoryResponse.model_validate(cat)


@router.delete(
    "/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete UOM Category",
    description="Deletes a UOM Category and all associated units.",
)
async def delete_category(
    category_id: uuid.UUID = Path(..., description="Category ID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    company_id = _resolve_company_id(user)
    await UOMService.delete_category(db, company_id, category_id)


# ---------------------------------------------------------------------------
# Unit Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/units",
    response_model=UOMUnitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Unit of Measure",
    description="Registers a new unit of measure relative to its category reference unit.",
)
async def create_unit(
    payload: UOMUnitCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UOMUnitResponse:
    company_id = _resolve_company_id(user)
    unit = await UOMService.create_unit(db, company_id, payload)
    return UOMUnitResponse.model_validate(unit)


@router.get(
    "/units",
    response_model=List[UOMUnitResponse],
    summary="List Units of Measure",
    description="Lists units of measure for the company tenant, with optional category filter.",
)
async def list_units(
    category_id: Optional[uuid.UUID] = Query(None, description="Filter units by parent category"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[UOMUnitResponse]:
    company_id = _resolve_company_id(user)
    units = await UOMService.list_units(db, company_id, category_id=category_id)
    return [UOMUnitResponse.model_validate(u) for u in units]


@router.get(
    "/units/{unit_id}",
    response_model=UOMUnitResponse,
    summary="Get Unit of Measure",
    description="Retrieves a specific unit of measure by ID.",
)
async def get_unit(
    unit_id: uuid.UUID = Path(..., description="Unit ID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UOMUnitResponse:
    company_id = _resolve_company_id(user)
    unit = await UOMService.get_unit(db, company_id, unit_id=unit_id)
    return UOMUnitResponse.model_validate(unit)


@router.put(
    "/units/{unit_id}",
    response_model=UOMUnitResponse,
    summary="Update Unit of Measure",
    description="Updates name, ratio, precision, or operational state of a unit.",
)
async def update_unit(
    unit_id: uuid.UUID = Path(..., description="Unit ID"),
    payload: UOMUnitUpdate = ...,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UOMUnitResponse:
    company_id = _resolve_company_id(user)
    unit = await UOMService.update_unit(db, company_id, unit_id, payload)
    return UOMUnitResponse.model_validate(unit)


@router.delete(
    "/units/{unit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Unit of Measure",
    description="Deletes a unit of measure from the system.",
)
async def delete_unit(
    unit_id: uuid.UUID = Path(..., description="Unit ID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    company_id = _resolve_company_id(user)
    await UOMService.delete_unit(db, company_id, unit_id)


# ---------------------------------------------------------------------------
# Explicit Conversion Rules Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/conversion-rules",
    response_model=UOMConversionRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Conversion Rule",
    description="Registers an explicit or cross-category unit conversion rule (e.g. 1 Liter Olive Oil = 0.92 kg).",
)
async def create_conversion_rule(
    payload: UOMConversionRuleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UOMConversionRuleResponse:
    company_id = _resolve_company_id(user)
    rule = await UOMService.create_conversion_rule(db, company_id, payload)
    return UOMConversionRuleResponse.model_validate(rule)


@router.get(
    "/conversion-rules",
    response_model=List[UOMConversionRuleResponse],
    summary="List Conversion Rules",
    description="Lists explicit conversion rules with optional product or entity filtering.",
)
async def list_conversion_rules(
    res_model: Optional[str] = Query(None, description="Filter by attached record model"),
    res_id: Optional[uuid.UUID] = Query(None, description="Filter by attached record ID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[UOMConversionRuleResponse]:
    company_id = _resolve_company_id(user)
    rules = await UOMService.list_conversion_rules(db, company_id, res_model=res_model, res_id=res_id)
    return [UOMConversionRuleResponse.model_validate(r) for r in rules]


@router.delete(
    "/conversion-rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Conversion Rule",
    description="Removes an explicit conversion rule.",
)
async def delete_conversion_rule(
    rule_id: uuid.UUID = Path(..., description="Conversion rule ID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    company_id = _resolve_company_id(user)
    await UOMService.delete_conversion_rule(db, company_id, rule_id)


# ---------------------------------------------------------------------------
# Unit Conversion Execution Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/convert",
    response_model=UOMConvertResponse,
    summary="Convert Quantity Between UOMs",
    description="Converts a quantity between units using intra-category reference ratios or explicit cross-category rules.",
)
async def convert_quantity(
    payload: UOMConvertRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UOMConvertResponse:
    company_id = _resolve_company_id(user)
    return await UOMService.convert(
        db,
        company_id,
        quantity=payload.quantity,
        from_uom_id=payload.from_uom_id,
        from_uom_code=payload.from_uom_code,
        to_uom_id=payload.to_uom_id,
        to_uom_code=payload.to_uom_code,
        res_model=payload.res_model,
        res_id=payload.res_id,
    )
