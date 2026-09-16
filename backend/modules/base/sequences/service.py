"""Service layer for the Universal Sequence & Legal Auto-Numbering Engine."""

import uuid
import re
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.base.sequences.models import Sequence
from modules.base.sequences.schemas import SequenceCreate, SequenceUpdate
from core.exceptions import PlatformException


class SequenceNotFoundException(PlatformException):
    """Raised when an requested sequence code does not exist."""
    def __init__(self, code: str, company_id: uuid.UUID):
        super().__init__(
            code="SEQUENCE_NOT_FOUND",
            message=f"Sequence series with code '{code}' not found or inactive for this company.",
            resolution_hint="Create the sequence in settings or bootstrap standard sequence fixtures.",
            details={"code": code, "company_id": str(company_id)},
            status_code=404,
        )


class SequenceDuplicateException(PlatformException):
    """Raised when creating a sequence with a code that already exists."""
    def __init__(self, code: str):
        super().__init__(
            code="SEQUENCE_ALREADY_EXISTS",
            message=f"Sequence series with code '{code}' already exists for this company.",
            resolution_hint="Use a unique sequence code or update the existing sequence configuration.",
            details={"code": code},
            status_code=409,
        )


class SequenceService:
    """Core domain service for allocating and formatting consecutive document numbers."""

    @staticmethod
    def _interpolate_tokens(template: str, context_date: datetime) -> str:
        """Interpolate date tokens (e.g. %(year)s, %(month)s, %(day)s, %(year_short)s) in prefix/suffix."""
        if not template:
            return ""

        date_dict = {
            "year": context_date.strftime("%Y"),
            "year_short": context_date.strftime("%y"),
            "month": context_date.strftime("%m"),
            "day": context_date.strftime("%d"),
            "quarter": f"Q{(context_date.month - 1) // 3 + 1}",
        }

        try:
            return template % date_dict
        except (KeyError, ValueError):
            # Fallback for Python f-string or single bracket notation e.g. {year}
            result = template
            for k, v in date_dict.items():
                result = result.replace(f"%({k})s", v).replace(f"{{{k}}}", v)
            return result

    @classmethod
    def format_sequence(
        cls,
        prefix_template: str,
        suffix_template: str,
        number: int,
        padding: int,
        context_date: datetime,
    ) -> str:
        """Format the complete sequence string: prefix + zero-padded number + suffix."""
        prefix = cls._interpolate_tokens(prefix_template, context_date)
        suffix = cls._interpolate_tokens(suffix_template, context_date)
        padded_number = str(number).zfill(padding)
        return f"{prefix}{padded_number}{suffix}"

    @classmethod
    def _should_reset(cls, sequence: Sequence, context_date: datetime) -> bool:
        """Evaluate whether a sequence counter should reset based on its reset_period."""
        if sequence.reset_period == "never":
            return False

        last_date = sequence.last_reset_date or sequence.created_at
        if not last_date:
            return False

        # Ensure timezone-aware comparison
        if last_date.tzinfo is None:
            last_date = last_date.replace(tzinfo=timezone.utc)
        if context_date.tzinfo is None:
            context_date = context_date.replace(tzinfo=timezone.utc)

        if sequence.reset_period == "yearly":
            return context_date.year > last_date.year
        elif sequence.reset_period == "monthly":
            return (context_date.year, context_date.month) > (last_date.year, last_date.month)
        elif sequence.reset_period == "daily":
            return context_date.date() > last_date.date()

        return False

    @classmethod
    async def get_next_number(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        code: str,
        context_date: Optional[datetime] = None,
    ) -> Tuple[str, int]:
        """Atomically lock sequence row, increment counter, and return formatted sequence string."""
        target_date = context_date or datetime.now(timezone.utc)

        # High-concurrency row lock (SELECT ... FOR UPDATE)
        stmt = (
            select(Sequence)
            .where(
                Sequence.company_id == company_id,
                Sequence.code == code,
                Sequence.is_active == True,
                Sequence.deleted_at.is_(None),
            )
            .with_for_update()
        )
        result = await db.execute(stmt)
        sequence = result.scalar_one_or_none()

        if not sequence:
            raise SequenceNotFoundException(code=code, company_id=company_id)

        # Evaluate periodic reset (yearly / monthly / daily)
        if cls._should_reset(sequence, target_date):
            sequence.current_number = 0
            sequence.last_reset_date = target_date

        # Increment atomic counter
        sequence.current_number += sequence.step
        if not sequence.last_reset_date:
            sequence.last_reset_date = target_date

        # Generate formatted string
        formatted = cls.format_sequence(
            prefix_template=sequence.prefix,
            suffix_template=sequence.suffix,
            number=sequence.current_number,
            padding=sequence.padding,
            context_date=target_date,
        )

        await db.flush()
        return formatted, sequence.current_number

    @classmethod
    async def peek_next_number(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        code: str,
        context_date: Optional[datetime] = None,
    ) -> Tuple[str, int]:
        """Preview next number without incrementing or locking the database counter."""
        target_date = context_date or datetime.now(timezone.utc)

        stmt = (
            select(Sequence)
            .where(
                Sequence.company_id == company_id,
                Sequence.code == code,
                Sequence.is_active == True,
                Sequence.deleted_at.is_(None),
            )
        )
        result = await db.execute(stmt)
        sequence = result.scalar_one_or_none()

        if not sequence:
            raise SequenceNotFoundException(code=code, company_id=company_id)

        next_number = sequence.current_number
        if cls._should_reset(sequence, target_date):
            next_number = 0

        next_number += sequence.step
        formatted = cls.format_sequence(
            prefix_template=sequence.prefix,
            suffix_template=sequence.suffix,
            number=next_number,
            padding=sequence.padding,
            context_date=target_date,
        )

        return formatted, next_number

    @classmethod
    async def create_sequence(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        payload: SequenceCreate,
        user_id: Optional[uuid.UUID] = None,
    ) -> Sequence:
        """Create a new sequence definition for the tenant company."""
        # Check existing code
        existing = await db.execute(
            select(Sequence).where(
                Sequence.company_id == company_id,
                Sequence.code == payload.code,
                Sequence.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise SequenceDuplicateException(code=payload.code)

        now = datetime.now(timezone.utc)
        seq = Sequence(
            company_id=company_id,
            created_by_id=user_id,
            updated_by_id=user_id,
            name=payload.name,
            code=payload.code,
            prefix=payload.prefix,
            suffix=payload.suffix,
            padding=payload.padding,
            current_number=payload.current_number,
            step=payload.step,
            reset_period=payload.reset_period,
            last_reset_date=now if payload.current_number > 0 else None,
            is_active=payload.is_active,
        )
        db.add(seq)
        await db.flush()
        return seq

    @classmethod
    async def get_sequence(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        sequence_id: uuid.UUID,
    ) -> Sequence:
        """Retrieve sequence by UUID."""
        stmt = select(Sequence).where(
            Sequence.id == sequence_id,
            Sequence.company_id == company_id,
            Sequence.deleted_at.is_(None),
        )
        result = await db.execute(stmt)
        seq = result.scalar_one_or_none()
        if not seq:
            raise PlatformException(
                message=f"Sequence '{sequence_id}' not found.",
                code="SEQUENCE_NOT_FOUND",
                status_code=404,
            )
        return seq

    @classmethod
    async def list_sequences(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        search: Optional[str] = None,
    ) -> List[Sequence]:
        """List active sequences with optional search filtering."""
        stmt = (
            select(Sequence)
            .where(
                Sequence.company_id == company_id,
                Sequence.deleted_at.is_(None),
            )
            .order_by(Sequence.code.asc())
        )
        if search:
            stmt = stmt.where(
                Sequence.name.ilike(f"%{search}%") | Sequence.code.ilike(f"%{search}%")
            )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def update_sequence(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        sequence_id: uuid.UUID,
        payload: SequenceUpdate,
        user_id: Optional[uuid.UUID] = None,
    ) -> Sequence:
        """Update sequence settings."""
        seq = await cls.get_sequence(db, company_id, sequence_id)
        update_data = payload.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(seq, field, value)

        seq.updated_by_id = user_id
        await db.flush()
        return seq

    @classmethod
    async def delete_sequence(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        sequence_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Soft-delete a sequence definition."""
        seq = await cls.get_sequence(db, company_id, sequence_id)
        seq.deleted_at = datetime.now(timezone.utc)
        seq.deleted_by_id = user_id
        await db.flush()
