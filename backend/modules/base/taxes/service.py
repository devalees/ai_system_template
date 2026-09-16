"""Business logic and computational engine for Tax Engine & Fiscal Positions."""

import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import EntityNotFoundException, ValidationException
from modules.base.taxes.models import Tax, TaxFiscalPosition, TaxFiscalPositionRule
from modules.base.taxes.schemas import (
    TaxCreate,
    TaxUpdate,
    FiscalPositionCreate,
    FiscalPositionUpdate,
    FiscalPositionRuleCreate,
    TaxComputeRequest,
    TaxComputeResponse,
    TaxLineResult,
    TaxLineBreakdownItem,
    TaxSummaryItem,
)


class TaxService:
    """Enterprise tax calculation engine supporting multi-jurisdiction fiscal positions."""

    # -----------------------------------------------------------------------
    # Helper: Rounding
    # -----------------------------------------------------------------------

    @staticmethod
    def _round(value: Decimal, precision: Decimal) -> Decimal:
        """Quantize Decimal value to discrete precision intervals (e.g. 0.01)."""
        if precision <= 0:
            precision = Decimal("0.01")
        return (value / precision).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * precision

    # -----------------------------------------------------------------------
    # Tax CRUD
    # -----------------------------------------------------------------------

    @classmethod
    async def create_tax(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        payload: TaxCreate,
    ) -> Tax:
        """Create a new tax definition scoped to tenant company."""
        tax = Tax(
            company_id=company_id,
            name=payload.name,
            code=payload.code,
            tax_scope=payload.tax_scope,
            calculation_type=payload.calculation_type,
            amount=payload.amount,
            is_inclusive=payload.is_inclusive,
            include_base_amount=payload.include_base_amount,
            sequence=payload.sequence,
            description=payload.description,
            is_active=True,
        )
        db.add(tax)
        await db.commit()
        await db.refresh(tax)
        return tax

    @classmethod
    async def get_tax(
        cls,
        db: AsyncSession,
        tax_id: uuid.UUID,
    ) -> Tax:
        """Fetch tax definition by ID."""
        stmt = select(Tax).where(Tax.id == tax_id)
        result = await db.execute(stmt)
        tax = result.scalar_one_or_none()
        if not tax:
            raise EntityNotFoundException("Tax", tax_id)
        return tax

    @classmethod
    async def list_taxes(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        scope: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[Tax]:
        """List taxes for tenant company with optional scope and active filter."""
        stmt = select(Tax).where(Tax.company_id == company_id)
        if scope:
            stmt = stmt.where(Tax.tax_scope == scope)
        if is_active is not None:
            stmt = stmt.where(Tax.is_active == is_active)
        stmt = stmt.order_by(Tax.sequence.asc(), Tax.name.asc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def update_tax(
        cls,
        db: AsyncSession,
        tax_id: uuid.UUID,
        payload: TaxUpdate,
    ) -> Tax:
        """Update existing tax configuration."""
        tax = await cls.get_tax(db, tax_id)
        for field, val in payload.model_dump(exclude_unset=True).items():
            setattr(tax, field, val)
        await db.commit()
        await db.refresh(tax)
        return tax

    @classmethod
    async def delete_tax(
        cls,
        db: AsyncSession,
        tax_id: uuid.UUID,
    ) -> bool:
        """Soft-delete tax definition."""
        tax = await cls.get_tax(db, tax_id)
        await db.delete(tax)
        await db.commit()
        return True

    # -----------------------------------------------------------------------
    # Fiscal Position CRUD
    # -----------------------------------------------------------------------

    @classmethod
    async def create_fiscal_position(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        payload: FiscalPositionCreate,
    ) -> TaxFiscalPosition:
        """Create a new fiscal position and optional initial mapping rules."""
        fp = TaxFiscalPosition(
            company_id=company_id,
            name=payload.name,
            code=payload.code,
            description=payload.description,
            auto_apply=payload.auto_apply,
            country_id=payload.country_id,
            vat_required=payload.vat_required,
            note=payload.note,
            is_active=True,
        )
        db.add(fp)
        await db.flush()

        for rule_in in payload.rules:
            rule = TaxFiscalPositionRule(
                company_id=company_id,
                position_id=fp.id,
                source_tax_id=rule_in.source_tax_id,
                dest_tax_id=rule_in.dest_tax_id,
            )
            db.add(rule)

        await db.commit()
        return await cls.get_fiscal_position(db, fp.id)

    @classmethod
    async def get_fiscal_position(
        cls,
        db: AsyncSession,
        position_id: uuid.UUID,
    ) -> TaxFiscalPosition:
        """Fetch fiscal position by ID including its rules."""
        stmt = (
            select(TaxFiscalPosition)
            .where(TaxFiscalPosition.id == position_id)
            .options(
                selectinload(TaxFiscalPosition.rules).selectinload(TaxFiscalPositionRule.source_tax),
                selectinload(TaxFiscalPosition.rules).selectinload(TaxFiscalPositionRule.dest_tax),
            )
        )
        result = await db.execute(stmt)
        fp = result.scalar_one_or_none()
        if not fp:
            raise EntityNotFoundException("TaxFiscalPosition", position_id)
        return fp

    @classmethod
    async def list_fiscal_positions(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        is_active: Optional[bool] = None,
    ) -> List[TaxFiscalPosition]:
        """List all fiscal positions for tenant company."""
        stmt = (
            select(TaxFiscalPosition)
            .where(TaxFiscalPosition.company_id == company_id)
            .options(
                selectinload(TaxFiscalPosition.rules).selectinload(TaxFiscalPositionRule.source_tax),
                selectinload(TaxFiscalPosition.rules).selectinload(TaxFiscalPositionRule.dest_tax),
            )
        )
        if is_active is not None:
            stmt = stmt.where(TaxFiscalPosition.is_active == is_active)
        stmt = stmt.order_by(TaxFiscalPosition.name.asc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def update_fiscal_position(
        cls,
        db: AsyncSession,
        position_id: uuid.UUID,
        payload: FiscalPositionUpdate,
    ) -> TaxFiscalPosition:
        """Update existing fiscal position."""
        fp = await cls.get_fiscal_position(db, position_id)
        for field, val in payload.model_dump(exclude_unset=True).items():
            setattr(fp, field, val)
        await db.commit()
        return await cls.get_fiscal_position(db, fp.id)

    @classmethod
    async def delete_fiscal_position(
        cls,
        db: AsyncSession,
        position_id: uuid.UUID,
    ) -> bool:
        """Soft-delete fiscal position."""
        fp = await cls.get_fiscal_position(db, position_id)
        await db.delete(fp)
        await db.commit()
        return True

    @classmethod
    async def add_fiscal_position_rule(
        cls,
        db: AsyncSession,
        position_id: uuid.UUID,
        payload: FiscalPositionRuleCreate,
    ) -> TaxFiscalPositionRule:
        """Add a mapping rule to an existing fiscal position."""
        fp = await cls.get_fiscal_position(db, position_id)
        rule = TaxFiscalPositionRule(
            company_id=fp.company_id,
            position_id=fp.id,
            source_tax_id=payload.source_tax_id,
            dest_tax_id=payload.dest_tax_id,
        )
        db.add(rule)
        await db.commit()
        stmt = (
            select(TaxFiscalPositionRule)
            .where(TaxFiscalPositionRule.id == rule.id)
            .options(
                selectinload(TaxFiscalPositionRule.source_tax),
                selectinload(TaxFiscalPositionRule.dest_tax),
            )
        )
        res = await db.execute(stmt)
        return res.scalar_one()


    @classmethod
    async def delete_fiscal_position_rule(
        cls,
        db: AsyncSession,
        rule_id: uuid.UUID,
    ) -> bool:
        """Delete a fiscal position rule."""
        stmt = select(TaxFiscalPositionRule).where(TaxFiscalPositionRule.id == rule_id)
        res = await db.execute(stmt)
        rule = res.scalar_one_or_none()
        if not rule:
            raise EntityNotFoundException("TaxFiscalPositionRule", rule_id)
        await db.delete(rule)
        await db.commit()
        return True

    # -----------------------------------------------------------------------
    # Tax Computation Engine
    # -----------------------------------------------------------------------

    @classmethod
    async def compute_taxes(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        payload: TaxComputeRequest,
    ) -> TaxComputeResponse:
        """Calculate multi-line taxes, compound rates, and fiscal position substitutions."""
        precision = payload.currency_rounding

        # Step 1: Load Fiscal Position rule map if specified
        fp_applied_name: Optional[str] = None
        tax_rule_map: Dict[uuid.UUID, Optional[uuid.UUID]] = {}
        if payload.fiscal_position_id:
            fp = await cls.get_fiscal_position(db, payload.fiscal_position_id)
            fp_applied_name = fp.name
            for rule in fp.rules:
                tax_rule_map[rule.source_tax_id] = rule.dest_tax_id

        # Step 2: Determine all effective tax IDs across all lines
        all_effective_tax_ids = set()
        line_tax_mappings: List[List[uuid.UUID]] = []

        for line in payload.lines:
            effective_line_tax_ids: List[uuid.UUID] = []
            for src_id in line.tax_ids:
                if src_id in tax_rule_map:
                    dest_id = tax_rule_map[src_id]
                    if dest_id is not None:
                        effective_line_tax_ids.append(dest_id)
                        all_effective_tax_ids.add(dest_id)
                    # if dest_id is None -> tax exempt, skip!
                else:
                    effective_line_tax_ids.append(src_id)
                    all_effective_tax_ids.add(src_id)
            line_tax_mappings.append(effective_line_tax_ids)

        # Step 3: Load all needed Tax entities
        tax_registry: Dict[uuid.UUID, Tax] = {}
        if all_effective_tax_ids:
            stmt = select(Tax).where(Tax.id.in_(all_effective_tax_ids), Tax.company_id == company_id)
            taxes_res = await db.execute(stmt)
            for t in taxes_res.scalars().all():
                tax_registry[t.id] = t

        # Step 4: Evaluate each line
        evaluated_lines: List[TaxLineResult] = []
        tax_summary_dict: Dict[uuid.UUID, Dict] = {}

        for idx, line in enumerate(payload.lines):
            effective_tax_ids = line_tax_mappings[idx]
            applicable_taxes = [tax_registry[tid] for tid in effective_tax_ids if tid in tax_registry]
            applicable_taxes.sort(key=lambda t: t.sequence)

            discount_pct = line.discount_percentage or Decimal("0.0")
            discount_factor = Decimal("1.0") - (discount_pct / Decimal("100.0"))
            effective_unit_price = cls._round(line.price_unit * discount_factor, precision)
            line_gross_total = effective_unit_price * line.quantity

            # Segregate inclusive percent taxes
            inclusive_percent_sum = Decimal("0.0")
            for t in applicable_taxes:
                if t.is_inclusive and t.calculation_type == "percent":
                    inclusive_percent_sum += t.amount

            # Base taxable amount (extract inclusive portion if any)
            if inclusive_percent_sum > 0:
                divisor = Decimal("1.0") + (inclusive_percent_sum / Decimal("100.0"))
                base_unrounded = line_gross_total / divisor
            else:
                base_unrounded = line_gross_total

            current_base = base_unrounded
            line_breakdown: List[TaxLineBreakdownItem] = []
            line_total_tax = Decimal("0.0")

            for t in applicable_taxes:
                tax_base = current_base
                tax_amount = Decimal("0.0")

                if t.calculation_type == "percent":
                    tax_amount = tax_base * (t.amount / Decimal("100.0"))
                elif t.calculation_type == "fixed":
                    tax_amount = t.amount * line.quantity
                elif t.calculation_type == "division":
                    div = Decimal("100.0") - t.amount
                    if div > 0:
                        tax_amount = tax_base * (t.amount / div)

                rounded_tax_amount = cls._round(tax_amount, precision)
                rounded_tax_base = cls._round(tax_base, precision)

                line_breakdown.append(
                    TaxLineBreakdownItem(
                        tax_id=t.id,
                        tax_name=t.name,
                        rate=t.amount,
                        base_amount=rounded_tax_base,
                        tax_amount=rounded_tax_amount,
                        is_inclusive=t.is_inclusive,
                    )
                )

                line_total_tax += rounded_tax_amount

                # Compound tax: subsequent taxes include this tax amount in their base
                if t.include_base_amount:
                    current_base += tax_amount

                # Update global summary
                if t.id not in tax_summary_dict:
                    tax_summary_dict[t.id] = {
                        "tax_id": t.id,
                        "tax_name": t.name,
                        "rate": t.amount,
                        "total_base": Decimal("0.0"),
                        "total_tax": Decimal("0.0"),
                    }
                tax_summary_dict[t.id]["total_base"] += rounded_tax_base
                tax_summary_dict[t.id]["total_tax"] += rounded_tax_amount

            net_subtotal = cls._round(base_unrounded, precision)
            line_total_amount = net_subtotal + line_total_tax

            evaluated_lines.append(
                TaxLineResult(
                    line_id=line.line_id,
                    price_unit=line.price_unit,
                    quantity=line.quantity,
                    discount_percentage=discount_pct,
                    effective_unit_price=effective_unit_price,
                    net_subtotal=net_subtotal,
                    total_tax=line_total_tax,
                    total_amount=line_total_amount,
                    tax_breakdown=line_breakdown,
                )
            )

        # Step 5: Compute document-level totals
        overall_subtotal = sum((l.net_subtotal for l in evaluated_lines), Decimal("0.0"))
        overall_total_tax = sum((l.total_tax for l in evaluated_lines), Decimal("0.0"))
        overall_total_amount = overall_subtotal + overall_total_tax

        summary_items = [
            TaxSummaryItem(
                tax_id=v["tax_id"],
                tax_name=v["tax_name"],
                rate=v["rate"],
                total_base=cls._round(v["total_base"], precision),
                total_tax=cls._round(v["total_tax"], precision),
            )
            for v in tax_summary_dict.values()
        ]

        return TaxComputeResponse(
            subtotal=cls._round(overall_subtotal, precision),
            total_tax=cls._round(overall_total_tax, precision),
            total_amount=cls._round(overall_total_amount, precision),
            fiscal_position_applied=fp_applied_name,
            lines=evaluated_lines,
            tax_summary=summary_items,
        )
