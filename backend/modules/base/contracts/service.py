"""Business logic and lifecycle management engine for Contracts, Agreements & Subscriptions."""

import uuid
from decimal import Decimal
from datetime import date, timedelta
from typing import Optional, List
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import EntityNotFoundException, ValidationException
from modules.base.parties.models import Party
from modules.base.contracts.models import Contract, ContractLine
from modules.base.contracts.schemas import (
    ContractCreate,
    ContractUpdate,
    ContractRenewRequest,
    ContractTerminateRequest,
)


class ContractService:
    """Service managing commercial agreements, recurring renewals, and state lifecycles."""

    # -----------------------------------------------------------------------
    # Contract CRUD
    # -----------------------------------------------------------------------

    @classmethod
    async def create_contract(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        payload: ContractCreate,
    ) -> Contract:
        """Create new commercial contract with line items and financial commitments."""
        # 1. Verify party exists
        stmt = select(Party).where(Party.id == payload.party_id)
        p_res = await db.execute(stmt)
        if not p_res.scalar_one_or_none():
            raise EntityNotFoundException("Party", payload.party_id)

        seq_no = payload.sequence_number or f"CTR-{uuid.uuid4().hex[:8].upper()}"

        contract = Contract(
            company_id=company_id,
            sequence_number=seq_no,
            title=payload.title,
            party_id=payload.party_id,
            contract_type=payload.contract_type,
            start_date=payload.start_date,
            end_date=payload.end_date,
            billing_frequency=payload.billing_frequency,
            amount=payload.amount,
            currency_id=payload.currency_id,
            auto_renew=payload.auto_renew,
            notice_days=payload.notice_days,
            state="draft",
            terms_and_conditions=payload.terms_and_conditions,
            notes=payload.notes,
        )
        db.add(contract)
        await db.flush()

        lines_total = Decimal("0.00")
        for line_in in payload.lines:
            line_subtotal = (line_in.quantity * line_in.unit_price).quantize(Decimal("0.01"))
            lines_total += line_subtotal
            line = ContractLine(
                company_id=company_id,
                contract_id=contract.id,
                name=line_in.name,
                quantity=line_in.quantity,
                unit_price=line_in.unit_price,
                subtotal=line_subtotal,
            )
            db.add(line)

        # If amount was omitted or zero, but lines exist, sum lines
        if contract.amount == Decimal("0.00") and lines_total > Decimal("0.00"):
            contract.amount = lines_total

        await db.commit()
        return await cls.get_contract(db, contract.id)

    @classmethod
    async def get_contract(
        cls,
        db: AsyncSession,
        contract_id: uuid.UUID,
    ) -> Contract:
        """Fetch contract by ID with party, currency, and line items loaded."""
        stmt = (
            select(Contract)
            .where(Contract.id == contract_id)
            .options(
                selectinload(Contract.party),
                selectinload(Contract.currency),
                selectinload(Contract.lines),
            )
        )
        result = await db.execute(stmt)
        contract = result.scalar_one_or_none()
        if not contract:
            raise EntityNotFoundException("Contract", contract_id)
        return contract

    @classmethod
    async def list_contracts(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        party_id: Optional[uuid.UUID] = None,
        contract_type: Optional[str] = None,
        state: Optional[str] = None,
    ) -> List[Contract]:
        """List contracts for tenant company with optional party and state filters."""
        stmt = (
            select(Contract)
            .where(Contract.company_id == company_id)
            .options(
                selectinload(Contract.party),
                selectinload(Contract.currency),
                selectinload(Contract.lines),
            )
        )
        if party_id:
            stmt = stmt.where(Contract.party_id == party_id)
        if contract_type:
            stmt = stmt.where(Contract.contract_type == contract_type)
        if state:
            stmt = stmt.where(Contract.state == state)
        stmt = stmt.order_by(Contract.start_date.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def update_contract(
        cls,
        db: AsyncSession,
        contract_id: uuid.UUID,
        payload: ContractUpdate,
    ) -> Contract:
        """Update contract parameters."""
        contract = await cls.get_contract(db, contract_id)
        for field, val in payload.model_dump(exclude_unset=True).items():
            setattr(contract, field, val)
        await db.commit()
        return await cls.get_contract(db, contract.id)

    @classmethod
    async def delete_contract(
        cls,
        db: AsyncSession,
        contract_id: uuid.UUID,
    ) -> bool:
        """Soft-delete contract."""
        contract = await cls.get_contract(db, contract_id)
        await db.delete(contract)
        await db.commit()
        return True

    # -----------------------------------------------------------------------
    # State Transitions & Renewals
    # -----------------------------------------------------------------------

    @classmethod
    async def activate_contract(
        cls,
        db: AsyncSession,
        contract_id: uuid.UUID,
    ) -> Contract:
        """Transition draft contract to active."""
        contract = await cls.get_contract(db, contract_id)
        if contract.state != "draft":
            raise ValidationException(f"Only draft contracts can be activated. Current state: '{contract.state}'")
        contract.state = "active"
        await db.commit()
        return await cls.get_contract(db, contract.id)

    @classmethod
    async def renew_contract(
        cls,
        db: AsyncSession,
        contract_id: uuid.UUID,
        payload: ContractRenewRequest,
    ) -> Contract:
        """Extend contract end date and reactivate."""
        contract = await cls.get_contract(db, contract_id)
        if contract.state not in ("active", "expired"):
            raise ValidationException(f"Cannot renew contract in '{contract.state}' state.")

        if payload.new_end_date <= contract.start_date:
            raise ValidationException("New renewal end date must be strictly after the contract start date.")

        if contract.end_date and payload.new_end_date <= contract.end_date:
            raise ValidationException("New renewal end date must be later than the existing expiration date.")

        contract.end_date = payload.new_end_date
        contract.state = "active"
        await db.commit()
        return await cls.get_contract(db, contract.id)

    @classmethod
    async def terminate_contract(
        cls,
        db: AsyncSession,
        contract_id: uuid.UUID,
        payload: ContractTerminateRequest,
    ) -> Contract:
        """Terminate active contract."""
        contract = await cls.get_contract(db, contract_id)
        if contract.state not in ("active", "draft"):
            raise ValidationException(f"Cannot terminate contract in '{contract.state}' state.")

        contract.state = "terminated"
        if payload.reason:
            note_entry = f"[Terminated on {date.today()}]: {payload.reason}"
            contract.notes = f"{contract.notes}\n{note_entry}" if contract.notes else note_entry

        await db.commit()
        return await cls.get_contract(db, contract.id)

    @classmethod
    async def cancel_contract(
        cls,
        db: AsyncSession,
        contract_id: uuid.UUID,
    ) -> Contract:
        """Cancel contract."""
        contract = await cls.get_contract(db, contract_id)
        contract.state = "cancelled"
        await db.commit()
        return await cls.get_contract(db, contract.id)

    # -----------------------------------------------------------------------
    # Expiring Contracts Detection
    # -----------------------------------------------------------------------

    @classmethod
    async def get_expiring_contracts(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        horizon_days: int = 30,
    ) -> List[Contract]:
        """Fetch active contracts nearing expiration within a specified day horizon."""
        today = date.today()
        deadline = today + timedelta(days=horizon_days)

        stmt = (
            select(Contract)
            .where(
                Contract.company_id == company_id,
                Contract.state == "active",
                Contract.end_date.is_not(None),
                Contract.end_date <= deadline,
            )
            .options(
                selectinload(Contract.party),
                selectinload(Contract.currency),
                selectinload(Contract.lines),
            )
            .order_by(Contract.end_date.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
