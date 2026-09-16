"""API Routes for the Universal Sequence & Legal Auto-Numbering Engine."""

import uuid
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from modules.base.identity_rbac.dependencies import get_current_user
from modules.base.identity_rbac.models import User
from modules.base.sequences.schemas import (
    SequenceCreate,
    SequenceUpdate,
    SequenceRead,
    NextNumberRequest,
    NextNumberResponse,
)
from modules.base.sequences.service import SequenceService
from modules.base.sequences.fixtures import seed_standard_sequences

router = APIRouter()


# ---------------- Seed Standard Sequences ----------------
@router.post(
    "/seed",
    response_model=Dict[str, int],
    summary="Seed Standard Document Sequences",
    description="Idempotently creates standard legal sequences (Invoices, Sales Orders, Purchase Orders, Contracts, Customer/Vendor codes) for the active tenant company.",
)
async def bootstrap_company_sequences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, int]:
    """Seed standard enterprise document numbering sequences."""
    seeded = await seed_standard_sequences(db, current_user.company_id)
    return {"seeded_sequences": seeded}


# ---------------- Sequence Definitions CRUD ----------------
@router.get(
    "/",
    response_model=List[SequenceRead],
    summary="List Sequence Series",
    description="List all active document numbering sequence definitions configured for the tenant company.",
)
async def list_sequences(
    search: Optional[str] = Query(None, description="Search by name or sequence code"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[SequenceRead]:
    """Retrieve all configured sequences for the active company."""
    sequences = await SequenceService.list_sequences(db, current_user.company_id, search)
    return [SequenceRead.model_validate(s) for s in sequences]


@router.post(
    "/",
    response_model=SequenceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Sequence Series",
    description="Define a new legal document numbering sequence with custom prefix, padding, step, and reset policy.",
)
async def create_sequence(
    payload: SequenceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SequenceRead:
    """Register a new sequence definition."""
    seq = await SequenceService.create_sequence(
        db=db,
        company_id=current_user.company_id,
        payload=payload,
        user_id=current_user.id,
    )
    return SequenceRead.model_validate(seq)


@router.get(
    "/{sequence_id}",
    response_model=SequenceRead,
    summary="Get Sequence Details",
    description="Retrieve details and current counter status of a specific sequence series by UUID.",
)
async def get_sequence(
    sequence_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SequenceRead:
    """Get single sequence definition."""
    seq = await SequenceService.get_sequence(db, current_user.company_id, sequence_id)
    return SequenceRead.model_validate(seq)


@router.patch(
    "/{sequence_id}",
    response_model=SequenceRead,
    summary="Update Sequence Series",
    description="Update title, prefix, padding, or reset rules for an existing sequence.",
)
async def update_sequence(
    sequence_id: uuid.UUID,
    payload: SequenceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SequenceRead:
    """Modify sequence parameters."""
    seq = await SequenceService.update_sequence(
        db=db,
        company_id=current_user.company_id,
        sequence_id=sequence_id,
        payload=payload,
        user_id=current_user.id,
    )
    return SequenceRead.model_validate(seq)


@router.delete(
    "/{sequence_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-Delete Sequence",
    description="Soft-deletes a sequence series. Past documents retaining this code are unaffected.",
)
async def delete_sequence(
    sequence_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a sequence definition."""
    await SequenceService.delete_sequence(
        db=db,
        company_id=current_user.company_id,
        sequence_id=sequence_id,
        user_id=current_user.id,
    )


# ---------------- Number Allocation & Preview ----------------
@router.post(
    "/{code}/next",
    response_model=NextNumberResponse,
    summary="Atomically Allocate Next Number",
    description="Atomically increments the sequence counter using PostgreSQL row locks and returns the formatted legal document number (e.g. 'INV/2026/09/00001').",
)
async def allocate_next_number(
    code: str,
    payload: Optional[NextNumberRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NextNumberResponse:
    """Allocate and increment the next consecutive document number."""
    context_date = payload.context_date if payload else None
    formatted, number = await SequenceService.get_next_number(
        db=db,
        company_id=current_user.company_id,
        code=code,
        context_date=context_date,
    )
    return NextNumberResponse(
        sequence_number=formatted,
        code=code,
        number=number,
        is_preview=False,
    )


@router.get(
    "/{code}/peek",
    response_model=NextNumberResponse,
    summary="Preview Next Number (Non-Mutating)",
    description="Preview the formatted next number without incrementing the database counter or acquiring a row lock.",
)
async def peek_next_number(
    code: str,
    context_date: Optional[str] = Query(None, description="ISO datetime string for date token evaluation"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NextNumberResponse:
    """Preview the next number in sequence without mutation."""
    from datetime import datetime
    c_date = datetime.fromisoformat(context_date) if context_date else None
    formatted, number = await SequenceService.peek_next_number(
        db=db,
        company_id=current_user.company_id,
        code=code,
        context_date=c_date,
    )
    return NextNumberResponse(
        sequence_number=formatted,
        code=code,
        number=number,
        is_preview=True,
    )
