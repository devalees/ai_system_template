"""FastAPI route endpoints for Universal Product & Item Master Data."""

import uuid
from typing import List, Optional, Literal, Dict, Any
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.context import get_active_company_id
from core.exceptions import ValidationException
from modules.base.identity_rbac.models import User
from modules.base.identity_rbac.dependencies import get_current_user, require_permission

from modules.base.products.models import Product
from modules.base.products.service import ProductService
from modules.base.products.schemas import (
    ProductCreate,
    ProductUpdate,
    ProductRead,
    ProductDetailRead,
)

router = APIRouter(prefix="", tags=["Product & Catalog Master Data"])


def _resolve_company_id(user: User) -> uuid.UUID:
    """Resolve active company tenant context."""
    cid = get_active_company_id() or user.company_id
    if not cid:
        raise ValidationException("Active company context (X-Company-ID) is required.")
    return cid


def _to_detail_read(product: Product) -> ProductDetailRead:
    """Serialize model to enriched ProductDetailRead schema."""
    return ProductDetailRead(
        id=product.id,
        company_id=product.company_id,
        code=product.code,
        name=product.name,
        description=product.description,
        product_type=product.product_type,
        uom_id=product.uom_id,
        purchase_uom_id=product.purchase_uom_id,
        sale_price=product.sale_price,
        cost_price=product.cost_price,
        sale_tax_ids=product.sale_tax_ids or [],
        purchase_tax_ids=product.purchase_tax_ids or [],
        income_account_id=product.income_account_id,
        expense_account_id=product.expense_account_id,
        category_id=product.category_id,
        is_saleable=product.is_saleable,
        is_purchasable=product.is_purchasable,
        is_active=product.is_active,
        custom_fields=product.custom_fields or {},
        created_at=product.created_at,
        updated_at=product.updated_at,
        version_id=product.version_id,
        category_name=product.category.name if product.category else None,
        uom_name=product.uom.name if product.uom else None,
        uom_symbol=product.uom.symbol if product.uom else None,
        purchase_uom_name=product.purchase_uom.name if product.purchase_uom else None,
        purchase_uom_symbol=product.purchase_uom.symbol if product.purchase_uom else None,
    )


@router.post(
    "",
    response_model=ProductDetailRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Product",
    description="Registers a new catalog item, SKU, or service in the enterprise catalog.",
    dependencies=[Depends(require_permission("products.product.create"))],
)
async def create_product(
    payload: ProductCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProductDetailRead:
    company_id = _resolve_company_id(user)
    product = await ProductService.create_product(
        db, company_id, payload, current_user_id=user.id
    )
    return _to_detail_read(product)


@router.get(
    "",
    response_model=List[ProductDetailRead],
    summary="List Products",
    description="Retrieves a list of catalog products filtered by type, category, or search string.",
    dependencies=[Depends(require_permission("products.product.read"))],
)
async def list_products(
    search: Optional[str] = Query(None, description="Search across code and name"),
    product_type: Optional[str] = Query(None, description="Filter by storable, consumable, service"),
    category_id: Optional[uuid.UUID] = Query(None, description="Filter by category UUID"),
    is_saleable: Optional[bool] = Query(None, description="Filter saleable items"),
    is_purchasable: Optional[bool] = Query(None, description="Filter purchasable items"),
    is_active: Optional[bool] = Query(None, description="Filter active/inactive items"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[ProductDetailRead]:
    company_id = _resolve_company_id(user)
    products = await ProductService.list_products(
        db,
        company_id,
        search=search,
        product_type=product_type,
        category_id=category_id,
        is_saleable=is_saleable,
        is_purchasable=is_purchasable,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )
    return [_to_detail_read(p) for p in products]


@router.get(
    "/{product_id}",
    response_model=ProductDetailRead,
    summary="Get Product Detail",
    description="Retrieves full detail of a specific product including UoM and Category metadata.",
    dependencies=[Depends(require_permission("products.product.read"))],
)
async def get_product(
    product_id: uuid.UUID = Path(..., description="Target product UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProductDetailRead:
    company_id = _resolve_company_id(user)
    product = await ProductService.get_product(db, company_id, product_id)
    return _to_detail_read(product)


@router.patch(
    "/{product_id}",
    response_model=ProductDetailRead,
    summary="Update Product",
    description="Partially updates an existing product's attributes.",
    dependencies=[Depends(require_permission("products.product.update"))],
)
async def update_product(
    product_id: uuid.UUID = Path(..., description="Target product UUID"),
    payload: ProductUpdate = ...,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProductDetailRead:
    company_id = _resolve_company_id(user)
    product = await ProductService.update_product(
        db, company_id, product_id, payload, current_user_id=user.id
    )
    return _to_detail_read(product)


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Product",
    description="Soft-deletes a product from the enterprise catalog.",
    dependencies=[Depends(require_permission("products.product.delete"))],
)
async def delete_product(
    product_id: uuid.UUID = Path(..., description="Target product UUID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    company_id = _resolve_company_id(user)
    await ProductService.delete_product(
        db, company_id, product_id, current_user_id=user.id
    )


@router.get(
    "/{product_id}/defaults",
    response_model=Dict[str, Any],
    summary="Resolve Product Defaults",
    description="Calculates line auto-population defaults (UoM, unit price, taxes, account) for sales or purchases.",
    dependencies=[Depends(require_permission("products.product.read"))],
)
async def resolve_defaults(
    product_id: uuid.UUID = Path(..., description="Target product UUID"),
    for_operation: Literal["sale", "purchase"] = Query("sale", description="Context operation"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    company_id = _resolve_company_id(user)
    return await ProductService.resolve_product_defaults(
        db, company_id, product_id, for_operation=for_operation
    )
