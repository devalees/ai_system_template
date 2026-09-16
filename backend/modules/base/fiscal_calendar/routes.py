"""REST API routes for Fiscal Calendar & Period Locking Engine."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from modules.base.identity_rbac.dependencies import get_current_user
from modules.base.identity_rbac.models import User
from modules.base.fiscal_calendar.service import FiscalCalendarService
from modules.base.fiscal_calendar.schemas import (
    FiscalYearCreate,
    FiscalYearRead,
    FiscalPeriodRead,
    FiscalPeriodUpdate,
    DateValidationRequest,
    DateValidationResponse,
)

router = APIRouter(prefix="", tags=["Fiscal Calendar & Period Locking Engine"])


@router.post(
    "/years",
    response_model=FiscalYearRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Fiscal Year",
    description="Create a new fiscal year and optionally auto-generate monthly or quarterly periods.",
)
async def create_fiscal_year(
    payload: FiscalYearCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FiscalYearRead:
    """Create a new fiscal year with optional child periods."""
    return await FiscalCalendarService.create_fiscal_year(db, current_user.company_id, payload)


@router.get(
    "/years",
    response_model=List[FiscalYearRead],
    summary="List Fiscal Years",
    description="List all fiscal years registered for the current company.",
)
async def list_fiscal_years(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[FiscalYearRead]:
    """Retrieve all fiscal years for the active tenant company."""
    return await FiscalCalendarService.list_fiscal_years(db, current_user.company_id)


@router.get(
    "/years/{year_id}",
    response_model=FiscalYearRead,
    summary="Get Fiscal Year by ID",
    description="Retrieve full details and child periods for a specific fiscal year.",
)
async def get_fiscal_year(
    year_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FiscalYearRead:
    """Fetch fiscal year details by UUID."""
    return await FiscalCalendarService.get_fiscal_year(db, current_user.company_id, year_id)


@router.post(
    "/years/{year_id}/close",
    response_model=FiscalYearRead,
    summary="Close Fiscal Year",
    description="Officially close a fiscal year and permanently lock all its child periods.",
)
async def close_fiscal_year(
    year_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FiscalYearRead:
    """Close the fiscal year and lock all child periods."""
    return await FiscalCalendarService.close_fiscal_year(db, current_user.company_id, year_id)


@router.get(
    "/periods",
    response_model=List[FiscalPeriodRead],
    summary="List Fiscal Periods",
    description="Query fiscal periods with optional filtering by parent year or state (open, closing, locked).",
)
async def list_fiscal_periods(
    year_id: Optional[uuid.UUID] = Query(None, description="Filter by parent fiscal year ID"),
    state: Optional[str] = Query(None, description="Filter by state ('open', 'closing', 'locked')"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[FiscalPeriodRead]:
    """Retrieve filtered fiscal periods."""
    return await FiscalCalendarService.list_fiscal_periods(db, current_user.company_id, year_id=year_id, state=state)


@router.get(
    "/periods/{period_id}",
    response_model=FiscalPeriodRead,
    summary="Get Fiscal Period by ID",
    description="Retrieve details for a single fiscal period.",
)
async def get_fiscal_period(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FiscalPeriodRead:
    """Fetch a single fiscal period by ID."""
    return await FiscalCalendarService.get_fiscal_period(db, current_user.company_id, period_id)


@router.post(
    "/periods/{period_id}/lock",
    response_model=FiscalPeriodRead,
    summary="Lock Fiscal Period",
    description="Lock a fiscal period to prevent further backdated journal entries or mutations.",
)
async def lock_period(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FiscalPeriodRead:
    """Lock an operational period."""
    return await FiscalCalendarService.lock_period(db, current_user.company_id, period_id)


@router.post(
    "/periods/{period_id}/reopen",
    response_model=FiscalPeriodRead,
    summary="Reopen Fiscal Period",
    description="Reopen a previously locked period (allowed only if parent fiscal year is still open).",
)
async def reopen_period(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FiscalPeriodRead:
    """Reopen a locked period."""
    return await FiscalCalendarService.reopen_period(db, current_user.company_id, period_id)


@router.post(
    "/validate-date",
    response_model=DateValidationResponse,
    summary="Validate Transaction Posting Date",
    description="Verify whether a target transaction date falls into an active, open fiscal period.",
)
async def validate_posting_date(
    payload: DateValidationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DateValidationResponse:
    """Check date openness without throwing exceptions."""
    return await FiscalCalendarService.validate_posting_date(db, current_user.company_id, payload.target_date)
