"""Enterprise Purchases & Procurement Service Engine."""

import uuid
from decimal import Decimal
from typing import Optional, List
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.event_bus import event_bus
from core.exceptions import NotFoundException, ValidationException
from modules.base.sequences.service import SequenceService
from modules.base.settings.service import SettingsService
from modules.apps.purchases.models import PurchaseOrder, PurchaseOrderLine
from modules.apps.purchases.schemas import PurchaseOrderCreate
from modules.apps.purchases.settings import PurchaseSettings
from modules.apps.accounting.models import Account, AccountJournal, AccountMove
from modules.apps.accounting.schemas import AccountMoveCreate, AccountMoveLineCreate
from modules.apps.accounting.service import AccountingService


class PurchaseService:
    """Core domain operations for RFQs, Purchase Orders, and Vendor Billing Bridge."""

    @staticmethod
    async def create_order(
        db: AsyncSession, payload: PurchaseOrderCreate, company_id: uuid.UUID
    ) -> PurchaseOrder:
        """Create a new purchase order draft with line computations."""
        order = PurchaseOrder(
            company_id=company_id,
            party_id=payload.party_id,
            order_date=payload.order_date,
            currency_id=payload.currency_id,
            payment_term_id=payload.payment_term_id,
            analytic_account_id=payload.analytic_account_id,
            state="draft",
            bill_status="to_bill",
        )
        db.add(order)
        await db.flush()

        untaxed = Decimal("0.0000")
        tax_total = Decimal("0.0000")

        for l_dto in payload.lines:
            line_dict = l_dto.model_dump()
            if l_dto.product_id:
                try:
                    from modules.base.products.service import ProductService
                    defaults = await ProductService.resolve_product_defaults(
                        db, company_id, l_dto.product_id, for_operation="purchase"
                    )
                    if not line_dict.get("name"):
                        line_dict["name"] = defaults["name"]
                    if line_dict.get("unit_price") is None:
                        line_dict["unit_price"] = Decimal(str(defaults["unit_price"]))
                    if not line_dict.get("uom_id") and defaults.get("uom_id"):
                        line_dict["uom_id"] = uuid.UUID(defaults["uom_id"])
                    if not line_dict.get("tax_ids") and defaults.get("tax_ids"):
                        line_dict["tax_ids"] = defaults["tax_ids"]
                except Exception:
                    pass

            if line_dict.get("name") is None:
                line_dict["name"] = "Item"
            if line_dict.get("unit_price") is None:
                line_dict["unit_price"] = Decimal("0.0000")

            unit_price = line_dict["unit_price"]
            subtotal = l_dto.quantity * unit_price
            tax_amt = (subtotal * Decimal("0.15")) if line_dict.get("tax_ids") else Decimal("0.0000")
            total = subtotal + tax_amt

            untaxed += subtotal
            tax_total += tax_amt

            line = PurchaseOrderLine(
                **line_dict,
                order_id=order.id,
                company_id=company_id,
                price_subtotal=subtotal,
                price_total=total,
            )
            db.add(line)

        order.amount_untaxed = untaxed
        order.amount_tax = tax_total
        order.amount_total = untaxed + tax_total

        await db.commit()
        stmt = sa.select(PurchaseOrder).options(selectinload(PurchaseOrder.lines)).where(PurchaseOrder.id == order.id)
        return (await db.execute(stmt)).scalar_one()

    @staticmethod
    async def confirm_order(
        db: AsyncSession, order_id: uuid.UUID, company_id: uuid.UUID
    ) -> PurchaseOrder:
        """Confirm a purchase order, evaluating approval thresholds and stamping legal sequence."""
        stmt = (
            sa.select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.lines))
            .where(
                PurchaseOrder.id == order_id,
                PurchaseOrder.company_id == company_id,
                PurchaseOrder.deleted_at.is_(None),
            )
        )
        res = await db.execute(stmt)
        order = res.scalar_one_or_none()
        if not order:
            raise NotFoundException("PurchaseOrder", order_id)

        if order.state == "purchase":
            return order

        # Evaluate procurement settings
        raw_settings = await SettingsService.get_settings(db, "purchases", company_id)
        settings = PurchaseSettings(**raw_settings) if raw_settings else PurchaseSettings()
        if float(order.amount_total) > settings.po_approval_threshold:
            # Requires approval
            order.state = "to_approve"
        else:
            order.state = "purchase"

        try:
            seq_num, _ = await SequenceService.get_next_number(db, company_id, "purchase.order")
        except Exception:
            seq_num = f"PO/{order.order_date.year}/{uuid.uuid4().hex[:6].upper()}"
        order.order_number = seq_num

        await db.commit()
        await db.refresh(order)

        await event_bus.publish(
            "purchases.order.confirmed",
            {
                "order_id": str(order.id),
                "order_number": order.order_number,
                "amount_total": float(order.amount_total),
                "party_id": str(order.party_id),
                "company_id": str(company_id),
            },
        )
        return order

    @staticmethod
    async def create_bill(
        db: AsyncSession, order_id: uuid.UUID, company_id: uuid.UUID
    ) -> AccountMove:
        """1-Click Generation of draft Vendor Bill in Accounting from confirmed Purchase Order."""
        stmt = (
            sa.select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.lines))
            .where(
                PurchaseOrder.id == order_id,
                PurchaseOrder.company_id == company_id,
                PurchaseOrder.deleted_at.is_(None),
            )
        )
        res = await db.execute(stmt)
        order = res.scalar_one_or_none()
        if not order:
            raise NotFoundException("PurchaseOrder", order_id)

        if order.bill_id:
            bill_res = await db.execute(
                sa.select(AccountMove).where(AccountMove.id == order.bill_id)
            )
            return bill_res.scalar_one()

        # Find or use Purchase Journal
        j_res = await db.execute(
            sa.select(AccountJournal).where(
                AccountJournal.company_id == company_id,
                AccountJournal.type == "purchase",
                AccountJournal.deleted_at.is_(None),
            )
        )
        journal = j_res.scalar_one_or_none()
        if not journal:
            any_j = await db.execute(
                sa.select(AccountJournal).where(AccountJournal.company_id == company_id)
            )
            journal = any_j.scalar_one_or_none()
            if not journal:
                raise ValidationException("No accounting journal configured for purchase billing.")

        # Find AP Payable Account and Expense Account
        pay_res = await db.execute(
            sa.select(Account).where(
                Account.company_id == company_id,
                Account.account_type.in_(("liability_current", "liability")),
                Account.reconcilable.is_(True),
            )
        )
        payable_acc = pay_res.scalar_one_or_none()

        exp_res = await db.execute(
            sa.select(Account).where(
                Account.company_id == company_id,
                Account.account_type.in_(("expense", "expense_depreciation")),
            )
        )
        expense_acc = exp_res.scalar_one_or_none()

        if not payable_acc or not expense_acc:
            all_accs = (await db.execute(sa.select(Account).where(Account.company_id == company_id))).scalars().all()
            if len(all_accs) < 2:
                raise ValidationException("Need at least 2 Chart of Accounts entries (Payable & Expense) to bill.")
            expense_acc = all_accs[0]
            payable_acc = all_accs[1]

        # Construct balanced Vendor Bill lines:
        # Debit: Expense Account (Total amount)
        # Credit: Accounts Payable (Total amount)
        bill_lines = [
            AccountMoveLineCreate(
                account_id=expense_acc.id,
                party_id=order.party_id,
                name=f"Vendor Expense - {order.order_number}",
                debit=order.amount_total,
                credit=Decimal("0.0000"),
                currency_id=order.currency_id,
                analytic_distribution={str(order.analytic_account_id): 100.0}
                if order.analytic_account_id
                else {},
            ),
            AccountMoveLineCreate(
                account_id=payable_acc.id,
                party_id=order.party_id,
                name=f"Vendor Bill Payable - {order.order_number}",
                debit=Decimal("0.0000"),
                credit=order.amount_total,
                currency_id=order.currency_id,
            ),
        ]

        bill_payload = AccountMoveCreate(
            move_type="in_invoice",
            date=order.order_date,
            ref=f"PO: {order.order_number}",
            journal_id=journal.id,
            party_id=order.party_id,
            currency_id=order.currency_id,
            payment_term_id=order.payment_term_id,
            lines=bill_lines,
        )

        bill = await AccountingService.create_move(db, bill_payload, company_id)
        order.bill_id = bill.id
        order.bill_status = "billed"
        await db.commit()

        return bill
