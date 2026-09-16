"""Service layer for Universal Product & Item Master Data."""

import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from datetime import datetime, timezone
from modules.base.products.models import Product
from modules.base.products.schemas import ProductCreate, ProductUpdate
from modules.base.uom.models import UOMUnit
from modules.base.lookups.models import Category


class ProductService:
    """Enterprise domain service managing catalog products, defaults, and pricing linkages."""

    @staticmethod
    async def create_product(
        db: AsyncSession,
        company_id: uuid.UUID,
        data: ProductCreate,
        current_user_id: Optional[uuid.UUID] = None,
    ) -> Product:
        """Create a new catalog product with validation."""
        # 1. Check code uniqueness within company
        existing_res = await db.execute(
            select(Product).where(
                and_(
                    Product.company_id == company_id,
                    Product.code == data.code.strip(),
                    Product.deleted_at.is_(None),
                )
            )
        )
        if existing_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Product with code '{data.code}' already exists in this organization.",
            )

        # 2. Verify UoM exists
        uom_res = await db.execute(
            select(UOMUnit).where(
                and_(
                    UOMUnit.id == data.uom_id,
                    UOMUnit.company_id == company_id,
                    UOMUnit.deleted_at.is_(None),
                )
            )
        )
        if not uom_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sales/Inventory Unit of Measure '{data.uom_id}' not found.",
            )

        # 3. Verify Purchase UoM if provided
        if data.purchase_uom_id:
            p_uom_res = await db.execute(
                select(UOMUnit).where(
                    and_(
                        UOMUnit.id == data.purchase_uom_id,
                        UOMUnit.company_id == company_id,
                        UOMUnit.deleted_at.is_(None),
                    )
                )
            )
            if not p_uom_res.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Purchase Unit of Measure '{data.purchase_uom_id}' not found.",
                )

        # 4. Verify Category if provided
        if data.category_id:
            cat_res = await db.execute(
                select(Category).where(
                    and_(
                        Category.id == data.category_id,
                        Category.company_id == company_id,
                        Category.deleted_at.is_(None),
                    )
                )
            )
            if not cat_res.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Category '{data.category_id}' not found.",
                )

        # 5. Instantiate Product
        product = Product(
            company_id=company_id,
            created_by_id=current_user_id,
            code=data.code.strip(),
            name=data.name.strip(),
            description=data.description,
            product_type=data.product_type,
            uom_id=data.uom_id,
            purchase_uom_id=data.purchase_uom_id,
            sale_price=data.sale_price,
            cost_price=data.cost_price,
            sale_tax_ids=data.sale_tax_ids,
            purchase_tax_ids=data.purchase_tax_ids,
            income_account_id=data.income_account_id,
            expense_account_id=data.expense_account_id,
            category_id=data.category_id,
            is_saleable=data.is_saleable,
            is_purchasable=data.is_purchasable,
            is_active=data.is_active,
            custom_fields=data.custom_fields,
        )
        db.add(product)
        await db.flush()
        await db.refresh(product)
        return product

    @staticmethod
    async def get_product(
        db: AsyncSession,
        company_id: uuid.UUID,
        product_id: uuid.UUID,
    ) -> Product:
        """Retrieve a product by ID with eager-loaded relations."""
        stmt = (
            select(Product)
            .where(
                and_(
                    Product.id == product_id,
                    Product.company_id == company_id,
                    Product.deleted_at.is_(None),
                )
            )
            .options(
                selectinload(Product.uom),
                selectinload(Product.purchase_uom),
                selectinload(Product.category),
            )
        )
        res = await db.execute(stmt)
        product = res.scalar_one_or_none()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with ID '{product_id}' not found.",
            )
        return product

    @staticmethod
    async def update_product(
        db: AsyncSession,
        company_id: uuid.UUID,
        product_id: uuid.UUID,
        data: ProductUpdate,
        current_user_id: Optional[uuid.UUID] = None,
    ) -> Product:
        """Update an existing product partially."""
        product = await ProductService.get_product(db, company_id, product_id)

        update_dict = data.model_dump(exclude_unset=True)

        # Validate code uniqueness if updating code
        if "code" in update_dict and update_dict["code"] != product.code:
            code_val = update_dict["code"].strip()
            existing_res = await db.execute(
                select(Product).where(
                    and_(
                        Product.company_id == company_id,
                        Product.code == code_val,
                        Product.id != product_id,
                        Product.deleted_at.is_(None),
                    )
                )
            )
            if existing_res.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Product with code '{code_val}' already exists in this organization.",
                )
            product.code = code_val

        # Apply remaining fields
        for field, value in update_dict.items():
            if field != "code":
                setattr(product, field, value)

        product.updated_by_id = current_user_id
        product.updated_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(product)
        return product

    @staticmethod
    async def list_products(
        db: AsyncSession,
        company_id: uuid.UUID,
        search: Optional[str] = None,
        product_type: Optional[str] = None,
        category_id: Optional[uuid.UUID] = None,
        is_saleable: Optional[bool] = None,
        is_purchasable: Optional[bool] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Product]:
        """List products with optional search and filters."""
        stmt = (
            select(Product)
            .where(
                and_(
                    Product.company_id == company_id,
                    Product.deleted_at.is_(None),
                )
            )
            .options(
                selectinload(Product.uom),
                selectinload(Product.purchase_uom),
                selectinload(Product.category),
            )
            .order_by(Product.code.asc())
            .offset(skip)
            .limit(limit)
        )

        if search:
            search_pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                sa.or_(
                    Product.code.ilike(search_pattern),
                    Product.name.ilike(search_pattern),
                )
            )

        if product_type:
            stmt = stmt.where(Product.product_type == product_type)

        if category_id:
            stmt = stmt.where(Product.category_id == category_id)

        if is_saleable is not None:
            stmt = stmt.where(Product.is_saleable == is_saleable)

        if is_purchasable is not None:
            stmt = stmt.where(Product.is_purchasable == is_purchasable)

        if is_active is not None:
            stmt = stmt.where(Product.is_active == is_active)

        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def delete_product(
        db: AsyncSession,
        company_id: uuid.UUID,
        product_id: uuid.UUID,
        current_user_id: Optional[uuid.UUID] = None,
    ) -> bool:
        """Soft-delete a product record."""
        product = await ProductService.get_product(db, company_id, product_id)
        product.deleted_at = datetime.now(timezone.utc)
        product.deleted_by_id = current_user_id
        await db.flush()
        return True

    @staticmethod
    async def resolve_product_defaults(
        db: AsyncSession,
        company_id: uuid.UUID,
        product_id: uuid.UUID,
        for_operation: str = "sale",
    ) -> Dict[str, Any]:
        """Resolve auto-population defaults when selecting a product in order lines."""
        product = await ProductService.get_product(db, company_id, product_id)

        is_sale = (for_operation == "sale")
        target_uom_id = product.uom_id if (is_sale or not product.purchase_uom_id) else product.purchase_uom_id
        target_price = product.sale_price if is_sale else product.cost_price
        target_taxes = list(product.sale_tax_ids or []) if is_sale else list(product.purchase_tax_ids or [])
        target_account_id = product.income_account_id if is_sale else product.expense_account_id

        # Hierarchical Fallback: Walk up Category ancestors if account or taxes are missing
        curr_cat = product.category
        while curr_cat and (not target_account_id or not target_taxes):
            if not target_account_id:
                cat_acc = curr_cat.income_account_id if is_sale else curr_cat.expense_account_id
                if cat_acc:
                    target_account_id = cat_acc
            if not target_taxes:
                cat_taxes = curr_cat.sale_tax_ids if is_sale else curr_cat.purchase_tax_ids
                if cat_taxes:
                    target_taxes = [str(t) for t in cat_taxes]

            if curr_cat.parent_id and (not target_account_id or not target_taxes):
                parent_stmt = (
                    select(Category)
                    .where(
                        and_(
                            Category.id == curr_cat.parent_id,
                            Category.company_id == company_id,
                            Category.deleted_at.is_(None),
                        )
                    )
                )
                curr_cat = (await db.execute(parent_stmt)).scalar_one_or_none()
            else:
                curr_cat = None

        return {
            "product_id": str(product.id),
            "name": product.name,
            "description": product.description,
            "product_type": product.product_type,
            "uom_id": str(target_uom_id),
            "unit_price": float(target_price),
            "tax_ids": [str(t) for t in target_taxes] if target_taxes else [],
            "account_id": str(target_account_id) if target_account_id else None,
        }
