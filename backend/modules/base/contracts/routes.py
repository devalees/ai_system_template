"""FastAPI route endpoints for Contracts, Agreements & Subscriptions."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.context import get_active_company_id
from core.exceptions import ValidationException
from modules.base.identity_rbac.models import User
from modules.base.identity_rbac.dependencies import get_current_user

from modules.base.contracts.service import ContractService
from modules.base.contracts.schemas import (
    ContractCreate,
    ContractUpdate,
    ContractResponse,
    ContractRenewRequest,
    ContractTerminateRequest,
)

router = APIRouter(prefix="", tags=["Contracts, Agreements & Subscriptions"])


def _resolve_company_id(user: User) -> uuid.UUID:
    """Resolve active company tenant context."""
    cid = get_active_company_id() or user.company_id
    if not cid:
        raise ValidationException("Active company context (X-Company-ID) is required.")
    return cid


# ---------------------------------------------------------------------------
# Contract Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=ContractResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Contract",
    description="Registers a new commercial contract, subscription, or agreement.",
)
async def create_contract(
    payload: ContractCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ContractResponse:
    company_id = _resolve_company_id(user)
    contract = await ContractService.create_contract(db, company_id, payload)
    return ContractResponse.model_validate(contract)


@router.get(
    "",
    response_model=List[ContractResponse],
    summary="List Contracts",
    description="Lists contracts for active tenant company with optional filters.",
)
async def list_contracts(
    party_id: Optional[uuid.UUID] = Query(None, description="Filter by customer or vendor party UUID"),
    contract_type: Optional[str] = Query(None, description="Filter by type (customer, vendor, employment, lease, subscription)"),
    state: Optional[str] = Query(None, description="Filter by state (draft, active, expired, terminated, cancelled)"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[ContractResponse]:
    company_id = _resolve_company_id(user)
    contracts = await ContractService.list_contracts(
        db, company_id, party_id=party_id, contract_type=contract_type, state=state
    )
    return [ContractResponse.model_validate(c) for c in contracts]


@router.get(
    "/expiring",
    response_model=List[ContractResponse],
    summary="Get Expiring Contracts",
    description="Lists active contracts nearing their expiration date within a specified horizon (default 30 days).",
)
async def get_expiring_contracts(
    horizon_days: int = Query(30, ge=1, le=365, description="Day lookahead horizon"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[ContractResponse]:
    company_id = _resolve_company_id(user)
    contracts = await ContractService.get_expiring_contracts(db, company_id, horizon_days=horizon_days)
    return [ContractResponse.model_validate(c) for c in contracts]


@router.get(
    "/{contract_id}",
    response_model=ContractResponse,
    summary="Get Contract",
    description="Fetch single contract details by UUID.",
)
async def get_contract(
    contract_id: uuid.UUID = Path(..., description="Contract UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ContractResponse:
    contract = await ContractService.get_contract(db, contract_id)
    return ContractResponse.model_validate(contract)


@router.patch(
    "/{contract_id}",
    response_model=ContractResponse,
    summary="Update Contract",
    description="Update contract terms or financial commitment.",
)
async def update_contract(
    payload: ContractUpdate,
    contract_id: uuid.UUID = Path(..., description="Contract UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ContractResponse:
    contract = await ContractService.update_contract(db, contract_id, payload)
    return ContractResponse.model_validate(contract)


@router.delete(
    "/{contract_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Contract",
    description="Soft-deletes a contract.",
)
async def delete_contract(
    contract_id: uuid.UUID = Path(..., description="Contract UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await ContractService.delete_contract(db, contract_id)


# ---------------------------------------------------------------------------
# Contract State Transitions & Renewal
# ---------------------------------------------------------------------------

@router.post(
    "/{contract_id}/activate",
    response_model=ContractResponse,
    summary="Activate Contract",
    description="Transitions a draft contract to active status.",
)
async def activate_contract(
    contract_id: uuid.UUID = Path(..., description="Contract UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ContractResponse:
    contract = await ContractService.activate_contract(db, contract_id)
    return ContractResponse.model_validate(contract)


@router.post(
    "/{contract_id}/renew",
    response_model=ContractResponse,
    summary="Renew Contract",
    description="Extends the contract expiration date and sets state to active.",
)
async def renew_contract(
    payload: ContractRenewRequest,
    contract_id: uuid.UUID = Path(..., description="Contract UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ContractResponse:
    contract = await ContractService.renew_contract(db, contract_id, payload)
    return ContractResponse.model_validate(contract)


@router.post(
    "/{contract_id}/terminate",
    response_model=ContractResponse,
    summary="Terminate Contract",
    description="Terminates an active contract prematurely with an optional audit reason.",
)
async def terminate_contract(
    payload: ContractTerminateRequest,
    contract_id: uuid.UUID = Path(..., description="Contract UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ContractResponse:
    contract = await ContractService.terminate_contract(db, contract_id, payload)
    return ContractResponse.model_validate(contract)


@router.post(
    "/{contract_id}/cancel",
    response_model=ContractResponse,
    summary="Cancel Contract",
    description="Cancels a contract.",
)
async def cancel_contract(
    contract_id: uuid.UUID = Path(..., description="Contract UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ContractResponse:
    contract = await ContractService.cancel_contract(db, contract_id)
    return ContractResponse.model_validate(contract)
