"""Enterprise Sales Order Management REST API Router."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.database import get_db
from core.context import get_active_company_id
from core.exceptions import NotFoundException
from modules.base.identity_rbac.dependencies import get_current_user
from modules.base.identity_rbac.models import User
from modules.apps.sales.models import SaleOrder
from modules.apps.sales.schemas import SaleOrderCreate, SaleOrderRead
from modules.apps.sales.service import SaleService
from modules.apps.accounting.schemas import AccountMoveRead

router = APIRouter(tags=["Sales & Customer Order Management"])


@router.get("/orders", response_model=List[SaleOrderRead])
async def list_orders(
    state: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """List all Sales Quotations and Orders for the active company."""
    stmt = (
        select(SaleOrder)
        .options(selectinload(SaleOrder.lines))
        .where(SaleOrder.company_id == company_id, SaleOrder.deleted_at.is_(None))
        .order_by(SaleOrder.created_at.desc())
    )
    if state:
        stmt = stmt.where(SaleOrder.state == state)

    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/orders", response_model=SaleOrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: SaleOrderCreate,
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """Create a new Sales Quotation."""
    return await SaleService.create_order(db, payload, company_id)


@router.get("/orders/{order_id}", response_model=SaleOrderRead)
async def get_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """Retrieve a single Sales Order by ID."""
    stmt = (
        select(SaleOrder)
        .options(selectinload(SaleOrder.lines))
        .where(
            SaleOrder.id == order_id,
            SaleOrder.company_id == company_id,
            SaleOrder.deleted_at.is_(None),
        )
    )
    res = await db.execute(stmt)
    order = res.scalar_one_or_none()
    if not order:
        raise NotFoundException("SaleOrder", order_id)
    return order


@router.post("/orders/{order_id}/confirm", response_model=SaleOrderRead)
async def confirm_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """Confirm a Quotation into a Sales Order, stamping legal sequence."""
    return await SaleService.confirm_order(db, order_id, company_id)


@router.post("/orders/{order_id}/create-invoice", response_model=AccountMoveRead)
async def create_invoice_from_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """1-Click generation of draft Customer Invoice in Accounting from confirmed Sales Order."""
    return await SaleService.create_invoice(db, order_id, company_id)
