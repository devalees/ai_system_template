"""FastAPI route endpoints for Tax Engine & Fiscal Positions."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.context import get_active_company_id
from core.exceptions import ValidationException
from modules.base.identity_rbac.models import User
from modules.base.identity_rbac.dependencies import get_current_user

from modules.base.taxes.service import TaxService
from modules.base.taxes.schemas import (
    TaxCreate,
    TaxUpdate,
    TaxResponse,
    FiscalPositionCreate,
    FiscalPositionUpdate,
    FiscalPositionResponse,
    FiscalPositionRuleCreate,
    FiscalPositionRuleResponse,
    TaxComputeRequest,
    TaxComputeResponse,
)

router = APIRouter(prefix="", tags=["Tax Engine & Fiscal Positions"])


def _resolve_company_id(user: User) -> uuid.UUID:
    """Resolve active company tenant context."""
    cid = get_active_company_id() or user.company_id
    if not cid:
        raise ValidationException("Active company context (X-Company-ID) is required.")
    return cid


# ---------------------------------------------------------------------------
# Tax Definition Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=TaxResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Tax Definition",
    description="Registers a new tax definition (percentage, fixed, inclusive, or compound).",
)
async def create_tax(
    payload: TaxCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaxResponse:
    company_id = _resolve_company_id(user)
    tax = await TaxService.create_tax(db, company_id, payload)
    return TaxResponse.model_validate(tax)


@router.get(
    "",
    response_model=List[TaxResponse],
    summary="List Tax Definitions",
    description="Retrieves all taxes defined for the active tenant company.",
)
async def list_taxes(
    scope: Optional[str] = Query(None, description="Filter by scope: sales, purchase, or none"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[TaxResponse]:
    company_id = _resolve_company_id(user)
    taxes = await TaxService.list_taxes(db, company_id, scope=scope, is_active=is_active)
    return [TaxResponse.model_validate(t) for t in taxes]


@router.get(
    "/{tax_id}",
    response_model=TaxResponse,
    summary="Get Tax Definition",
    description="Fetch single tax configuration by UUID.",
)
async def get_tax(
    tax_id: uuid.UUID = Path(..., description="Tax UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaxResponse:
    tax = await TaxService.get_tax(db, tax_id)
    return TaxResponse.model_validate(tax)


@router.patch(
    "/{tax_id}",
    response_model=TaxResponse,
    summary="Update Tax Definition",
    description="Update parameters or rate of an existing tax.",
)
async def update_tax(
    payload: TaxUpdate,
    tax_id: uuid.UUID = Path(..., description="Tax UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaxResponse:
    tax = await TaxService.update_tax(db, tax_id, payload)
    return TaxResponse.model_validate(tax)


@router.delete(
    "/{tax_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Tax Definition",
    description="Soft-deletes a tax definition.",
)
async def delete_tax(
    tax_id: uuid.UUID = Path(..., description="Tax UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await TaxService.delete_tax(db, tax_id)


# ---------------------------------------------------------------------------
# Fiscal Position Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/fiscal-positions",
    response_model=FiscalPositionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Fiscal Position",
    description="Creates a jurisdiction or export fiscal position mapping.",
)
async def create_fiscal_position(
    payload: FiscalPositionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FiscalPositionResponse:
    company_id = _resolve_company_id(user)
    fp = await TaxService.create_fiscal_position(db, company_id, payload)
    return FiscalPositionResponse.model_validate(fp)


@router.get(
    "/fiscal-positions",
    response_model=List[FiscalPositionResponse],
    summary="List Fiscal Positions",
    description="Lists all fiscal positions for current tenant company.",
)
async def list_fiscal_positions(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[FiscalPositionResponse]:
    company_id = _resolve_company_id(user)
    fps = await TaxService.list_fiscal_positions(db, company_id, is_active=is_active)
    return [FiscalPositionResponse.model_validate(fp) for fp in fps]


@router.get(
    "/fiscal-positions/{position_id}",
    response_model=FiscalPositionResponse,
    summary="Get Fiscal Position",
    description="Fetch single fiscal position with its mapping rules.",
)
async def get_fiscal_position(
    position_id: uuid.UUID = Path(..., description="Fiscal position UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FiscalPositionResponse:
    fp = await TaxService.get_fiscal_position(db, position_id)
    return FiscalPositionResponse.model_validate(fp)


@router.patch(
    "/fiscal-positions/{position_id}",
    response_model=FiscalPositionResponse,
    summary="Update Fiscal Position",
    description="Updates fiscal position settings or active status.",
)
async def update_fiscal_position(
    payload: FiscalPositionUpdate,
    position_id: uuid.UUID = Path(..., description="Fiscal position UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FiscalPositionResponse:
    fp = await TaxService.update_fiscal_position(db, position_id, payload)
    return FiscalPositionResponse.model_validate(fp)


@router.delete(
    "/fiscal-positions/{position_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Fiscal Position",
    description="Soft-deletes a fiscal position and cascades to its rules.",
)
async def delete_fiscal_position(
    position_id: uuid.UUID = Path(..., description="Fiscal position UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await TaxService.delete_fiscal_position(db, position_id)


@router.post(
    "/fiscal-positions/{position_id}/rules",
    response_model=FiscalPositionRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Fiscal Position Rule",
    description="Appends a tax mapping rule (source -> destination or exemption) to a fiscal position.",
)
async def add_fiscal_position_rule(
    payload: FiscalPositionRuleCreate,
    position_id: uuid.UUID = Path(..., description="Fiscal position UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FiscalPositionRuleResponse:
    rule = await TaxService.add_fiscal_position_rule(db, position_id, payload)
    return FiscalPositionRuleResponse.model_validate(rule)


@router.delete(
    "/fiscal-positions/rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Fiscal Position Rule",
    description="Deletes a specific tax mapping rule.",
)
async def delete_fiscal_position_rule(
    rule_id: uuid.UUID = Path(..., description="Rule UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await TaxService.delete_fiscal_position_rule(db, rule_id)


# ---------------------------------------------------------------------------
# Tax Computation Engine Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/compute",
    response_model=TaxComputeResponse,
    summary="Compute Taxes for Document Lines",
    description="Calculates multi-line taxes, inclusive/exclusive bases, compounding, and fiscal position substitutions.",
)
async def compute_taxes(
    payload: TaxComputeRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaxComputeResponse:
    company_id = _resolve_company_id(user)
    return await TaxService.compute_taxes(db, company_id, payload)
