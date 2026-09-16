"""FastAPI route endpoints for Pricing Engine & Multi-Tier Price Lists."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.context import get_active_company_id
from core.exceptions import ValidationException
from modules.base.identity_rbac.models import User
from modules.base.identity_rbac.dependencies import get_current_user

from modules.base.pricing.service import PricingService
from modules.base.pricing.schemas import (
    PriceListCreate,
    PriceListUpdate,
    PriceListResponse,
    PriceListItemCreate,
    PriceListItemUpdate,
    PriceListItemResponse,
    PriceEvaluateRequest,
    PriceEvaluateResponse,
)

router = APIRouter(prefix="", tags=["Pricing Engine & Multi-Tier Price Lists"])


def _resolve_company_id(user: User) -> uuid.UUID:
    """Resolve active company tenant context."""
    cid = get_active_company_id() or user.company_id
    if not cid:
        raise ValidationException("Active company context (X-Company-ID) is required.")
    return cid


# ---------------------------------------------------------------------------
# Price List Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/lists",
    response_model=PriceListResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Price List",
    description="Registers a new commercial price list catalog with optional currency association.",
)
async def create_price_list(
    payload: PriceListCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PriceListResponse:
    company_id = _resolve_company_id(user)
    pl = await PricingService.create_price_list(db, company_id, payload)
    return PriceListResponse.model_validate(pl)


@router.get(
    "/lists",
    response_model=List[PriceListResponse],
    summary="List Price Lists",
    description="Lists price list catalogs for the current company tenant.",
)
async def list_price_lists(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[PriceListResponse]:
    company_id = _resolve_company_id(user)
    lists = await PricingService.list_price_lists(db, company_id, is_active=is_active)
    return [PriceListResponse.model_validate(l) for l in lists]


@router.get(
    "/lists/{price_list_id}",
    response_model=PriceListResponse,
    summary="Get Price List",
    description="Retrieves a specific price list along with its defined pricing rules and tiers.",
)
async def get_price_list(
    price_list_id: uuid.UUID = Path(..., description="Price List ID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PriceListResponse:
    company_id = _resolve_company_id(user)
    pl = await PricingService.get_price_list(db, company_id, price_list_id)
    return PriceListResponse.model_validate(pl)


@router.put(
    "/lists/{price_list_id}",
    response_model=PriceListResponse,
    summary="Update Price List",
    description="Updates name, description, currency, or operational state of a price list.",
)
async def update_price_list(
    price_list_id: uuid.UUID = Path(..., description="Price List ID"),
    payload: PriceListUpdate = ...,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PriceListResponse:
    company_id = _resolve_company_id(user)
    pl = await PricingService.update_price_list(db, company_id, price_list_id, payload)
    return PriceListResponse.model_validate(pl)


@router.delete(
    "/lists/{price_list_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Price List",
    description="Deletes a price list catalog and all child rule items.",
)
async def delete_price_list(
    price_list_id: uuid.UUID = Path(..., description="Price List ID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    company_id = _resolve_company_id(user)
    await PricingService.delete_price_list(db, company_id, price_list_id)


# ---------------------------------------------------------------------------
# Price List Item Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/lists/{price_list_id}/items",
    response_model=PriceListItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Price List Item",
    description="Adds a new tiered volume break, fixed price, or discount rule to a price list.",
)
async def add_price_list_item(
    price_list_id: uuid.UUID = Path(..., description="Price List ID"),
    payload: PriceListItemCreate = ...,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PriceListItemResponse:
    company_id = _resolve_company_id(user)
    item = await PricingService.add_item(db, company_id, price_list_id, payload)
    return PriceListItemResponse.model_validate(item)


@router.get(
    "/items/{item_id}",
    response_model=PriceListItemResponse,
    summary="Get Price List Item",
    description="Retrieves a specific pricing rule item by ID.",
)
async def get_price_list_item(
    item_id: uuid.UUID = Path(..., description="Price List Item ID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PriceListItemResponse:
    company_id = _resolve_company_id(user)
    item = await PricingService.get_item(db, company_id, item_id)
    return PriceListItemResponse.model_validate(item)


@router.put(
    "/items/{item_id}",
    response_model=PriceListItemResponse,
    summary="Update Price List Item",
    description="Updates parameters, discounts, quantities, or dates of a pricing rule item.",
)
async def update_price_list_item(
    item_id: uuid.UUID = Path(..., description="Price List Item ID"),
    payload: PriceListItemUpdate = ...,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PriceListItemResponse:
    company_id = _resolve_company_id(user)
    item = await PricingService.update_item(db, company_id, item_id, payload)
    return PriceListItemResponse.model_validate(item)


@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Price List Item",
    description="Deletes a pricing rule item.",
)
async def delete_price_list_item(
    item_id: uuid.UUID = Path(..., description="Price List Item ID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    company_id = _resolve_company_id(user)
    await PricingService.delete_item(db, company_id, item_id)


# ---------------------------------------------------------------------------
# Price Evaluation Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/evaluate",
    response_model=PriceEvaluateResponse,
    summary="Evaluate Commercial Price",
    description="Computes the net unit price, applicable discount, and total amount for a product line.",
)
async def evaluate_price(
    payload: PriceEvaluateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PriceEvaluateResponse:
    company_id = _resolve_company_id(user)
    return await PricingService.evaluate_price(db, company_id, payload)
