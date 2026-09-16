"""Standard enterprise sequence fixtures for initial seeding and bootstrapping."""

import uuid
from typing import Dict, Any, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.base.sequences.models import Sequence


STANDARD_SEQUENCES: List[Dict[str, Any]] = [
    {
        "name": "Customer Invoices",
        "code": "account.invoice",
        "prefix": "INV/%(year)s/%(month)s/",
        "suffix": "",
        "padding": 5,
        "current_number": 0,
        "step": 1,
        "reset_period": "yearly",
    },
    {
        "name": "Customer Payments",
        "code": "account.payment",
        "prefix": "PAY/%(year)s/",
        "suffix": "",
        "padding": 5,
        "current_number": 0,
        "step": 1,
        "reset_period": "yearly",
    },
    {
        "name": "Sales Orders",
        "code": "sale.order",
        "prefix": "SO/%(year)s/%(month)s/",
        "suffix": "",
        "padding": 5,
        "current_number": 0,
        "step": 1,
        "reset_period": "yearly",
    },
    {
        "name": "Purchase Orders",
        "code": "purchase.order",
        "prefix": "PO/%(year)s/",
        "suffix": "",
        "padding": 5,
        "current_number": 0,
        "step": 1,
        "reset_period": "yearly",
    },
    {
        "name": "Customer Code Series",
        "code": "partner.customer",
        "prefix": "CUST-",
        "suffix": "",
        "padding": 5,
        "current_number": 0,
        "step": 1,
        "reset_period": "never",
    },
    {
        "name": "Vendor Code Series",
        "code": "partner.vendor",
        "prefix": "VEND-",
        "suffix": "",
        "padding": 5,
        "current_number": 0,
        "step": 1,
        "reset_period": "never",
    },
    {
        "name": "Commercial Contracts",
        "code": "contract",
        "prefix": "CON/%(year)s/",
        "suffix": "",
        "padding": 4,
        "current_number": 0,
        "step": 1,
        "reset_period": "yearly",
    },
    {
        "name": "General Journal Entries",
        "code": "general.journal",
        "prefix": "JV/%(year)s/%(month)s/",
        "suffix": "",
        "padding": 5,
        "current_number": 0,
        "step": 1,
        "reset_period": "yearly",
    },
]


async def seed_standard_sequences(db: AsyncSession, company_id: uuid.UUID) -> int:
    """Idempotently seed standard business sequences for a tenant company."""
    seeded_count = 0

    for fixture in STANDARD_SEQUENCES:
        stmt = select(Sequence).where(
            Sequence.company_id == company_id,
            Sequence.code == fixture["code"],
            Sequence.deleted_at.is_(None),
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()

        if not existing:
            seq = Sequence(
                company_id=company_id,
                name=fixture["name"],
                code=fixture["code"],
                prefix=fixture["prefix"],
                suffix=fixture["suffix"],
                padding=fixture["padding"],
                current_number=fixture["current_number"],
                step=fixture["step"],
                reset_period=fixture["reset_period"],
                is_active=True,
            )
            db.add(seq)
            seeded_count += 1

    if seeded_count > 0:
        await db.flush()

    return seeded_count
