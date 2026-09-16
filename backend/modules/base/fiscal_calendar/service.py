"""Business logic and verification service for Fiscal Calendar & Period Locking Engine."""

import uuid
import calendar
from datetime import date
from typing import Optional, List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.exceptions import PlatformException
from modules.base.fiscal_calendar.models import FiscalYear, FiscalPeriod
from modules.base.fiscal_calendar.schemas import (
    FiscalYearCreate,
    FiscalYearUpdate,
    FiscalPeriodCreate,
    FiscalPeriodUpdate,
    DateValidationResponse,
)


class FiscalYearNotFoundException(PlatformException):
    """Raised when an requested fiscal year is not found."""
    def __init__(self, year_id: uuid.UUID):
        super().__init__(
            code="FISCAL_YEAR_NOT_FOUND",
            message=f"Fiscal year '{year_id}' not found.",
            resolution_hint="Verify fiscal year ID or create a new fiscal year in settings.",
            details={"year_id": str(year_id)},
            status_code=404,
        )


class FiscalPeriodNotFoundException(PlatformException):
    """Raised when no fiscal period exists for an ID or date."""
    def __init__(self, identifier: Any):
        super().__init__(
            code="FISCAL_PERIOD_NOT_FOUND",
            message=f"No active fiscal period found for '{identifier}'.",
            resolution_hint="Create fiscal periods for this date range in Fiscal Calendar.",
            details={"identifier": str(identifier)},
            status_code=404,
        )


