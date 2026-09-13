"""API Routes for Master Data Lookups Management."""

import uuid
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from modules.base.identity_rbac.dependencies import get_current_user
from modules.base.identity_rbac.models import User
from modules.base.lookups.models import Country, City, Currency, UnitOfMeasure, TaxType, Tag
from modules.base.lookups.schemas import (
    CountryCreate, CountryRead,
    CityCreate, CityRead,
    CurrencyCreate, CurrencyRead,
    UnitOfMeasureCreate, UnitOfMeasureRead,
    TaxTypeCreate, TaxTypeRead,
    TagCreate, TagRead,
)
from modules.base.lookups.fixtures import seed_iso_data

router = APIRouter()


# ---------------- Seed Fixtures ----------------
@router.post("/seed", response_model=Dict[str, int], tags=["Lookups Master Data"])
async def bootstrap_company_iso_lookups(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, int]:
    """Seed standard ISO countries, currencies, UOMs, tax types, and tags for tenant company."""
    return await seed_iso_data(db, current_user.company_id)


# ---------------- Countries ----------------
@router.get("/countries", response_model=List[CountryRead], tags=["Countries"])
async def list_countries(
    search: Optional[str] = Query(None, description="Search by name or code"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[Country]:
    stmt = select(Country).where(Country.company_id == current_user.company_id)
    if search:
        stmt = stmt.where(Country.name.ilike(f"%{search}%") | Country.code.ilike(f"%{search}%"))
    return (await db.execute(stmt)).scalars().all()


@router.post("/countries", response_model=CountryRead, status_code=status.HTTP_201_CREATED, tags=["Countries"])
async def create_country(
    payload: CountryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Country:
    country = Country(
        company_id=current_user.company_id,
        name=payload.name,
        code=payload.code.upper(),
        code_alpha2=payload.code_alpha2.upper() if payload.code_alpha2 else None,
        dialing_code=payload.dialing_code,
        currency_code=payload.currency_code.upper() if payload.currency_code else None,
    )
    db.add(country)
    await db.commit()
    await db.refresh(country)
    return country


# ---------------- Cities ----------------
@router.get("/cities", response_model=List[CityRead], tags=["Cities"])
async def list_cities(
    country_id: Optional[uuid.UUID] = Query(None, description="Filter cities by country ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[City]:
    stmt = select(City).where(City.company_id == current_user.company_id)
    if country_id:
        stmt = stmt.where(City.country_id == country_id)
    return (await db.execute(stmt)).scalars().all()


@router.post("/cities", response_model=CityRead, status_code=status.HTTP_201_CREATED, tags=["Cities"])
async def create_city(
    payload: CityCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> City:
    # Verify country belongs to tenant
    country_stmt = select(Country).where(Country.id == payload.country_id, Country.company_id == current_user.company_id)
    country = (await db.execute(country_stmt)).scalar_one_or_none()
    if not country:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Country not found for this tenant.")

    city = City(
        company_id=current_user.company_id,
        name=payload.name,
        country_id=payload.country_id,
        state_or_province=payload.state_or_province,
        postal_code=payload.postal_code,
    )
    db.add(city)
    await db.commit()
    await db.refresh(city)
    return city


# ---------------- Currencies ----------------
@router.get("/currencies", response_model=List[CurrencyRead], tags=["Currencies"])
async def list_currencies(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[Currency]:
    stmt = select(Currency).where(Currency.company_id == current_user.company_id)
    return (await db.execute(stmt)).scalars().all()


@router.post("/currencies", response_model=CurrencyRead, status_code=status.HTTP_201_CREATED, tags=["Currencies"])
async def create_currency(
    payload: CurrencyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Currency:
    currency = Currency(
        company_id=current_user.company_id,
        code=payload.code.upper(),
        name=payload.name,
        symbol=payload.symbol,
        decimal_places=payload.decimal_places,
        is_base=payload.is_base,
    )
    db.add(currency)
    await db.commit()
    await db.refresh(currency)
    return currency


# ---------------- Units of Measure ----------------
@router.get("/uom", response_model=List[UnitOfMeasureRead], tags=["Units of Measure"])
async def list_units_of_measure(
    category: Optional[str] = Query(None, description="Filter by category (weight, volume, unit, length, time)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[UnitOfMeasure]:
    stmt = select(UnitOfMeasure).where(UnitOfMeasure.company_id == current_user.company_id)
    if category:
        stmt = stmt.where(UnitOfMeasure.category == category)
    return (await db.execute(stmt)).scalars().all()


@router.post("/uom", response_model=UnitOfMeasureRead, status_code=status.HTTP_201_CREATED, tags=["Units of Measure"])
async def create_unit_of_measure(
    payload: UnitOfMeasureCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnitOfMeasure:
    uom = UnitOfMeasure(
        company_id=current_user.company_id,
        name=payload.name,
        code=payload.code.upper(),
        category=payload.category,
        rounding_precision=payload.rounding_precision,
    )
    db.add(uom)
    await db.commit()
    await db.refresh(uom)
    return uom


# ---------------- Tax Types ----------------
@router.get("/tax-types", response_model=List[TaxTypeRead], tags=["Tax Types"])
async def list_tax_types(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[TaxType]:
    stmt = select(TaxType).where(TaxType.company_id == current_user.company_id)
    return (await db.execute(stmt)).scalars().all()


@router.post("/tax-types", response_model=TaxTypeRead, status_code=status.HTTP_201_CREATED, tags=["Tax Types"])
async def create_tax_type(
    payload: TaxTypeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaxType:
    tax = TaxType(
        company_id=current_user.company_id,
        name=payload.name,
        code=payload.code.upper(),
        rate=payload.rate,
        is_inclusive=payload.is_inclusive,
    )
    db.add(tax)
    await db.commit()
    await db.refresh(tax)
    return tax


# ---------------- Tags ----------------
@router.get("/tags", response_model=List[TagRead], tags=["Tags"])
async def list_tags(
    model_target: Optional[str] = Query(None, description="Filter tags by targeted model"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[Tag]:
    stmt = select(Tag).where(Tag.company_id == current_user.company_id)
    if model_target:
        stmt = stmt.where((Tag.model_target == model_target) | (Tag.model_target.is_(None)))
    return (await db.execute(stmt)).scalars().all()


@router.post("/tags", response_model=TagRead, status_code=status.HTTP_201_CREATED, tags=["Tags"])
async def create_tag(
    payload: TagCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Tag:
    tag = Tag(
        company_id=current_user.company_id,
        name=payload.name,
        color=payload.color,
        model_target=payload.model_target,
    )
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag
