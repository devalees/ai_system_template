"""Business domain service for Unit of Measure & Conversion Matrix."""

import uuid
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import EntityNotFoundException, ValidationException
from core.event_bus import event_bus
from modules.base.uom.models import UOMCategory, UOMUnit, UOMConversionRule
from modules.base.uom.schemas import (
    UOMCategoryCreate,
    UOMCategoryUpdate,
    UOMUnitCreate,
    UOMUnitUpdate,
    UOMConversionRuleCreate,
    UOMConvertResponse,
)

logger = logging.getLogger("sovereign.uom")


class UOMService:
    """Enterprise Unit of Measure management and multi-category conversion engine."""

    @staticmethod
    def _round_precision(val: Decimal, precision: Decimal) -> Decimal:
        """Round decimal value according to specified unit precision step."""
        if not precision or precision <= Decimal("0"):
            return val
        return (val / precision).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * precision

    # -----------------------------------------------------------------------
    # Category Management
    # -----------------------------------------------------------------------

    @classmethod
    async def create_category(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        data: UOMCategoryCreate,
    ) -> UOMCategory:
        """Create a new UOM Category."""
        stmt = select(UOMCategory).where(
            UOMCategory.company_id == company_id,
            UOMCategory.name == data.name,
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            raise ValidationException(f"UOM Category '{data.name}' already exists in this tenant.")

        category = UOMCategory(
            company_id=company_id,
            name=data.name,
            description=data.description,
        )
        db.add(category)
        await db.commit()
        await db.refresh(category)
        return category

    @classmethod
    async def get_category(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        category_id: uuid.UUID,
    ) -> UOMCategory:
        """Retrieve a UOM Category by ID."""
        stmt = select(UOMCategory).where(
            UOMCategory.id == category_id,
            UOMCategory.company_id == company_id,
        )
        category = (await db.execute(stmt)).scalar_one_or_none()
        if not category:
            raise EntityNotFoundException("UOMCategory", category_id)
        return category

    @classmethod
    async def list_categories(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
    ) -> List[UOMCategory]:
        """List all UOM Categories for the company tenant."""
        stmt = select(UOMCategory).where(
            UOMCategory.company_id == company_id
        ).order_by(UOMCategory.name.asc())
        return list((await db.execute(stmt)).scalars().all())

    @classmethod
    async def update_category(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        category_id: uuid.UUID,
        data: UOMCategoryUpdate,
    ) -> UOMCategory:
        """Update a UOM Category."""
        category = await cls.get_category(db, company_id, category_id)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(category, field, value)

        await db.commit()
        await db.refresh(category)
        return category

    @classmethod
    async def delete_category(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        category_id: uuid.UUID,
    ) -> None:
        """Delete a UOM Category and its units."""
        category = await cls.get_category(db, company_id, category_id)
        await db.delete(category)
        await db.commit()

    # -----------------------------------------------------------------------
    # Unit Management
    # -----------------------------------------------------------------------

    @classmethod
    async def create_unit(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        data: UOMUnitCreate,
    ) -> UOMUnit:
        """Create a new unit of measure."""
        # Verify parent category exists
        await cls.get_category(db, company_id, data.category_id)

        # Unique code check
        stmt = select(UOMUnit).where(
            UOMUnit.company_id == company_id,
            UOMUnit.code == data.code,
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            raise ValidationException(f"Unit of measure with code '{data.code}' already exists.")

        # Reference unit check: only 1 reference per category
        ratio = data.ratio
        if data.uom_type == "reference":
            ratio = Decimal("1.00000000")
            # Demote any existing reference unit in the same category
            stmt_ref = select(UOMUnit).where(
                UOMUnit.company_id == company_id,
                UOMUnit.category_id == data.category_id,
                UOMUnit.uom_type == "reference",
            )
            existing_ref = (await db.execute(stmt_ref)).scalars().all()
            for r_unit in existing_ref:
                r_unit.uom_type = "bigger"

        unit = UOMUnit(
            company_id=company_id,
            category_id=data.category_id,
            name=data.name,
            code=data.code,
            symbol=data.symbol,
            uom_type=data.uom_type,
            ratio=ratio,
            rounding_precision=data.rounding_precision,
        )
        db.add(unit)
        await db.commit()
        await db.refresh(unit)
        return unit

    @classmethod
    async def get_unit(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        unit_id: Optional[uuid.UUID] = None,
        code: Optional[str] = None,
    ) -> UOMUnit:
        """Retrieve a unit by ID or code within the current tenant."""
        if unit_id:
            stmt = select(UOMUnit).where(UOMUnit.id == unit_id, UOMUnit.company_id == company_id)
        elif code:
            stmt = select(UOMUnit).where(UOMUnit.code == code, UOMUnit.company_id == company_id)
        else:
            raise ValidationException("Must provide unit_id or code.")

        unit = (await db.execute(stmt)).scalar_one_or_none()
        if not unit:
            identifier = str(unit_id) if unit_id else code
            raise EntityNotFoundException("UOMUnit", identifier)
        return unit

    @classmethod
    async def list_units(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        category_id: Optional[uuid.UUID] = None,
    ) -> List[UOMUnit]:
        """List units for the tenant, with optional category filtering."""
        conditions = [UOMUnit.company_id == company_id]
        if category_id:
            conditions.append(UOMUnit.category_id == category_id)

        stmt = select(UOMUnit).where(and_(*conditions)).order_by(UOMUnit.name.asc())
        return list((await db.execute(stmt)).scalars().all())

    @classmethod
    async def update_unit(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        unit_id: uuid.UUID,
        data: UOMUnitUpdate,
    ) -> UOMUnit:
        """Update a unit of measure."""
        unit = await cls.get_unit(db, company_id, unit_id=unit_id)
        update_data = data.model_dump(exclude_unset=True)

        if "uom_type" in update_data and update_data["uom_type"] == "reference":
            update_data["ratio"] = Decimal("1.00000000")
            # Demote others
            stmt_ref = select(UOMUnit).where(
                UOMUnit.company_id == company_id,
                UOMUnit.category_id == unit.category_id,
                UOMUnit.uom_type == "reference",
                UOMUnit.id != unit.id,
            )
            for r_unit in (await db.execute(stmt_ref)).scalars().all():
                r_unit.uom_type = "bigger"

        for field, value in update_data.items():
            setattr(unit, field, value)

        await db.commit()
        await db.refresh(unit)
        return unit

    @classmethod
    async def delete_unit(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        unit_id: uuid.UUID,
    ) -> None:
        """Delete a unit of measure."""
        unit = await cls.get_unit(db, company_id, unit_id=unit_id)
        await db.delete(unit)
        await db.commit()

    # -----------------------------------------------------------------------
    # Explicit / Cross-Category Conversion Rules
    # -----------------------------------------------------------------------

    @classmethod
    async def create_conversion_rule(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        data: UOMConversionRuleCreate,
    ) -> UOMConversionRule:
        """Register an explicit or cross-category conversion multiplier."""
        # Verify both units exist in tenant
        await cls.get_unit(db, company_id, unit_id=data.from_uom_id)
        await cls.get_unit(db, company_id, unit_id=data.to_uom_id)

        rule = UOMConversionRule(
            company_id=company_id,
            from_uom_id=data.from_uom_id,
            to_uom_id=data.to_uom_id,
            ratio=data.ratio,
            res_model=data.res_model,
            res_id=data.res_id,
        )
        db.add(rule)
        await db.commit()
        await db.refresh(rule)
        return rule

    @classmethod
    async def list_conversion_rules(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        res_model: Optional[str] = None,
        res_id: Optional[uuid.UUID] = None,
    ) -> List[UOMConversionRule]:
        """List conversion rules."""
        conditions = [UOMConversionRule.company_id == company_id]
        if res_model:
            conditions.append(UOMConversionRule.res_model == res_model)
        if res_id:
            conditions.append(UOMConversionRule.res_id == res_id)

        stmt = select(UOMConversionRule).where(and_(*conditions))
        return list((await db.execute(stmt)).scalars().all())

    @classmethod
    async def delete_conversion_rule(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        rule_id: uuid.UUID,
    ) -> None:
        """Delete an explicit conversion rule."""
        stmt = select(UOMConversionRule).where(
            UOMConversionRule.id == rule_id,
            UOMConversionRule.company_id == company_id,
        )
        rule = (await db.execute(stmt)).scalar_one_or_none()
        if not rule:
            raise EntityNotFoundException("UOMConversionRule", rule_id)
        await db.delete(rule)
        await db.commit()

    # -----------------------------------------------------------------------
    # Conversion Engine
    # -----------------------------------------------------------------------

    @classmethod
    async def convert(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        quantity: Decimal,
        from_uom_id: Optional[uuid.UUID] = None,
        from_uom_code: Optional[str] = None,
        to_uom_id: Optional[uuid.UUID] = None,
        to_uom_code: Optional[str] = None,
        res_model: Optional[str] = None,
        res_id: Optional[uuid.UUID] = None,
    ) -> UOMConvertResponse:
        """Convert a quantity from one unit of measure to another."""
        from_uom = await cls.get_unit(db, company_id, unit_id=from_uom_id, code=from_uom_code)
        to_uom = await cls.get_unit(db, company_id, unit_id=to_uom_id, code=to_uom_code)

        # Identity conversion
        if from_uom.id == to_uom.id:
            return UOMConvertResponse(
                original_quantity=quantity,
                from_uom_code=from_uom.code,
                converted_quantity=quantity,
                to_uom_code=to_uom.code,
                conversion_factor=Decimal("1.0"),
                method="identity",
            )

        # 1. Check for explicit conversion rule (first item-specific, then generic)
        rule = await cls._find_conversion_rule(db, company_id, from_uom.id, to_uom.id, res_model, res_id)
        if rule:
            converted = quantity * rule.ratio
            factor = rule.ratio
            rounded = cls._round_precision(converted, to_uom.rounding_precision)
            return UOMConvertResponse(
                original_quantity=quantity,
                from_uom_code=from_uom.code,
                converted_quantity=rounded,
                to_uom_code=to_uom.code,
                conversion_factor=factor,
                method="explicit_rule",
            )

        # Check inverse explicit rule
        inv_rule = await cls._find_conversion_rule(db, company_id, to_uom.id, from_uom.id, res_model, res_id)
        if inv_rule and inv_rule.ratio > Decimal("0"):
            factor = Decimal("1.0") / inv_rule.ratio
            converted = quantity * factor
            rounded = cls._round_precision(converted, to_uom.rounding_precision)
            return UOMConvertResponse(
                original_quantity=quantity,
                from_uom_code=from_uom.code,
                converted_quantity=rounded,
                to_uom_code=to_uom.code,
                conversion_factor=factor,
                method="explicit_rule_inverse",
            )

        # 2. Intra-category conversion via Category Reference Unit
        if from_uom.category_id != to_uom.category_id:
            raise ValidationException(
                f"Cannot convert between different categories: '{from_uom.name}' and '{to_uom.name}'. "
                "No explicit cross-category conversion rule is configured."
            )

        # Convert from_uom quantity -> Reference Unit quantity
        if from_uom.uom_type == "reference":
            qty_ref = quantity
        elif from_uom.uom_type == "bigger":
            qty_ref = quantity * from_uom.ratio
        elif from_uom.uom_type == "smaller":
            qty_ref = quantity / from_uom.ratio
        else:
            qty_ref = quantity

        # Convert Reference Unit quantity -> to_uom quantity
        if to_uom.uom_type == "reference":
            qty_target = qty_ref
        elif to_uom.uom_type == "bigger":
            qty_target = qty_ref / to_uom.ratio
        elif to_uom.uom_type == "smaller":
            qty_target = qty_ref * to_uom.ratio
        else:
            qty_target = qty_ref

        factor = qty_target / quantity
        rounded = cls._round_precision(qty_target, to_uom.rounding_precision)

        return UOMConvertResponse(
            original_quantity=quantity,
            from_uom_code=from_uom.code,
            converted_quantity=rounded,
            to_uom_code=to_uom.code,
            conversion_factor=factor,
            method="intra_category",
        )

    @classmethod
    async def _find_conversion_rule(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        from_id: uuid.UUID,
        to_id: uuid.UUID,
        res_model: Optional[str] = None,
        res_id: Optional[uuid.UUID] = None,
    ) -> Optional[UOMConversionRule]:
        """Search for item-specific rule first, then global rule."""
        if res_model and res_id:
            stmt = select(UOMConversionRule).where(
                UOMConversionRule.company_id == company_id,
                UOMConversionRule.from_uom_id == from_id,
                UOMConversionRule.to_uom_id == to_id,
                UOMConversionRule.res_model == res_model,
                UOMConversionRule.res_id == res_id,
            )
            rule = (await db.execute(stmt)).scalar_one_or_none()
            if rule:
                return rule

        stmt = select(UOMConversionRule).where(
            UOMConversionRule.company_id == company_id,
            UOMConversionRule.from_uom_id == from_id,
            UOMConversionRule.to_uom_id == to_id,
            UOMConversionRule.res_model.is_(None),
            UOMConversionRule.res_id.is_(None),
        )
        return (await db.execute(stmt)).scalar_one_or_none()
