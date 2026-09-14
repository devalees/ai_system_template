"""Standard ISO master data fixtures and automated seeder."""

import uuid
import logging
from typing import Dict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.base.lookups.models import Country, Currency, UnitOfMeasure, TaxType, Tag, Category

logger = logging.getLogger("sovereign.lookups.fixtures")

DEFAULT_CURRENCIES = [
    {"code": "USD", "name": "US Dollar", "symbol": "$", "decimal_places": 2, "is_base": True},
    {"code": "EUR", "name": "Euro", "symbol": "€", "decimal_places": 2, "is_base": False},
    {"code": "GBP", "name": "British Pound", "symbol": "£", "decimal_places": 2, "is_base": False},
    {"code": "SAR", "name": "Saudi Riyal", "symbol": "ر.س", "decimal_places": 2, "is_base": False},
    {"code": "AED", "name": "UAE Dirham", "symbol": "د.إ", "decimal_places": 2, "is_base": False},
    {"code": "EGP", "name": "Egyptian Pound", "symbol": "ج.م", "decimal_places": 2, "is_base": False},
    {"code": "KWD", "name": "Kuwaiti Dinar", "symbol": "د.ك", "decimal_places": 3, "is_base": False},
    {"code": "QAR", "name": "Qatari Riyal", "symbol": "ر.ق", "decimal_places": 2, "is_base": False},
]

DEFAULT_COUNTRIES = [
    {"code": "USA", "code_alpha2": "US", "name": "United States of America", "dialing_code": "+1", "currency_code": "USD"},
    {"code": "SAU", "code_alpha2": "SA", "name": "Saudi Arabia", "dialing_code": "+966", "currency_code": "SAR"},
    {"code": "ARE", "code_alpha2": "AE", "name": "United Arab Emirates", "dialing_code": "+971", "currency_code": "AED"},
    {"code": "EGY", "code_alpha2": "EG", "name": "Egypt", "dialing_code": "+20", "currency_code": "EGP"},
    {"code": "GBR", "code_alpha2": "GB", "name": "United Kingdom", "dialing_code": "+44", "currency_code": "GBP"},
    {"code": "DEU", "code_alpha2": "DE", "name": "Germany", "dialing_code": "+49", "currency_code": "EUR"},
    {"code": "FRA", "code_alpha2": "FR", "name": "France", "dialing_code": "+33", "currency_code": "EUR"},
    {"code": "KWT", "code_alpha2": "KW", "name": "Kuwait", "dialing_code": "+965", "currency_code": "KWD"},
    {"code": "QAT", "code_alpha2": "QA", "name": "Qatar", "dialing_code": "+974", "currency_code": "QAR"},
]

DEFAULT_UOMS = [
    {"code": "PCS", "name": "Pieces", "category": "unit", "rounding_precision": 1.0},
    {"code": "KG", "name": "Kilograms", "category": "weight", "rounding_precision": 0.001},
    {"code": "G", "name": "Grams", "category": "weight", "rounding_precision": 0.1},
    {"code": "LTR", "name": "Liters", "category": "volume", "rounding_precision": 0.01},
    {"code": "ML", "name": "Milliliters", "category": "volume", "rounding_precision": 1.0},
    {"code": "MTR", "name": "Meters", "category": "length", "rounding_precision": 0.01},
    {"code": "HR", "name": "Hours", "category": "time", "rounding_precision": 0.25},
]

DEFAULT_TAX_TYPES = [
    {"code": "VAT_15", "name": "Standard VAT 15%", "rate": 15.0, "is_inclusive": False},
    {"code": "VAT_14", "name": "Standard VAT 14%", "rate": 14.0, "is_inclusive": False},
    {"code": "VAT_5", "name": "Reduced VAT 5%", "rate": 5.0, "is_inclusive": False},
    {"code": "ZERO_TAX", "name": "Zero-Rated 0%", "rate": 0.0, "is_inclusive": False},
    {"code": "EXEMPT", "name": "Tax Exempt", "rate": 0.0, "is_inclusive": False},
]

DEFAULT_TAGS = [
    {"name": "VIP", "color": "#f59e0b", "model_target": None},
    {"name": "Urgent", "color": "#ef4444", "model_target": None},
    {"name": "Internal", "color": "#6b7280", "model_target": None},
    {"name": "Approved", "color": "#10b981", "model_target": None},
]

