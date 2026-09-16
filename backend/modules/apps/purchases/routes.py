"""Enterprise Purchases & Procurement REST API Router."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.database import get_db
from core.context import get_active_company_id, get_active_company_ids
from core.exceptions import NotFoundException
from modules.base.identity_rbac.dependencies import get_current_user
from modules.base.identity_rbac.models import User
from modules.apps.purchases.models import PurchaseOrder
from modules.apps.purchases.schemas import PurchaseOrderCreate, PurchaseOrderRead
from modules.apps.purchases.service import PurchaseService
from modules.apps.accounting.schemas import AccountMoveRead

router = APIRouter(tags=["Purchases & Vendor Procurement"])


@router.get("/orders", response_model=List[PurchaseOrderRead])
async def list_orders(
    state: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """List all Purchase Orders and RFQs for the active company context."""
    active_comps = get_active_company_ids() or [company_id]
    stmt = (
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.lines))
        .where(PurchaseOrder.company_id.in_(active_comps), PurchaseOrder.deleted_at.is_(None))
        .order_by(PurchaseOrder.created_at.desc())
    )
    if state:
        stmt = stmt.where(PurchaseOrder.state == state)

    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/orders", response_model=PurchaseOrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: PurchaseOrderCreate,
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """Create a new Request for Quotation (RFQ) or Purchase Order draft."""
    return await PurchaseService.create_order(db, payload, company_id)


@router.get("/orders/{order_id}", response_model=PurchaseOrderRead)
async def get_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """Retrieve a single Purchase Order by ID."""
    active_comps = get_active_company_ids() or [company_id]
    stmt = (
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.lines))
        .where(
            PurchaseOrder.id == order_id,
            PurchaseOrder.company_id.in_(active_comps),
            PurchaseOrder.deleted_at.is_(None),
        )
    )
    res = await db.execute(stmt)
    order = res.scalar_one_or_none()
    if not order:
        raise NotFoundException("PurchaseOrder", order_id)
    return order


@router.post("/orders/{order_id}/confirm", response_model=PurchaseOrderRead)
async def confirm_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """Confirm a Purchase Order, evaluating approval thresholds and stamping legal sequence."""
    return await PurchaseService.confirm_order(db, order_id, company_id)


@router.post("/orders/{order_id}/create-bill", response_model=AccountMoveRead)
async def create_bill_from_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    company_id: uuid.UUID = Depends(get_active_company_id),
    current_user: User = Depends(get_current_user),
):
    """1-Click generation of draft Vendor Bill in Accounting from confirmed Purchase Order."""
    return await PurchaseService.create_bill(db, order_id, company_id)
