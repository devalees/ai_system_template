"""Enterprise Sales Order Management Service Engine."""

import uuid
from decimal import Decimal
from typing import Optional, List
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.event_bus import event_bus
from core.exceptions import NotFoundException, ValidationException
from modules.base.sequences.service import SequenceService
from modules.apps.sales.models import SaleOrder, SaleOrderLine
from modules.apps.sales.schemas import SaleOrderCreate
from modules.apps.accounting.models import Account, AccountJournal, AccountMove
from modules.apps.accounting.schemas import AccountMoveCreate, AccountMoveLineCreate
from modules.apps.accounting.service import AccountingService


class SaleService:
    """Core domain operations for Sales Quotations, Orders, and Invoicing Bridge."""

    @staticmethod
    async def create_order(
        db: AsyncSession, payload: SaleOrderCreate, company_id: uuid.UUID
    ) -> SaleOrder:
        """Create a new sales quotation with line calculations."""
        order = SaleOrder(
            company_id=company_id,
            party_id=payload.party_id,
            order_date=payload.order_date,
            currency_id=payload.currency_id,
            payment_term_id=payload.payment_term_id,
            analytic_account_id=payload.analytic_account_id,
            state="draft",
            invoice_status="to_invoice",
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
                        db, company_id, l_dto.product_id, for_operation="sale"
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
            base_amt = l_dto.quantity * unit_price
            discount_factor = Decimal(str(1.0 - (l_dto.discount_percent / 100.0)))
            subtotal = base_amt * discount_factor
            # Simple standard VAT assumption if tax specified
            tax_amt = (subtotal * Decimal("0.15")) if line_dict.get("tax_ids") else Decimal("0.0000")
            total = subtotal + tax_amt

            untaxed += subtotal
            tax_total += tax_amt

            line = SaleOrderLine(
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
        stmt = sa.select(SaleOrder).options(selectinload(SaleOrder.lines)).where(SaleOrder.id == order.id)
        return (await db.execute(stmt)).scalar_one()

    @staticmethod
    async def confirm_order(
        db: AsyncSession, order_id: uuid.UUID, company_id: uuid.UUID
    ) -> SaleOrder:
        """Confirm sales quotation into active Sales Order, stamping legal sequence."""
        stmt = (
            sa.select(SaleOrder)
            .options(selectinload(SaleOrder.lines))
            .where(
                SaleOrder.id == order_id,
                SaleOrder.company_id == company_id,
                SaleOrder.deleted_at.is_(None),
            )
        )
        res = await db.execute(stmt)
        order = res.scalar_one_or_none()
        if not order:
            raise NotFoundException("SaleOrder", order_id)

        if order.state == "sale":
            return order

        try:
            seq_num, _ = await SequenceService.get_next_number(db, company_id, "sale.order")
        except Exception:
            seq_num = f"SO/{order.order_date.year}/{uuid.uuid4().hex[:6].upper()}"
        order.order_number = seq_num
        order.state = "sale"

        await db.commit()
        await db.refresh(order)

        await event_bus.publish(
            "sales.order.confirmed",
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
    async def create_invoice(
        db: AsyncSession, order_id: uuid.UUID, company_id: uuid.UUID
    ) -> AccountMove:
        """1-Click Generation of draft Customer Invoice in Accounting from confirmed Sales Order."""
        stmt = (
            sa.select(SaleOrder)
            .options(selectinload(SaleOrder.lines))
            .where(
                SaleOrder.id == order_id,
                SaleOrder.company_id == company_id,
                SaleOrder.deleted_at.is_(None),
            )
        )
        res = await db.execute(stmt)
        order = res.scalar_one_or_none()
        if not order:
            raise NotFoundException("SaleOrder", order_id)

        if order.invoice_id:
            inv_res = await db.execute(
                sa.select(AccountMove).where(AccountMove.id == order.invoice_id)
            )
            return inv_res.scalar_one()

        # Find or use Sales Journal
        j_res = await db.execute(
            sa.select(AccountJournal).where(
                AccountJournal.company_id == company_id,
                AccountJournal.type == "sale",
                AccountJournal.deleted_at.is_(None),
            )
        )
        journal = j_res.scalar_one_or_none()
        if not journal:
            # Fallback to any journal
            any_j = await db.execute(
                sa.select(AccountJournal).where(AccountJournal.company_id == company_id)
            )
            journal = any_j.scalar_one_or_none()
            if not journal:
                raise ValidationException("No accounting journal configured for sales invoicing.")

        # Find AR Receivable Account and Income Account
        rec_res = await db.execute(
            sa.select(Account).where(
                Account.company_id == company_id,
                Account.account_type.in_(("asset_current", "asset")),
                Account.reconcilable.is_(True),
            )
        )
        receivable_acc = rec_res.scalar_one_or_none()

        inc_res = await db.execute(
            sa.select(Account).where(
                Account.company_id == company_id,
                Account.account_type.in_(("income", "revenue")),
            )
        )
        income_acc = inc_res.scalar_one_or_none()

        if not receivable_acc or not income_acc:
            # Fallback to default accounts
            all_accs = (await db.execute(sa.select(Account).where(Account.company_id == company_id))).scalars().all()
            if len(all_accs) < 2:
                raise ValidationException("Need at least 2 Chart of Accounts entries (Receivable & Income) to invoice.")
            receivable_acc = all_accs[0]
            income_acc = all_accs[1]

        # Construct balanced Invoice lines:
        # Debit: Accounts Receivable (Total amount)
        # Credit: Income / Revenue (Total amount)
        invoice_lines = [
            AccountMoveLineCreate(
                account_id=receivable_acc.id,
                party_id=order.party_id,
                name=f"Customer Invoice - {order.order_number}",
                debit=order.amount_total,
                credit=Decimal("0.0000"),
                currency_id=order.currency_id,
            ),
            AccountMoveLineCreate(
                account_id=income_acc.id,
                party_id=order.party_id,
                name=f"Sales Revenue - {order.order_number}",
                debit=Decimal("0.0000"),
                credit=order.amount_total,
                currency_id=order.currency_id,
                analytic_distribution={str(order.analytic_account_id): 100.0}
                if order.analytic_account_id
                else {},
            ),
        ]

        invoice_payload = AccountMoveCreate(
            move_type="out_invoice",
            date=order.order_date,
            ref=f"SO: {order.order_number}",
            journal_id=journal.id,
            party_id=order.party_id,
            currency_id=order.currency_id,
            payment_term_id=order.payment_term_id,
            lines=invoice_lines,
        )

        invoice = await AccountingService.create_move(db, invoice_payload, company_id)
        order.invoice_id = invoice.id
        order.invoice_status = "invoiced"
        await db.commit()

        return invoice
