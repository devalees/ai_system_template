"""Business logic and computational engine for Payment Terms, Methods & Transactions."""

import uuid
import calendar
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date, timedelta, timezone
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import EntityNotFoundException, ValidationException
from modules.base.payments.models import PaymentMethod, PaymentTerms, PaymentTermsLine, PaymentTransaction
from modules.base.payments.schemas import (
    PaymentMethodCreate,
    PaymentMethodUpdate,
    PaymentTermsCreate,
    PaymentTermsUpdate,
    PaymentTransactionCreate,
    PaymentTransactionUpdate,
    ComputePaymentScheduleRequest,
    ComputePaymentScheduleResponse,
    PaymentInstallment,
)


class PaymentTermsService:
    """Service managing payment instruments, installment calculation, and transaction lifecycles."""

    @staticmethod
    def _round(value: Decimal, precision: Decimal) -> Decimal:
        """Round decimal to currency precision."""
        if precision <= 0:
            precision = Decimal("0.01")
        return (value / precision).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * precision

    # -----------------------------------------------------------------------
    # Payment Methods CRUD
    # -----------------------------------------------------------------------

    @classmethod
    async def create_payment_method(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        payload: PaymentMethodCreate,
    ) -> PaymentMethod:
        """Create new payment instrument method."""
        method = PaymentMethod(
            company_id=company_id,
            name=payload.name,
            code=payload.code,
            method_type=payload.method_type,
            description=payload.description,
            is_active=True,
        )
        db.add(method)
        await db.commit()
        await db.refresh(method)
        return method

    @classmethod
    async def get_payment_method(
        cls,
        db: AsyncSession,
        method_id: uuid.UUID,
    ) -> PaymentMethod:
        """Fetch payment method by ID."""
        stmt = select(PaymentMethod).where(PaymentMethod.id == method_id)
        result = await db.execute(stmt)
        method = result.scalar_one_or_none()
        if not method:
            raise EntityNotFoundException("PaymentMethod", method_id)
        return method

    @classmethod
    async def list_payment_methods(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        is_active: Optional[bool] = None,
    ) -> List[PaymentMethod]:
        """List payment methods for tenant company."""
        stmt = select(PaymentMethod).where(PaymentMethod.company_id == company_id)
        if is_active is not None:
            stmt = stmt.where(PaymentMethod.is_active == is_active)
        stmt = stmt.order_by(PaymentMethod.name.asc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def update_payment_method(
        cls,
        db: AsyncSession,
        method_id: uuid.UUID,
        payload: PaymentMethodUpdate,
    ) -> PaymentMethod:
        """Update payment method attributes."""
        method = await cls.get_payment_method(db, method_id)
        for field, val in payload.model_dump(exclude_unset=True).items():
            setattr(method, field, val)
        await db.commit()
        await db.refresh(method)
        return method

    @classmethod
    async def delete_payment_method(
        cls,
        db: AsyncSession,
        method_id: uuid.UUID,
    ) -> bool:
        """Soft-delete payment method."""
        method = await cls.get_payment_method(db, method_id)
        await db.delete(method)
        await db.commit()
        return True

    # -----------------------------------------------------------------------
    # Payment Terms CRUD
    # -----------------------------------------------------------------------

    @classmethod
    async def create_payment_terms(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        payload: PaymentTermsCreate,
    ) -> PaymentTerms:
        """Create new payment terms schedule with installment lines."""
        terms = PaymentTerms(
            company_id=company_id,
            name=payload.name,
            code=payload.code,
            description=payload.description,
            is_active=True,
        )
        db.add(terms)
        await db.flush()

        for idx, line_in in enumerate(payload.lines):
            line = PaymentTermsLine(
                company_id=company_id,
                terms_id=terms.id,
                sequence=line_in.sequence or (idx + 1) * 10,
                value_type=line_in.value_type,
                value=line_in.value,
                days=line_in.days,
                option=line_in.option,
            )
            db.add(line)

        await db.commit()
        return await cls.get_payment_terms(db, terms.id)

    @classmethod
    async def get_payment_terms(
        cls,
        db: AsyncSession,
        terms_id: uuid.UUID,
    ) -> PaymentTerms:
        """Fetch payment terms by ID including ordered installment lines."""
        stmt = (
            select(PaymentTerms)
            .where(PaymentTerms.id == terms_id)
            .options(selectinload(PaymentTerms.lines))
        )
        result = await db.execute(stmt)
        terms = result.scalar_one_or_none()
        if not terms:
            raise EntityNotFoundException("PaymentTerms", terms_id)
        return terms

    @classmethod
    async def list_payment_terms(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        is_active: Optional[bool] = None,
    ) -> List[PaymentTerms]:
        """List payment terms for tenant company."""
        stmt = (
            select(PaymentTerms)
            .where(PaymentTerms.company_id == company_id)
            .options(selectinload(PaymentTerms.lines))
        )
        if is_active is not None:
            stmt = stmt.where(PaymentTerms.is_active == is_active)
        stmt = stmt.order_by(PaymentTerms.name.asc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def update_payment_terms(
        cls,
        db: AsyncSession,
        terms_id: uuid.UUID,
        payload: PaymentTermsUpdate,
    ) -> PaymentTerms:
        """Update payment terms header."""
        terms = await cls.get_payment_terms(db, terms_id)
        for field, val in payload.model_dump(exclude_unset=True).items():
            setattr(terms, field, val)
        await db.commit()
        return await cls.get_payment_terms(db, terms.id)

    @classmethod
    async def delete_payment_terms(
        cls,
        db: AsyncSession,
        terms_id: uuid.UUID,
    ) -> bool:
        """Soft-delete payment terms."""
        terms = await cls.get_payment_terms(db, terms_id)
        await db.delete(terms)
        await db.commit()
        return True

    # -----------------------------------------------------------------------
    # Installment Schedule Calculation
    # -----------------------------------------------------------------------

    @classmethod
    async def compute_due_dates(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        payload: ComputePaymentScheduleRequest,
    ) -> ComputePaymentScheduleResponse:
        """Compute cash flow installment amounts and due dates based on payment terms."""
        terms = await cls.get_payment_terms(db, payload.terms_id)
        if terms.company_id != company_id:
            raise ValidationException("Payment terms do not belong to active company.")

        base_date = payload.invoice_date or date.today()
        precision = payload.currency_rounding
        total = payload.total_amount
        remaining_amount = total

        installments: List[PaymentInstallment] = []
        sorted_lines = sorted(terms.lines, key=lambda l: l.sequence)

        if not sorted_lines:
            # Default to 100% due immediately
            installments.append(
                PaymentInstallment(
                    installment_number=1,
                    due_date=base_date,
                    amount=cls._round(total, precision),
                    percentage=Decimal("100.00"),
                )
            )
        else:
            for idx, line in enumerate(sorted_lines):
                # 1. Compute installment amount
                if line.value_type == "percent":
                    amt = (total * line.value) / Decimal("100.0")
                elif line.value_type == "fixed":
                    amt = min(line.value, remaining_amount)
                elif line.value_type == "balance":
                    amt = max(Decimal("0.0"), remaining_amount)
                else:
                    amt = Decimal("0.0")

                # If this is the last line, allocate any remaining fraction to avoid roundoff gaps
                if idx == len(sorted_lines) - 1 and remaining_amount > Decimal("0.0"):
                    amt = remaining_amount

                rounded_amt = cls._round(amt, precision)
                remaining_amount -= rounded_amt

                # 2. Compute due date
                if line.option == "days_after_invoice":
                    due = base_date + timedelta(days=line.days)
                elif line.option == "end_of_month":
                    _, last_day = calendar.monthrange(base_date.year, base_date.month)
                    due = date(base_date.year, base_date.month, last_day)
                elif line.option == "days_after_end_of_month":
                    _, last_day = calendar.monthrange(base_date.year, base_date.month)
                    end_of_month = date(base_date.year, base_date.month, last_day)
                    due = end_of_month + timedelta(days=line.days)
                else:
                    due = base_date + timedelta(days=line.days)

                pct = Decimal("0.00")
                if total > 0:
                    pct = (rounded_amt / total * Decimal("100.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                installments.append(
                    PaymentInstallment(
                        installment_number=idx + 1,
                        due_date=due,
                        amount=rounded_amt,
                        percentage=pct,
                    )
                )

        return ComputePaymentScheduleResponse(
            terms_id=terms.id,
            terms_name=terms.name,
            total_amount=cls._round(total, precision),
            installments=installments,
        )

    # -----------------------------------------------------------------------
    # Payment Transaction CRUD & State Transitions
    # -----------------------------------------------------------------------

    @classmethod
    async def create_transaction(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        payload: PaymentTransactionCreate,
    ) -> PaymentTransaction:
        """Register a new payment transaction in draft state."""
        # Verify payment method exists
        await cls.get_payment_method(db, payload.payment_method_id)

        tx = PaymentTransaction(
            company_id=company_id,
            payment_number=payload.payment_number,
            res_model=payload.res_model,
            res_id=payload.res_id,
            party_id=payload.party_id,
            payment_method_id=payload.payment_method_id,
            transaction_type=payload.transaction_type,
            amount=payload.amount,
            currency_id=payload.currency_id,
            payment_date=payload.payment_date or datetime.now(timezone.utc),
            reference=payload.reference,
            status="draft",
            notes=payload.notes,
        )
        db.add(tx)
        await db.commit()
        stmt = (
            select(PaymentTransaction)
            .where(PaymentTransaction.id == tx.id)
            .options(selectinload(PaymentTransaction.payment_method))
        )
        res = await db.execute(stmt)
        return res.scalar_one()

    @classmethod
    async def get_transaction(
        cls,
        db: AsyncSession,
        transaction_id: uuid.UUID,
    ) -> PaymentTransaction:
        """Fetch payment transaction by ID."""
        stmt = (
            select(PaymentTransaction)
            .where(PaymentTransaction.id == transaction_id)
            .options(selectinload(PaymentTransaction.payment_method))
        )
        result = await db.execute(stmt)
        tx = result.scalar_one_or_none()
        if not tx:
            raise EntityNotFoundException("PaymentTransaction", transaction_id)
        return tx

    @classmethod
    async def list_transactions(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        status: Optional[str] = None,
        party_id: Optional[uuid.UUID] = None,
        res_model: Optional[str] = None,
        res_id: Optional[uuid.UUID] = None,
    ) -> List[PaymentTransaction]:
        """List transactions for tenant company with flexible filtering."""
        stmt = (
            select(PaymentTransaction)
            .where(PaymentTransaction.company_id == company_id)
            .options(selectinload(PaymentTransaction.payment_method))
        )
        if status:
            stmt = stmt.where(PaymentTransaction.status == status)
        if party_id:
            stmt = stmt.where(PaymentTransaction.party_id == party_id)
        if res_model:
            stmt = stmt.where(PaymentTransaction.res_model == res_model)
        if res_id:
            stmt = stmt.where(PaymentTransaction.res_id == res_id)
        stmt = stmt.order_by(PaymentTransaction.payment_date.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def update_transaction(
        cls,
        db: AsyncSession,
        transaction_id: uuid.UUID,
        payload: PaymentTransactionUpdate,
    ) -> PaymentTransaction:
        """Update draft or cleared payment transaction notes and reference."""
        tx = await cls.get_transaction(db, transaction_id)
        if tx.status == "reconciled":
            raise ValidationException("Cannot update notes or reference on a reconciled payment transaction.")
        for field, val in payload.model_dump(exclude_unset=True).items():
            setattr(tx, field, val)
        await db.commit()
        return await cls.get_transaction(db, tx.id)

    @classmethod
    async def clear_transaction(
        cls,
        db: AsyncSession,
        transaction_id: uuid.UUID,
    ) -> PaymentTransaction:
        """Transition payment transaction from draft to cleared."""
        tx = await cls.get_transaction(db, transaction_id)
        if tx.status != "draft":
            raise ValidationException(f"Only draft transactions can be cleared. Current status: '{tx.status}'")
        tx.status = "cleared"
        await db.commit()
        return await cls.get_transaction(db, tx.id)

    @classmethod
    async def reconcile_transaction(
        cls,
        db: AsyncSession,
        transaction_id: uuid.UUID,
    ) -> PaymentTransaction:
        """Transition payment transaction to reconciled."""
        tx = await cls.get_transaction(db, transaction_id)
        if tx.status not in ("draft", "cleared"):
            raise ValidationException(f"Cannot reconcile transaction in '{tx.status}' status.")
        tx.status = "reconciled"
        await db.commit()
        return await cls.get_transaction(db, tx.id)

    @classmethod
    async def cancel_transaction(
        cls,
        db: AsyncSession,
        transaction_id: uuid.UUID,
    ) -> PaymentTransaction:
        """Cancel payment transaction."""
        tx = await cls.get_transaction(db, transaction_id)
        if tx.status == "reconciled":
            raise ValidationException("Cannot cancel a reconciled payment transaction. It must be un-reconciled first.")
        tx.status = "cancelled"
        await db.commit()
        return await cls.get_transaction(db, tx.id)
