"""FastAPI route endpoints for Payment Terms, Methods & Transactions."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.context import get_active_company_id
from core.exceptions import ValidationException
from modules.base.identity_rbac.models import User
from modules.base.identity_rbac.dependencies import get_current_user

from modules.base.payments.service import PaymentTermsService
from modules.base.payments.schemas import (
    PaymentMethodCreate,
    PaymentMethodUpdate,
    PaymentMethodResponse,
    PaymentTermsCreate,
    PaymentTermsUpdate,
    PaymentTermsResponse,
    PaymentTransactionCreate,
    PaymentTransactionUpdate,
    PaymentTransactionResponse,
    ComputePaymentScheduleRequest,
    ComputePaymentScheduleResponse,
)

router = APIRouter(prefix="", tags=["Payment Terms, Methods & Transactions"])


def _resolve_company_id(user: User) -> uuid.UUID:
    """Resolve active company tenant context."""
    cid = get_active_company_id() or user.company_id
    if not cid:
        raise ValidationException("Active company context (X-Company-ID) is required.")
    return cid


# ---------------------------------------------------------------------------
# Payment Methods Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/methods",
    response_model=PaymentMethodResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Payment Method",
    description="Registers a new payment instrument (e.g. Bank Transfer, Credit Card, Cash).",
)
async def create_payment_method(
    payload: PaymentMethodCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaymentMethodResponse:
    company_id = _resolve_company_id(user)
    method = await PaymentTermsService.create_payment_method(db, company_id, payload)
    return PaymentMethodResponse.model_validate(method)


@router.get(
    "/methods",
    response_model=List[PaymentMethodResponse],
    summary="List Payment Methods",
    description="Lists all payment instruments registered for active tenant company.",
)
async def list_payment_methods(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[PaymentMethodResponse]:
    company_id = _resolve_company_id(user)
    methods = await PaymentTermsService.list_payment_methods(db, company_id, is_active=is_active)
    return [PaymentMethodResponse.model_validate(m) for m in methods]


@router.get(
    "/methods/{method_id}",
    response_model=PaymentMethodResponse,
    summary="Get Payment Method",
    description="Fetch single payment method details by UUID.",
)
async def get_payment_method(
    method_id: uuid.UUID = Path(..., description="Payment Method UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaymentMethodResponse:
    method = await PaymentTermsService.get_payment_method(db, method_id)
    return PaymentMethodResponse.model_validate(method)


@router.patch(
    "/methods/{method_id}",
    response_model=PaymentMethodResponse,
    summary="Update Payment Method",
    description="Update payment method parameters or active state.",
)
async def update_payment_method(
    payload: PaymentMethodUpdate,
    method_id: uuid.UUID = Path(..., description="Payment Method UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaymentMethodResponse:
    method = await PaymentTermsService.update_payment_method(db, method_id, payload)
    return PaymentMethodResponse.model_validate(method)


@router.delete(
    "/methods/{method_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Payment Method",
    description="Soft-deletes a payment method instrument.",
)
async def delete_payment_method(
    method_id: uuid.UUID = Path(..., description="Payment Method UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await PaymentTermsService.delete_payment_method(db, method_id)


# ---------------------------------------------------------------------------
# Payment Terms Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/terms",
    response_model=PaymentTermsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Payment Terms",
    description="Registers a new payment term schedule and its installment lines.",
)
async def create_payment_terms(
    payload: PaymentTermsCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaymentTermsResponse:
    company_id = _resolve_company_id(user)
    terms = await PaymentTermsService.create_payment_terms(db, company_id, payload)
    return PaymentTermsResponse.model_validate(terms)


@router.get(
    "/terms",
    response_model=List[PaymentTermsResponse],
    summary="List Payment Terms",
    description="Lists all payment term schedules for active tenant company.",
)
async def list_payment_terms(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[PaymentTermsResponse]:
    company_id = _resolve_company_id(user)
    terms_list = await PaymentTermsService.list_payment_terms(db, company_id, is_active=is_active)
    return [PaymentTermsResponse.model_validate(t) for t in terms_list]


@router.get(
    "/terms/{terms_id}",
    response_model=PaymentTermsResponse,
    summary="Get Payment Terms",
    description="Fetch single payment term schedule with all installment rules.",
)
async def get_payment_terms(
    terms_id: uuid.UUID = Path(..., description="Payment Terms UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaymentTermsResponse:
    terms = await PaymentTermsService.get_payment_terms(db, terms_id)
    return PaymentTermsResponse.model_validate(terms)


@router.patch(
    "/terms/{terms_id}",
    response_model=PaymentTermsResponse,
    summary="Update Payment Terms",
    description="Update payment terms header or active status.",
)
async def update_payment_terms(
    payload: PaymentTermsUpdate,
    terms_id: uuid.UUID = Path(..., description="Payment Terms UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaymentTermsResponse:
    terms = await PaymentTermsService.update_payment_terms(db, terms_id, payload)
    return PaymentTermsResponse.model_validate(terms)


@router.delete(
    "/terms/{terms_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Payment Terms",
    description="Soft-deletes a payment term schedule.",
)
async def delete_payment_terms(
    terms_id: uuid.UUID = Path(..., description="Payment Terms UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await PaymentTermsService.delete_payment_terms(db, terms_id)


@router.post(
    "/terms/compute-schedule",
    response_model=ComputePaymentScheduleResponse,
    summary="Compute Due Dates & Installments",
    description="Calculates due dates and installment breakdowns for a given invoice amount and payment terms.",
)
async def compute_due_dates(
    payload: ComputePaymentScheduleRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ComputePaymentScheduleResponse:
    company_id = _resolve_company_id(user)
    return await PaymentTermsService.compute_due_dates(db, company_id, payload)


# ---------------------------------------------------------------------------
# Payment Transactions Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/transactions",
    response_model=PaymentTransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Payment Transaction",
    description="Registers an inbound or outbound payment transaction in draft state.",
)
async def create_transaction(
    payload: PaymentTransactionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaymentTransactionResponse:
    company_id = _resolve_company_id(user)
    tx = await PaymentTermsService.create_transaction(db, company_id, payload)
    return PaymentTransactionResponse.model_validate(tx)


@router.get(
    "/transactions",
    response_model=List[PaymentTransactionResponse],
    summary="List Payment Transactions",
    description="Lists payment transactions for active tenant company with optional filters.",
)
async def list_transactions(
    status: Optional[str] = Query(None, description="Filter by status (draft, cleared, reconciled, cancelled)"),
    party_id: Optional[uuid.UUID] = Query(None, description="Filter by customer or vendor party UUID"),
    res_model: Optional[str] = Query(None, description="Filter by target model"),
    res_id: Optional[uuid.UUID] = Query(None, description="Filter by target record UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[PaymentTransactionResponse]:
    company_id = _resolve_company_id(user)
    txs = await PaymentTermsService.list_transactions(
        db, company_id, status=status, party_id=party_id, res_model=res_model, res_id=res_id
    )
    return [PaymentTransactionResponse.model_validate(tx) for tx in txs]


@router.get(
    "/transactions/{transaction_id}",
    response_model=PaymentTransactionResponse,
    summary="Get Payment Transaction",
    description="Fetch single payment transaction details by UUID.",
)
async def get_transaction(
    transaction_id: uuid.UUID = Path(..., description="Transaction UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaymentTransactionResponse:
    tx = await PaymentTermsService.get_transaction(db, transaction_id)
    return PaymentTransactionResponse.model_validate(tx)


@router.patch(
    "/transactions/{transaction_id}",
    response_model=PaymentTransactionResponse,
    summary="Update Payment Transaction",
    description="Update reference or internal notes for an un-reconciled transaction.",
)
async def update_transaction(
    payload: PaymentTransactionUpdate,
    transaction_id: uuid.UUID = Path(..., description="Transaction UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaymentTransactionResponse:
    tx = await PaymentTermsService.update_transaction(db, transaction_id, payload)
    return PaymentTransactionResponse.model_validate(tx)


@router.post(
    "/transactions/{transaction_id}/clear",
    response_model=PaymentTransactionResponse,
    summary="Clear Payment Transaction",
    description="Transitions a draft payment transaction to cleared (bank confirmed).",
)
async def clear_transaction(
    transaction_id: uuid.UUID = Path(..., description="Transaction UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaymentTransactionResponse:
    tx = await PaymentTermsService.clear_transaction(db, transaction_id)
    return PaymentTransactionResponse.model_validate(tx)


@router.post(
    "/transactions/{transaction_id}/reconcile",
    response_model=PaymentTransactionResponse,
    summary="Reconcile Payment Transaction",
    description="Transitions a cleared payment transaction to reconciled.",
)
async def reconcile_transaction(
    transaction_id: uuid.UUID = Path(..., description="Transaction UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaymentTransactionResponse:
    tx = await PaymentTermsService.reconcile_transaction(db, transaction_id)
    return PaymentTransactionResponse.model_validate(tx)


@router.post(
    "/transactions/{transaction_id}/cancel",
    response_model=PaymentTransactionResponse,
    summary="Cancel Payment Transaction",
    description="Cancels an un-reconciled payment transaction.",
)
async def cancel_transaction(
    transaction_id: uuid.UUID = Path(..., description="Transaction UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaymentTransactionResponse:
    tx = await PaymentTermsService.cancel_transaction(db, transaction_id)
    return PaymentTransactionResponse.model_validate(tx)
