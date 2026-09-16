"""REST API routes for Money, Multi-Currency & Historical FX Engine."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from modules.base.identity_rbac.dependencies import get_current_user
from modules.base.identity_rbac.models import User
from modules.base.fx_engine.service import FXService
from modules.base.fx_engine.schemas import (
    ExchangeRateCreate,
    ExchangeRateUpdate,
    ExchangeRateRead,
    CurrencyConvertRequest,
    CurrencyConvertResponse,
)

router = APIRouter(prefix="", tags=["Money, Multi-Currency & Historical FX Engine"])


@router.post(
    "/rates",
    response_model=ExchangeRateRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Exchange Rate",
    description="Register a new daily exchange rate between two currencies with automatic inverse rate calculation.",
)
async def create_exchange_rate(
    payload: ExchangeRateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExchangeRateRead:
    """Create a new daily exchange rate."""
    return await FXService.create_exchange_rate(db, current_user.company_id, payload)


@router.get(
    "/rates",
    response_model=List[ExchangeRateRead],
    summary="List Exchange Rates",
    description="Retrieve historical exchange rates with optional filtering by currency pair.",
)
async def list_exchange_rates(
    from_currency_id: Optional[uuid.UUID] = Query(None, description="Filter by source currency ID"),
    to_currency_id: Optional[uuid.UUID] = Query(None, description="Filter by target currency ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ExchangeRateRead]:
    """List exchange rates for the active company."""
    return await FXService.list_rates(
        db, current_user.company_id, from_currency_id=from_currency_id, to_currency_id=to_currency_id
    )


@router.get(
    "/rates/{rate_id}",
    response_model=ExchangeRateRead,
    summary="Get Exchange Rate by ID",
    description="Retrieve details for a single exchange rate entry.",
)
async def get_exchange_rate(
    rate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExchangeRateRead:
    """Fetch an exchange rate by UUID."""
    return await FXService.get_exchange_rate(db, current_user.company_id, rate_id)


@router.patch(
    "/rates/{rate_id}",
    response_model=ExchangeRateRead,
    summary="Update Exchange Rate",
    description="Update rate multiplier or provider source with automatic inverse rate recalculation.",
)
async def update_exchange_rate(
    rate_id: uuid.UUID,
    payload: ExchangeRateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExchangeRateRead:
    """Update exchange rate attributes."""
    return await FXService.update_exchange_rate(db, current_user.company_id, rate_id, payload)


@router.delete(
    "/rates/{rate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Exchange Rate",
    description="Soft-delete an exchange rate record.",
)
async def delete_exchange_rate(
    rate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Soft-delete exchange rate."""
    await FXService.delete_exchange_rate(db, current_user.company_id, rate_id)


@router.post(
    "/convert",
    response_model=CurrencyConvertResponse,
    summary="Convert Monetary Amount",
    description="Convert monetary values across currencies using direct, inverse, or triangulated exchange rates with ISO decimal rounding.",
)
async def convert_currency(
    payload: CurrencyConvertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CurrencyConvertResponse:
    """Perform dynamic currency conversion."""
    return await FXService.convert(db, current_user.company_id, payload)