DEFAULT_CATEGORIES = [
    {
        "name": "Documents & Attachments",
        "code": "DOC_ROOT",
        "res_model": "document",
        "color": "#3b82f6",
        "icon": "folder",
        "sequence": 10,
        "subcategories": [
            {"name": "Contracts & Agreements", "code": "DOC_LEGAL", "color": "#10b981", "icon": "file-text", "sequence": 10},
            {"name": "Financial Invoices & Receipts", "code": "DOC_FINANCE", "color": "#f59e0b", "icon": "receipt", "sequence": 20},
            {"name": "HR & Employee Records", "code": "DOC_HR", "color": "#8b5cf6", "icon": "users", "sequence": 30},
        ],
    },
    {
        "name": "Email Communication",
        "code": "MAIL_ROOT",
        "res_model": "mail_template",
        "color": "#6366f1",
        "icon": "mail",
        "sequence": 20,
        "subcategories": [
            {"name": "Transactional & System Notices", "code": "MAIL_TXN", "color": "#06b6d4", "icon": "send", "sequence": 10},
            {"name": "Marketing & Campaigns", "code": "MAIL_MKT", "color": "#ec4899", "icon": "megaphone", "sequence": 20},
        ],
    },
]


async def seed_iso_data(db: AsyncSession, company_id: uuid.UUID) -> Dict[str, int]:
    """Seed standard ISO and operational master data lookups for a company."""
    seeded_counts = {
        "currencies": 0,
        "countries": 0,
        "uom": 0,
        "tax_types": 0,
        "tags": 0,
    }

    # 1. Currencies
    for item in DEFAULT_CURRENCIES:
        stmt = select(Currency).where(Currency.company_id == company_id, Currency.code == item["code"])
        exists = (await db.execute(stmt)).scalar_one_or_none()
        if not exists:
            db.add(Currency(company_id=company_id, **item))
            seeded_counts["currencies"] += 1

    # 2. Countries
    for item in DEFAULT_COUNTRIES:
        stmt = select(Country).where(Country.company_id == company_id, Country.code == item["code"])
        exists = (await db.execute(stmt)).scalar_one_or_none()
        if not exists:
            db.add(Country(company_id=company_id, **item))
            seeded_counts["countries"] += 1

    # 3. Units of Measure
    for item in DEFAULT_UOMS:
        stmt = select(UnitOfMeasure).where(UnitOfMeasure.company_id == company_id, UnitOfMeasure.code == item["code"])
        exists = (await db.execute(stmt)).scalar_one_or_none()
        if not exists:
            db.add(UnitOfMeasure(company_id=company_id, **item))
            seeded_counts["uom"] += 1

    # 4. Tax Types
    for item in DEFAULT_TAX_TYPES:
        stmt = select(TaxType).where(TaxType.company_id == company_id, TaxType.code == item["code"])
        exists = (await db.execute(stmt)).scalar_one_or_none()
        if not exists:
            db.add(TaxType(company_id=company_id, **item))
            seeded_counts["tax_types"] += 1

    # 5. Tags
    for item in DEFAULT_TAGS:
        stmt = select(Tag).where(
            Tag.company_id == company_id,
            Tag.name == item["name"],
            Tag.model_target == item["model_target"],
        )
        exists = (await db.execute(stmt)).scalar_one_or_none()
        if not exists:
            db.add(Tag(company_id=company_id, **item))
            seeded_counts["tags"] += 1

    # 6. Categories (Hierarchical Trees)
    seeded_counts["categories"] = 0
    for cat_data in DEFAULT_CATEGORIES:
        stmt = select(Category).where(
            Category.company_id == company_id,
            Category.res_model == cat_data["res_model"],
            Category.code == cat_data["code"],
            Category.deleted_at.is_(None),
        )
        root_cat = (await db.execute(stmt)).scalar_one_or_none()
        if not root_cat:
            root_cat = Category(
                company_id=company_id,
                name=cat_data["name"],
                code=cat_data["code"],
                res_model=cat_data["res_model"],
                color=cat_data.get("color", "#3b82f6"),
                icon=cat_data.get("icon"),
                sequence=cat_data.get("sequence", 10),
            )
            db.add(root_cat)
            await db.flush()
            seeded_counts["categories"] += 1

        for sub_data in cat_data.get("subcategories", []):
            stmt_sub = select(Category).where(
                Category.company_id == company_id,
                Category.res_model == cat_data["res_model"],
                Category.code == sub_data["code"],
                Category.deleted_at.is_(None),
            )
            sub_cat = (await db.execute(stmt_sub)).scalar_one_or_none()
            if not sub_cat:
                sub_cat = Category(
                    company_id=company_id,
                    name=sub_data["name"],
                    code=sub_data["code"],
                    res_model=cat_data["res_model"],
                    parent_id=root_cat.id,
                    color=sub_data.get("color", "#3b82f6"),
                    icon=sub_data.get("icon"),
                    sequence=sub_data.get("sequence", 10),
                )
                db.add(sub_cat)
                seeded_counts["categories"] += 1

    await db.commit()
    logger.info(f"Seeded ISO lookups for company {company_id}: {seeded_counts}")
    return seeded_counts
