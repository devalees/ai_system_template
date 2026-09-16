"""API Routes for Master Data Lookups Management."""

import uuid
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from modules.base.identity_rbac.dependencies import get_current_user
from modules.base.identity_rbac.models import User
from modules.base.lookups.models import Country, City, Currency, UnitOfMeasure, TaxType, Tag, Category
from modules.base.lookups.schemas import (
    CountryCreate, CountryUpdate, CountryRead,
    CityCreate, CityUpdate, CityRead,
    CurrencyCreate, CurrencyUpdate, CurrencyRead,
    UnitOfMeasureCreate, UnitOfMeasureUpdate, UnitOfMeasureRead,
    TaxTypeCreate, TaxTypeUpdate, TaxTypeRead,
    TagCreate, TagUpdate, TagRead,
    CategoryCreate, CategoryUpdate, CategoryRead, CategoryTreeRead,
)
from modules.base.lookups.service import CategoryService
from modules.base.lookups.fixtures import seed_iso_data

router = APIRouter()


# ---------------- Seed Fixtures ----------------
@router.post("/seed", response_model=Dict[str, int])
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


@router.get("/countries/{id}", response_model=CountryRead, tags=["Countries"])
async def get_country(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Country:
    stmt = select(Country).where(Country.id == id, Country.company_id == current_user.company_id)
    country = (await db.execute(stmt)).scalar_one_or_none()
    if not country:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Country not found")
    return country


@router.patch("/countries/{id}", response_model=CountryRead, tags=["Countries"])
async def update_country(
    id: uuid.UUID,
    payload: CountryUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Country:
    stmt = select(Country).where(Country.id == id, Country.company_id == current_user.company_id)
    country = (await db.execute(stmt)).scalar_one_or_none()
    if not country:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Country not found")
    data = payload.model_dump(exclude_unset=True)
    if "code" in data and data["code"]:
        data["code"] = data["code"].upper()
    if "code_alpha2" in data and data["code_alpha2"]:
        data["code_alpha2"] = data["code_alpha2"].upper()
    if "currency_code" in data and data["currency_code"]:
        data["currency_code"] = data["currency_code"].upper()
    for field, val in data.items():
        setattr(country, field, val)
    country.updated_by_id = current_user.id
    await db.commit()
    await db.refresh(country)
    return country


@router.delete("/countries/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Countries"])
async def delete_country(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Country).where(Country.id == id, Country.company_id == current_user.company_id)
    country = (await db.execute(stmt)).scalar_one_or_none()
    if not country:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Country not found")
    country.soft_delete(current_user.id)
    await db.commit()
    return None


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


@router.get("/cities/{id}", response_model=CityRead, tags=["Cities"])
async def get_city(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> City:
    stmt = select(City).where(City.id == id, City.company_id == current_user.company_id)
    city = (await db.execute(stmt)).scalar_one_or_none()
    if not city:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="City not found")
    return city


@router.patch("/cities/{id}", response_model=CityRead, tags=["Cities"])
async def update_city(
    id: uuid.UUID,
    payload: CityUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> City:
    stmt = select(City).where(City.id == id, City.company_id == current_user.company_id)
    city = (await db.execute(stmt)).scalar_one_or_none()
    if not city:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="City not found")
    data = payload.model_dump(exclude_unset=True)
    if "country_id" in data and data["country_id"]:
        country_stmt = select(Country).where(Country.id == data["country_id"], Country.company_id == current_user.company_id)
        if not (await db.execute(country_stmt)).scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Country not found for this tenant.")
    for field, val in data.items():
        setattr(city, field, val)
    city.updated_by_id = current_user.id
    await db.commit()
    await db.refresh(city)
    return city


@router.delete("/cities/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Cities"])
async def delete_city(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(City).where(City.id == id, City.company_id == current_user.company_id)
    city = (await db.execute(stmt)).scalar_one_or_none()
    if not city:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="City not found")
    city.soft_delete(current_user.id)
    await db.commit()
    return None


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


