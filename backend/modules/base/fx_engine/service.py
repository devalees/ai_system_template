"""Domain service for foreign exchange rates, precision rounding, and cross-currency triangulation."""

import uuid
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.exceptions import PlatformException
from modules.base.lookups.models import Currency
from modules.base.fx_engine.models import ExchangeRate
from modules.base.fx_engine.schemas import (
    ExchangeRateCreate,
    ExchangeRateUpdate,
    ExchangeRateRead,
    CurrencyConvertRequest,
    CurrencyConvertResponse,
)


class ExchangeRateNotFoundException(PlatformException):
    """Raised when no exchange rate or triangulation path exists between two currencies."""
    def __init__(self, from_code: str, to_code: str, val_date: date):
        super().__init__(
            code="EXCHANGE_RATE_NOT_FOUND",
            message=f"No exchange rate found to convert '{from_code}' to '{to_code}' on or before {val_date}.",
            resolution_hint="Define an exchange rate for this pair in the FX Engine or ensure a common base currency rate exists.",
            details={"from_currency": from_code, "to_currency": to_code, "date": str(val_date)},
            status_code=404,
        )


class FXService:
    """Core domain service for FX rate registration, historical retrieval, and currency conversions."""

    @classmethod
    def _to_read_dto(cls, rate: ExchangeRate) -> ExchangeRateRead:
        """Helper to convert ORM model to ExchangeRateRead DTO."""
        return ExchangeRateRead(
            id=rate.id,
            company_id=rate.company_id,
            from_currency_id=rate.from_currency_id,
            to_currency_id=rate.to_currency_id,
            rate=rate.rate,
            inverse_rate=rate.inverse_rate,
            effective_date=rate.effective_date,
            source=rate.source,
            from_currency_code=rate.from_currency.code if rate.from_currency else None,
            to_currency_code=rate.to_currency.code if rate.to_currency else None,
            version_id=rate.version_id,
            created_at=rate.created_at,
            updated_at=rate.updated_at,
        )

    @classmethod
    async def create_exchange_rate(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        payload: ExchangeRateCreate,
    ) -> ExchangeRateRead:
        """Create a new daily exchange rate and calculate its inverse rate."""
        if payload.from_currency_id == payload.to_currency_id:
            raise PlatformException(
                code="IDENTICAL_CURRENCIES",
                message="from_currency_id and to_currency_id must be distinct.",
                resolution_hint="Select two different currencies to establish an exchange rate.",
                status_code=400,
            )

        # Check duplicate
        existing = (
            await db.execute(
                select(ExchangeRate).where(
                    ExchangeRate.company_id == company_id,
                    ExchangeRate.from_currency_id == payload.from_currency_id,
                    ExchangeRate.to_currency_id == payload.to_currency_id,
                    ExchangeRate.effective_date == payload.effective_date,
                )
            )
        ).scalar_one_or_none()

        if existing:
            raise PlatformException(
                code="EXCHANGE_RATE_ALREADY_EXISTS",
                message=f"An exchange rate for this currency pair already exists on {payload.effective_date}.",
                resolution_hint="Update the existing exchange rate instead of creating a duplicate.",
                status_code=409,
            )

        inverse_calc = Decimal("1.0") / payload.rate
        inverse_rate = inverse_calc.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

        rate_obj = ExchangeRate(
            company_id=company_id,
            from_currency_id=payload.from_currency_id,
            to_currency_id=payload.to_currency_id,
            rate=payload.rate,
            inverse_rate=inverse_rate,
            effective_date=payload.effective_date,
            source=payload.source,
        )
        db.add(rate_obj)
        await db.commit()
        await db.refresh(rate_obj, ["from_currency", "to_currency"])
        return cls._to_read_dto(rate_obj)

    @classmethod
    async def get_rate(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        from_currency_id: uuid.UUID,
        to_currency_id: uuid.UUID,
        val_date: date,
    ) -> Tuple[Decimal, date, bool]:
        """Resolve conversion multiplier (direct, inverse, or triangulated).
        
        Returns:
            Tuple of (effective_rate, effective_date, is_triangulated)
        """
        if from_currency_id == to_currency_id:
            return Decimal("1.0"), val_date, False

        # 1. Direct rate on or before val_date
        stmt_direct = (
            select(ExchangeRate)
            .where(
                ExchangeRate.company_id == company_id,
                ExchangeRate.from_currency_id == from_currency_id,
                ExchangeRate.to_currency_id == to_currency_id,
                ExchangeRate.effective_date <= val_date,
            )
            .order_by(ExchangeRate.effective_date.desc())
        )
        direct_match = (await db.execute(stmt_direct)).scalars().first()
        if direct_match:
            return direct_match.rate, direct_match.effective_date, False

        # 2. Inverse rate on or before val_date
        stmt_inverse = (
            select(ExchangeRate)
            .where(
                ExchangeRate.company_id == company_id,
                ExchangeRate.from_currency_id == to_currency_id,
                ExchangeRate.to_currency_id == from_currency_id,
                ExchangeRate.effective_date <= val_date,
            )
            .order_by(ExchangeRate.effective_date.desc())
        )
        inverse_match = (await db.execute(stmt_inverse)).scalars().first()
        if inverse_match:
            inv_calc = (Decimal("1.0") / inverse_match.rate).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
            return inv_calc, inverse_match.effective_date, False

        # 3. Triangulation via base currency
        stmt_base = (
            select(Currency)
            .where(Currency.company_id == company_id, Currency.is_base.is_(True))
        )
        base_currency = (await db.execute(stmt_base)).scalars().first()
        if base_currency and base_currency.id not in (from_currency_id, to_currency_id):
            try:
                rate_leg1, date1, _ = await cls.get_rate(db, company_id, from_currency_id, base_currency.id, val_date)
                rate_leg2, date2, _ = await cls.get_rate(db, company_id, base_currency.id, to_currency_id, val_date)
                triangulated = (rate_leg1 * rate_leg2).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
                eff_date = min(date1, date2)
                return triangulated, eff_date, True
            except PlatformException:
                pass

        # If not found, retrieve names for exception
        from_curr = (await db.execute(select(Currency).where(Currency.id == from_currency_id))).scalar_one_or_none()
        to_curr = (await db.execute(select(Currency).where(Currency.id == to_currency_id))).scalar_one_or_none()
        from_code = from_curr.code if from_curr else str(from_currency_id)
        to_code = to_curr.code if to_curr else str(to_currency_id)
        raise ExchangeRateNotFoundException(from_code, to_code, val_date)

    @classmethod
    async def convert(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        payload: CurrencyConvertRequest,
    ) -> CurrencyConvertResponse:
        """Convert a monetary sum from source currency to destination currency."""
        val_date = payload.effective_date or date.today()

        from_curr = (
            await db.execute(
                select(Currency).where(Currency.company_id == company_id, Currency.id == payload.from_currency_id)
            )
        ).scalar_one_or_none()

        to_curr = (
            await db.execute(
                select(Currency).where(Currency.company_id == company_id, Currency.id == payload.to_currency_id)
            )
        ).scalar_one_or_none()

        if not from_curr:
            raise PlatformException(
                code="CURRENCY_NOT_FOUND",
                message=f"Source currency '{payload.from_currency_id}' not found.",
                status_code=404,
            )
        if not to_curr:
            raise PlatformException(
                code="CURRENCY_NOT_FOUND",
                message=f"Target currency '{payload.to_currency_id}' not found.",
                status_code=404,
            )

        rate, eff_date, triangulated = await cls.get_rate(
            db, company_id, payload.from_currency_id, payload.to_currency_id, val_date
        )

        raw_converted = payload.amount * rate
        precision = payload.round_precision if payload.round_precision is not None else to_curr.decimal_places
        quantize_pattern = Decimal("1") if precision == 0 else Decimal("0." + "0" * precision)
        converted_amount = raw_converted.quantize(quantize_pattern, rounding=ROUND_HALF_UP)

        return CurrencyConvertResponse(
            amount=payload.amount,
            converted_amount=converted_amount,
            from_currency_code=from_curr.code,
            to_currency_code=to_curr.code,
            rate_used=rate,
            effective_date=eff_date,
            triangulation_used=triangulated,
        )

    @classmethod
    async def list_rates(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        from_currency_id: Optional[uuid.UUID] = None,
        to_currency_id: Optional[uuid.UUID] = None,
    ) -> List[ExchangeRateRead]:
        """List exchange rates with pair filtering."""
        stmt = (
            select(ExchangeRate)
            .where(ExchangeRate.company_id == company_id)
            .options(selectinload(ExchangeRate.from_currency), selectinload(ExchangeRate.to_currency))
        )
        if from_currency_id:
            stmt = stmt.where(ExchangeRate.from_currency_id == from_currency_id)
        if to_currency_id:
            stmt = stmt.where(ExchangeRate.to_currency_id == to_currency_id)

        stmt = stmt.order_by(ExchangeRate.effective_date.desc())
        result = await db.execute(stmt)
        return [cls._to_read_dto(r) for r in result.scalars().all()]

    @classmethod
    async def get_exchange_rate(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        rate_id: uuid.UUID,
    ) -> ExchangeRateRead:
        """Fetch a specific exchange rate record by ID."""
        stmt = (
            select(ExchangeRate)
            .where(ExchangeRate.company_id == company_id, ExchangeRate.id == rate_id)
            .options(selectinload(ExchangeRate.from_currency), selectinload(ExchangeRate.to_currency))
        )
        rate = (await db.execute(stmt)).scalar_one_or_none()
        if not rate:
            raise PlatformException(
                code="EXCHANGE_RATE_NOT_FOUND",
                message=f"Exchange rate '{rate_id}' not found.",
                status_code=404,
            )
        return cls._to_read_dto(rate)

    @classmethod
    async def update_exchange_rate(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        rate_id: uuid.UUID,
        payload: ExchangeRateUpdate,
    ) -> ExchangeRateRead:
        """Update exchange rate value and recompute inverse."""
        stmt = (
            select(ExchangeRate)
            .where(ExchangeRate.company_id == company_id, ExchangeRate.id == rate_id)
            .options(selectinload(ExchangeRate.from_currency), selectinload(ExchangeRate.to_currency))
        )
        rate = (await db.execute(stmt)).scalar_one_or_none()
        if not rate:
            raise PlatformException(
                code="EXCHANGE_RATE_NOT_FOUND",
                message=f"Exchange rate '{rate_id}' not found.",
                status_code=404,
            )

        if payload.rate is not None:
            rate.rate = payload.rate
            inverse_calc = Decimal("1.0") / payload.rate
            rate.inverse_rate = inverse_calc.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        if payload.source is not None:
            rate.source = payload.source

        await db.commit()
        await db.refresh(rate, ["from_currency", "to_currency"])
        return cls._to_read_dto(rate)

    @classmethod
    async def delete_exchange_rate(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        rate_id: uuid.UUID,
    ) -> None:
        """Soft-delete an exchange rate entry."""
        stmt = select(ExchangeRate).where(ExchangeRate.company_id == company_id, ExchangeRate.id == rate_id)
        rate = (await db.execute(stmt)).scalar_one_or_none()
        if not rate:
            raise PlatformException(
                code="EXCHANGE_RATE_NOT_FOUND",
                message=f"Exchange rate '{rate_id}' not found.",
                status_code=404,
            )
        rate.soft_delete()
        await db.commit()