class FiscalPeriodClosedException(PlatformException):
    """Raised when a mutation is attempted on a locked or closed fiscal period/year."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="FISCAL_PERIOD_CLOSED",
            message=message,
            resolution_hint="Reopen the fiscal period or select an open transaction posting date.",
            details=details or {},
            status_code=400,
        )


class FiscalCalendarService:
    """Core domain service for governing financial calendar periods and enforcing posting locks."""

    @staticmethod
    def _generate_periods(
        start_date: date,
        end_date: date,
        period_type: str = "month",
    ) -> List[Dict[str, Any]]:
        """Generate monthly or quarterly period boundaries between start and end dates."""
        periods = []
        if period_type == "quarter":
            quarter_defs = [
                (1, 3, "Q1"),
                (4, 6, "Q2"),
                (7, 9, "Q3"),
                (10, 12, "Q4"),
            ]
            for start_m, end_m, q_code in quarter_defs:
                _, last_day = calendar.monthrange(start_date.year, end_m)
                q_start = max(start_date, date(start_date.year, start_m, 1))
                q_end = min(end_date, date(start_date.year, end_m, last_day))
                if q_start <= q_end:
                    periods.append({
                        "name": f"{q_code} {start_date.year}",
                        "code": f"{start_date.year}-{q_code}",
                        "date_from": q_start,
                        "date_to": q_end,
                        "period_type": "quarter",
                        "state": "open",
                    })
        else:
            # Default monthly periods
            curr = date(start_date.year, start_date.month, 1)
            while curr <= end_date:
                _, last_day = calendar.monthrange(curr.year, curr.month)
                p_start = max(start_date, curr)
                p_end = min(end_date, date(curr.year, curr.month, last_day))
                code = f"{curr.year}-{curr.month:02d}"
                month_name = calendar.month_name[curr.month]
                periods.append({
                    "name": f"{month_name} {curr.year}",
                    "code": code,
                    "date_from": p_start,
                    "date_to": p_end,
                    "period_type": "month",
                    "state": "open",
                })
                if curr.month == 12:
                    curr = date(curr.year + 1, 1, 1)
                else:
                    curr = date(curr.year, curr.month + 1, 1)
        return periods

    @classmethod
    async def create_fiscal_year(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        payload: FiscalYearCreate,
    ) -> FiscalYear:
        """Create a new fiscal year and optionally auto-generate its child periods."""
        if payload.date_from > payload.date_to:
            raise PlatformException(
                code="INVALID_DATE_RANGE",
                message="date_from cannot be later than date_to.",
                resolution_hint="Provide a valid date range where start is before or equal to end.",
                status_code=400,
            )

        # Check for duplicate code
        existing = (
            await db.execute(
                select(FiscalYear).where(
                    FiscalYear.company_id == company_id,
                    FiscalYear.code == payload.code,
                )
            )
        ).scalar_one_or_none()

        if existing:
            raise PlatformException(
                code="FISCAL_YEAR_ALREADY_EXISTS",
                message=f"Fiscal year with code '{payload.code}' already exists.",
                resolution_hint="Use a unique fiscal year code.",
                details={"code": payload.code},
                status_code=409,
            )

        year = FiscalYear(
            company_id=company_id,
            name=payload.name,
            code=payload.code,
            date_from=payload.date_from,
            date_to=payload.date_to,
            is_closed=False,
        )
        db.add(year)
        await db.flush()

        if payload.auto_generate_periods:
            period_data = cls._generate_periods(
                payload.date_from,
                payload.date_to,
                payload.period_type,
            )
            for p in period_data:
                period = FiscalPeriod(
                    company_id=company_id,
                    fiscal_year_id=year.id,
                    name=p["name"],
                    code=p["code"],
                    date_from=p["date_from"],
                    date_to=p["date_to"],
                    period_type=p["period_type"],
                    state=p["state"],
                )
                db.add(period)

        await db.commit()
        await db.refresh(year)
        return year

    @classmethod
    async def list_fiscal_years(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
    ) -> List[FiscalYear]:
        """List all fiscal years with their periods ordered chronologically."""
        stmt = (
            select(FiscalYear)
            .where(FiscalYear.company_id == company_id)
            .options(selectinload(FiscalYear.periods))
            .order_by(FiscalYear.date_from.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def get_fiscal_year(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        year_id: uuid.UUID,
    ) -> FiscalYear:
        """Fetch a specific fiscal year by ID."""
        stmt = (
            select(FiscalYear)
            .where(FiscalYear.company_id == company_id, FiscalYear.id == year_id)
            .options(selectinload(FiscalYear.periods))
        )
        year = (await db.execute(stmt)).scalar_one_or_none()
        if not year:
            raise FiscalYearNotFoundException(year_id)
        return year

    @classmethod
    async def close_fiscal_year(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        year_id: uuid.UUID,
    ) -> FiscalYear:
        """Close a fiscal year and automatically lock all associated periods."""
        year = await cls.get_fiscal_year(db, company_id, year_id)
        year.is_closed = True

        for period in year.periods:
            period.state = "locked"

        await db.commit()
        await db.refresh(year)
        return year

    @classmethod
    async def list_fiscal_periods(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        year_id: Optional[uuid.UUID] = None,
        state: Optional[str] = None,
    ) -> List[FiscalPeriod]:
        """Query periods with optional filtering by year and lock state."""
        stmt = select(FiscalPeriod).where(FiscalPeriod.company_id == company_id)
        if year_id:
            stmt = stmt.where(FiscalPeriod.fiscal_year_id == year_id)
        if state:
            stmt = stmt.where(FiscalPeriod.state == state)
        stmt = stmt.order_by(FiscalPeriod.date_from.asc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def get_fiscal_period(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        period_id: uuid.UUID,
    ) -> FiscalPeriod:
        """Fetch a specific period by ID."""
        stmt = (
            select(FiscalPeriod)
            .where(FiscalPeriod.company_id == company_id, FiscalPeriod.id == period_id)
            .options(selectinload(FiscalPeriod.fiscal_year))
        )
        period = (await db.execute(stmt)).scalar_one_or_none()
        if not period:
            raise FiscalPeriodNotFoundException(period_id)
        return period

    @classmethod
    async def lock_period(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        period_id: uuid.UUID,
    ) -> FiscalPeriod:
        """Lock an operational period preventing any further journal entries or mutations."""
        period = await cls.get_fiscal_period(db, company_id, period_id)
        period.state = "locked"
        await db.commit()
        await db.refresh(period)
        return period

    @classmethod
    async def reopen_period(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        period_id: uuid.UUID,
    ) -> FiscalPeriod:
        """Reopen a locked period if the parent fiscal year is still open."""
        period = await cls.get_fiscal_period(db, company_id, period_id)
        if period.fiscal_year and period.fiscal_year.is_closed:
            raise FiscalPeriodClosedException(
                message=f"Cannot reopen period '{period.code}' because parent fiscal year '{period.fiscal_year.code}' is closed.",
                details={"period_id": str(period_id), "year_id": str(period.fiscal_year_id)},
            )
        period.state = "open"
        await db.commit()
        await db.refresh(period)
        return period

    @classmethod
    async def get_period_for_date(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        target_date: date,
    ) -> FiscalPeriod:
        """Find the fiscal period that covers a given target date."""
        stmt = (
            select(FiscalPeriod)
            .where(
                FiscalPeriod.company_id == company_id,
                FiscalPeriod.date_from <= target_date,
                FiscalPeriod.date_to >= target_date,
            )
            .options(selectinload(FiscalPeriod.fiscal_year))
            .order_by(FiscalPeriod.date_from.desc())
        )
        period = (await db.execute(stmt)).scalars().first()
        if not period:
            raise FiscalPeriodNotFoundException(target_date)
        return period

    @classmethod
    async def assert_period_open(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        target_date: date,
    ) -> FiscalPeriod:
        """Assert that the target date falls into an open period within an open fiscal year.
        
        Raises:
            FiscalPeriodNotFoundException: If no period exists for target_date.
            FiscalPeriodClosedException: If period is locked/closing or fiscal year is closed.
        """
        period = await cls.get_period_for_date(db, company_id, target_date)
        
        if period.fiscal_year and period.fiscal_year.is_closed:
            raise FiscalPeriodClosedException(
                message=f"Transaction date {target_date} belongs to closed fiscal year '{period.fiscal_year.code}'.",
                details={
                    "target_date": str(target_date),
                    "fiscal_year_id": str(period.fiscal_year_id),
                    "fiscal_year_code": period.fiscal_year.code,
                },
            )

        if period.state != "open":
            raise FiscalPeriodClosedException(
                message=f"Transaction date {target_date} falls into period '{period.code}' which is '{period.state}'.",
                details={
                    "target_date": str(target_date),
                    "period_id": str(period.id),
                    "period_code": period.code,
                    "period_state": period.state,
                },
            )

        return period

    @classmethod
    async def validate_posting_date(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        target_date: date,
    ) -> DateValidationResponse:
        """Evaluate date openness without throwing exceptions, returning structured diagnostic response."""
        try:
            period = await cls.assert_period_open(db, company_id, target_date)
            return DateValidationResponse(
                is_open=True,
                target_date=target_date,
                period_id=period.id,
                period_code=period.code,
                period_state=period.state,
                year_code=period.fiscal_year.code if period.fiscal_year else None,
                message=f"Fiscal period '{period.code}' is open for transactions.",
            )
        except FiscalPeriodClosedException as exc:
            return DateValidationResponse(
                is_open=False,
                target_date=target_date,
                period_id=uuid.UUID(exc.details.get("period_id")) if "period_id" in exc.details else None,
                period_code=exc.details.get("period_code"),
                period_state=exc.details.get("period_state"),
                year_code=exc.details.get("fiscal_year_code"),
                message=exc.message,
            )
        except FiscalPeriodNotFoundException:
            return DateValidationResponse(
                is_open=False,
                target_date=target_date,
                message=f"No fiscal period found covering date {target_date}.",
            )
