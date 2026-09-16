"""Business domain service for Pricing Engine & Multi-Tier Price Lists."""

import uuid
import logging
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import EntityNotFoundException, ValidationException
from modules.base.pricing.models import PriceList, PriceListItem
from modules.base.pricing.schemas import (
    PriceListCreate,
    PriceListUpdate,
    PriceListItemCreate,
    PriceListItemUpdate,
    PriceEvaluateRequest,
    PriceEvaluateResponse,
)

logger = logging.getLogger("sovereign.pricing")


class PricingService:
    """Multi-currency, tiered, and promotional commercial pricing engine."""

    # -----------------------------------------------------------------------
    # Price List CRUD
    # -----------------------------------------------------------------------

    @classmethod
    async def create_price_list(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        data: PriceListCreate,
    ) -> PriceList:
        """Create a new PriceList catalog."""
        stmt = select(PriceList).where(
            PriceList.company_id == company_id,
            PriceList.code == data.code,
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            raise ValidationException(f"Price list with code '{data.code}' already exists.")

        price_list = PriceList(
            company_id=company_id,
            name=data.name,
            code=data.code,
            description=data.description,
            currency_id=data.currency_id,
        )
        db.add(price_list)
        await db.commit()
        await db.refresh(price_list)
        return price_list

    @classmethod
    async def get_price_list(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        price_list_id: uuid.UUID,
    ) -> PriceList:
        """Retrieve a PriceList by ID."""
        stmt = select(PriceList).where(
            PriceList.id == price_list_id,
            PriceList.company_id == company_id,
        )
        price_list = (await db.execute(stmt)).scalar_one_or_none()
        if not price_list:
            raise EntityNotFoundException("PriceList", price_list_id)
        return price_list

    @classmethod
    async def list_price_lists(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        is_active: Optional[bool] = None,
    ) -> List[PriceList]:
        """List price lists for the tenant."""
        conditions = [PriceList.company_id == company_id]
        if is_active is not None:
            conditions.append(PriceList.is_active == is_active)

        stmt = select(PriceList).where(and_(*conditions)).order_by(PriceList.name.asc())
        return list((await db.execute(stmt)).scalars().all())

    @classmethod
    async def update_price_list(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        price_list_id: uuid.UUID,
        data: PriceListUpdate,
    ) -> PriceList:
        """Update a price list."""
        price_list = await cls.get_price_list(db, company_id, price_list_id)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(price_list, field, value)

        await db.commit()
        await db.refresh(price_list)
        return price_list

    @classmethod
    async def delete_price_list(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        price_list_id: uuid.UUID,
    ) -> None:
        """Delete a price list and all its child items."""
        price_list = await cls.get_price_list(db, company_id, price_list_id)
        await db.delete(price_list)
        await db.commit()

    # -----------------------------------------------------------------------
    # Price List Items Management
    # -----------------------------------------------------------------------

    @classmethod
    async def add_item(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        price_list_id: uuid.UUID,
        data: PriceListItemCreate,
    ) -> PriceListItem:
        """Add a pricing rule line to a PriceList."""
        await cls.get_price_list(db, company_id, price_list_id)

        item = PriceListItem(
            company_id=company_id,
            price_list_id=price_list_id,
            applied_on=data.applied_on,
            res_model=data.res_model,
            res_id=data.res_id,
            min_quantity=data.min_quantity,
            pricing_mode=data.pricing_mode,
            fixed_price=data.fixed_price,
            discount_percentage=data.discount_percentage,
            formula_markup_percentage=data.formula_markup_percentage,
            formula_surcharge=data.formula_surcharge,
            valid_from=data.valid_from,
            valid_to=data.valid_to,
            sequence=data.sequence,
        )
        db.add(item)
        await db.commit()
        await db.refresh(item)
        return item

    @classmethod
    async def get_item(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> PriceListItem:
        """Retrieve a specific pricing item by ID."""
        stmt = select(PriceListItem).where(
            PriceListItem.id == item_id,
            PriceListItem.company_id == company_id,
        )
        item = (await db.execute(stmt)).scalar_one_or_none()
        if not item:
            raise EntityNotFoundException("PriceListItem", item_id)
        return item

    @classmethod
    async def update_item(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        item_id: uuid.UUID,
        data: PriceListItemUpdate,
    ) -> PriceListItem:
        """Update a pricing rule line."""
        item = await cls.get_item(db, company_id, item_id)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(item, field, value)

        await db.commit()
        await db.refresh(item)
        return item

    @classmethod
    async def delete_item(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> None:
        """Delete a pricing rule line."""
        item = await cls.get_item(db, company_id, item_id)
        await db.delete(item)
        await db.commit()

    # -----------------------------------------------------------------------
    # Pricing Evaluation Engine
    # -----------------------------------------------------------------------

    @classmethod
    async def evaluate_price(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        data: PriceEvaluateRequest,
    ) -> PriceEvaluateResponse:
        """Evaluate tiered and promotional pricing rules for a product line."""
        price_list = await cls.get_price_list(db, company_id, data.price_list_id)
        eval_dt = data.evaluation_date or datetime.now(timezone.utc)
        if eval_dt.tzinfo is None:
            eval_dt = eval_dt.replace(tzinfo=timezone.utc)

        # Candidate items: company, price_list, min_quantity <= requested quantity
        stmt = select(PriceListItem).where(
            PriceListItem.company_id == company_id,
            PriceListItem.price_list_id == price_list.id,
            PriceListItem.min_quantity <= data.quantity,
        )
        candidates = list((await db.execute(stmt)).scalars().all())

        # Date validity and scope filtering
        valid_candidates = []
        for item in candidates:
            # Check valid_from
            if item.valid_from:
                vf = item.valid_from if item.valid_from.tzinfo else item.valid_from.replace(tzinfo=timezone.utc)
                if vf > eval_dt:
                    continue
            # Check valid_to
            if item.valid_to:
                vt = item.valid_to if item.valid_to.tzinfo else item.valid_to.replace(tzinfo=timezone.utc)
                if vt < eval_dt:
                    continue

            # Check Scope Match
            scope_score = 0
            if item.applied_on == "product":
                if data.res_id and item.res_id == data.res_id:
                    scope_score = 3
                else:
                    continue
            elif item.applied_on == "category":
                if data.category_id and item.res_id == data.category_id:
                    scope_score = 2
                else:
                    continue
            elif item.applied_on == "all":
                scope_score = 1

            valid_candidates.append((scope_score, item))

        if not valid_candidates:
            # No matching rule: standard base catalog price
            unit_price = data.base_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            total = (unit_price * data.quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return PriceEvaluateResponse(
                price_list_id=price_list.id,
                base_price=data.base_price,
                quantity=data.quantity,
                unit_price=unit_price,
                total_amount=total,
                discount_amount=Decimal("0.00"),
                discount_percentage=Decimal("0.00"),
                applied_rule_id=None,
                applied_mode="none",
            )

        # Sort: Highest scope score first (product=3, category=2, all=1),
        # then highest min_quantity (best volume tier break),
        # then lowest sequence number.
        valid_candidates.sort(key=lambda x: (-x[0], -x[1].min_quantity, x[1].sequence))
        winning_rule = valid_candidates[0][1]

        # Calculate unit price based on rule pricing_mode
        if winning_rule.pricing_mode == "fixed":
            unit_price = (winning_rule.fixed_price or data.base_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            discount_amount = max(Decimal("0.00"), (data.base_price - unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            discount_pct = ((discount_amount / data.base_price) * Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        elif winning_rule.pricing_mode == "percentage_discount":
            discount_pct = (winning_rule.discount_percentage or Decimal("0.00")).quantize(Decimal("0.01"))
            discount_amount = (data.base_price * (discount_pct / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            unit_price = (data.base_price - discount_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        elif winning_rule.pricing_mode == "formula":
            markup_pct = winning_rule.formula_markup_percentage or Decimal("0.00")
            surcharge = winning_rule.formula_surcharge or Decimal("0.00")
            marked_up = data.base_price * (Decimal("1.00") + markup_pct / Decimal("100.00"))
            unit_price = (marked_up + surcharge).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            discount_amount = max(Decimal("0.00"), (data.base_price - unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            discount_pct = None
        else:
            unit_price = data.base_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            discount_amount = Decimal("0.00")
            discount_pct = Decimal("0.00")

        total_amount = (unit_price * data.quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        return PriceEvaluateResponse(
            price_list_id=price_list.id,
            base_price=data.base_price,
            quantity=data.quantity,
            unit_price=unit_price,
            total_amount=total_amount,
            discount_amount=discount_amount,
            discount_percentage=discount_pct,
            applied_rule_id=winning_rule.id,
            applied_mode=winning_rule.pricing_mode,
        )