@router.get("/currencies/{id}", response_model=CurrencyRead, tags=["Currencies"])
async def get_currency(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Currency:
    stmt = select(Currency).where(Currency.id == id, Currency.company_id == current_user.company_id)
    currency = (await db.execute(stmt)).scalar_one_or_none()
    if not currency:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Currency not found")
    return currency


@router.patch("/currencies/{id}", response_model=CurrencyRead, tags=["Currencies"])
async def update_currency(
    id: uuid.UUID,
    payload: CurrencyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Currency:
    stmt = select(Currency).where(Currency.id == id, Currency.company_id == current_user.company_id)
    currency = (await db.execute(stmt)).scalar_one_or_none()
    if not currency:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Currency not found")
    data = payload.model_dump(exclude_unset=True)
    if "code" in data and data["code"]:
        data["code"] = data["code"].upper()
    for field, val in data.items():
        setattr(currency, field, val)
    currency.updated_by_id = current_user.id
    await db.commit()
    await db.refresh(currency)
    return currency


@router.delete("/currencies/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Currencies"])
async def delete_currency(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Currency).where(Currency.id == id, Currency.company_id == current_user.company_id)
    currency = (await db.execute(stmt)).scalar_one_or_none()
    if not currency:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Currency not found")
    currency.soft_delete(current_user.id)
    await db.commit()
    return None


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


@router.get("/uom/{id}", response_model=UnitOfMeasureRead, tags=["Units of Measure"])
async def get_unit_of_measure(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnitOfMeasure:
    stmt = select(UnitOfMeasure).where(UnitOfMeasure.id == id, UnitOfMeasure.company_id == current_user.company_id)
    uom = (await db.execute(stmt)).scalar_one_or_none()
    if not uom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit of Measure not found")
    return uom


@router.patch("/uom/{id}", response_model=UnitOfMeasureRead, tags=["Units of Measure"])
async def update_unit_of_measure(
    id: uuid.UUID,
    payload: UnitOfMeasureUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnitOfMeasure:
    stmt = select(UnitOfMeasure).where(UnitOfMeasure.id == id, UnitOfMeasure.company_id == current_user.company_id)
    uom = (await db.execute(stmt)).scalar_one_or_none()
    if not uom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit of Measure not found")
    data = payload.model_dump(exclude_unset=True)
    for field, val in data.items():
        setattr(uom, field, val)
    uom.updated_by_id = current_user.id
    await db.commit()
    await db.refresh(uom)
    return uom


@router.delete("/uom/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Units of Measure"])
async def delete_unit_of_measure(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(UnitOfMeasure).where(UnitOfMeasure.id == id, UnitOfMeasure.company_id == current_user.company_id)
    uom = (await db.execute(stmt)).scalar_one_or_none()
    if not uom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit of Measure not found")
    uom.soft_delete(current_user.id)
    await db.commit()
    return None


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


@router.get("/tax-types/{id}", response_model=TaxTypeRead, tags=["Tax Types"])
async def get_tax_type(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaxType:
    stmt = select(TaxType).where(TaxType.id == id, TaxType.company_id == current_user.company_id)
    tax = (await db.execute(stmt)).scalar_one_or_none()
    if not tax:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tax Type not found")
    return tax


@router.patch("/tax-types/{id}", response_model=TaxTypeRead, tags=["Tax Types"])
async def update_tax_type(
    id: uuid.UUID,
    payload: TaxTypeUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaxType:
    stmt = select(TaxType).where(TaxType.id == id, TaxType.company_id == current_user.company_id)
    tax = (await db.execute(stmt)).scalar_one_or_none()
    if not tax:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tax Type not found")
    data = payload.model_dump(exclude_unset=True)
    for field, val in data.items():
        setattr(tax, field, val)
    tax.updated_by_id = current_user.id
    await db.commit()
    await db.refresh(tax)
    return tax


@router.delete("/tax-types/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Tax Types"])
async def delete_tax_type(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(TaxType).where(TaxType.id == id, TaxType.company_id == current_user.company_id)
    tax = (await db.execute(stmt)).scalar_one_or_none()
    if not tax:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tax Type not found")
    tax.soft_delete(current_user.id)
    await db.commit()
    return None


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


@router.get("/tags/{id}", response_model=TagRead, tags=["Tags"])
async def get_tag(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Tag:
    stmt = select(Tag).where(Tag.id == id, Tag.company_id == current_user.company_id)
    tag = (await db.execute(stmt)).scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    return tag


@router.patch("/tags/{id}", response_model=TagRead, tags=["Tags"])
async def update_tag(
    id: uuid.UUID,
    payload: TagUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Tag:
    stmt = select(Tag).where(Tag.id == id, Tag.company_id == current_user.company_id)
    tag = (await db.execute(stmt)).scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    data = payload.model_dump(exclude_unset=True)
    for field, val in data.items():
        setattr(tag, field, val)
    tag.updated_by_id = current_user.id
    await db.commit()
    await db.refresh(tag)
    return tag


@router.delete("/tags/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Tags"])
async def delete_tag(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Tag).where(Tag.id == id, Tag.company_id == current_user.company_id)
    tag = (await db.execute(stmt)).scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    tag.soft_delete(current_user.id)
    await db.commit()
    return None


# ---------------- Categories (Hierarchical Taxonomy) ----------------
@router.get("/categories", response_model=List[CategoryRead], tags=["Categories"])
async def list_categories(
    res_model: Optional[str] = Query(None, description="Filter by target model scope (e.g. document, mail_template)"),
    parent_id: Optional[uuid.UUID] = Query(None, description="Filter by parent category ID"),
    root_only: bool = Query(False, description="Return only top-level root categories without parents"),
    search: Optional[str] = Query(None, description="Search categories by name"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[CategoryRead]:
    """List categories for current tenant with breadcrumb paths and children counts."""
    return await CategoryService.list_categories(
        db=db,
        company_id=current_user.company_id,
        res_model=res_model,
        parent_id=parent_id,
        root_only=root_only,
        search=search,
    )


@router.get("/categories/tree", response_model=List[CategoryTreeRead], tags=["Categories"])
async def get_category_tree(
    res_model: Optional[str] = Query(None, description="Filter tree by model scope"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[CategoryTreeRead]:
    """Retrieve full nested hierarchical tree of categories for UI navigation and trees."""
    return await CategoryService.get_category_tree(
        db=db,
        company_id=current_user.company_id,
        res_model=res_model,
    )


@router.post("/categories", response_model=CategoryRead, status_code=status.HTTP_201_CREATED, tags=["Categories"])
async def create_category(
    payload: CategoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CategoryRead:
    """Create a new root or sub-category (with optional parent_id for sub-classification)."""
    cat = await CategoryService.create_category(
        db=db,
        payload=payload,
        company_id=current_user.company_id,
        user_id=current_user.id,
    )
    cats = await CategoryService.list_categories(
        db=db,
        company_id=current_user.company_id,
        parent_id=cat.parent_id,
        search=cat.name,
    )
    for c in cats:
        if c.id == cat.id:
            return c
    return CategoryRead(
        id=cat.id,
        company_id=cat.company_id,
        name=cat.name,
        code=cat.code,
        res_model=cat.res_model,
        parent_id=cat.parent_id,
        description=cat.description,
        color=cat.color,
        icon=cat.icon,
        sequence=cat.sequence,
        is_active=cat.is_active,
        full_path=cat.name,
        children_count=0,
        income_account_id=cat.income_account_id,
        expense_account_id=cat.expense_account_id,
        sale_tax_ids=cat.sale_tax_ids,
        purchase_tax_ids=cat.purchase_tax_ids,
        custom_fields=cat.custom_fields or {},
    )


@router.get("/categories/{id}", response_model=CategoryRead, tags=["Categories"])
async def get_category(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CategoryRead:
    """Get single category details with full breadcrumb path."""
    cat = await CategoryService.get_category(db, id, current_user.company_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    cats = await CategoryService.list_categories(
        db=db,
        company_id=current_user.company_id,
        search=cat.name,
    )
    for c in cats:
        if c.id == cat.id:
            return c
    return CategoryRead(
        id=cat.id,
        company_id=cat.company_id,
        name=cat.name,
        code=cat.code,
        res_model=cat.res_model,
        parent_id=cat.parent_id,
        description=cat.description,
        color=cat.color,
        icon=cat.icon,
        sequence=cat.sequence,
        is_active=cat.is_active,
        full_path=cat.name,
        children_count=0,
        income_account_id=cat.income_account_id,
        expense_account_id=cat.expense_account_id,
        sale_tax_ids=cat.sale_tax_ids,
        purchase_tax_ids=cat.purchase_tax_ids,
        custom_fields=cat.custom_fields or {},
    )


@router.patch("/categories/{id}", response_model=CategoryRead, tags=["Categories"])
async def update_category(
    id: uuid.UUID,
    payload: CategoryUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CategoryRead:
    """Update category attributes or re-parent in tree with circular reference protection."""
    cat = await CategoryService.update_category(
        db=db,
        category_id=id,
        payload=payload,
        company_id=current_user.company_id,
        user_id=current_user.id,
    )
    cats = await CategoryService.list_categories(
        db=db,
        company_id=current_user.company_id,
        search=cat.name,
    )
    for c in cats:
        if c.id == cat.id:
            return c
    return CategoryRead(
        id=cat.id,
        company_id=cat.company_id,
        name=cat.name,
        code=cat.code,
        res_model=cat.res_model,
        parent_id=cat.parent_id,
        description=cat.description,
        color=cat.color,
        icon=cat.icon,
        sequence=cat.sequence,
        is_active=cat.is_active,
        full_path=cat.name,
        children_count=0,
        income_account_id=cat.income_account_id,
        expense_account_id=cat.expense_account_id,
        sale_tax_ids=cat.sale_tax_ids,
        purchase_tax_ids=cat.purchase_tax_ids,
        custom_fields=cat.custom_fields or {},
    )


@router.delete("/categories/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Categories"])
async def delete_category(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete category and cascade soft delete to descendants."""
    await CategoryService.delete_category(
        db=db,
        category_id=id,
        company_id=current_user.company_id,
        user_id=current_user.id,
    )
    return None
