"""Business logic and tree traversal service for Hierarchical Category Taxonomy."""

import uuid
from typing import Optional, List, Dict, Set
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import PlatformException, EntityNotFoundException
from modules.base.lookups.models import Category
from modules.base.lookups.schemas import (
    CategoryCreate,
    CategoryUpdate,
    CategoryRead,
    CategoryTreeRead,
)


class CategoryService:
    """Service managing hierarchical categorization, cycle prevention, and tree serialization."""

    @classmethod
    async def get_category(
        cls,
        db: AsyncSession,
        category_id: uuid.UUID,
        company_id: uuid.UUID,
    ) -> Optional[Category]:
        """Fetch a single category scoped to tenant company."""
        stmt = select(Category).where(
            and_(
                Category.id == category_id,
                Category.company_id == company_id,
                Category.deleted_at.is_(None),
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def create_category(
        cls,
        db: AsyncSession,
        payload: CategoryCreate,
        company_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> Category:
        """Create a new root or sub-category with parent verification."""
        # 1. Verify parent if provided
        if payload.parent_id:
            parent = await cls.get_category(db, payload.parent_id, company_id)
            if not parent:
                raise EntityNotFoundException("Parent Category", payload.parent_id)

        # 2. Check code uniqueness within tenant and res_model scope
        stmt_check = select(Category).where(
            and_(
                Category.company_id == company_id,
                Category.res_model == payload.res_model,
                Category.code == payload.code,
                Category.deleted_at.is_(None),
            )
        )
        existing = await db.execute(stmt_check)
        if existing.scalar_one_or_none():
            raise PlatformException(
                code="DUPLICATE_CATEGORY_CODE",
                message=f"Category with code '{payload.code}' already exists for scope '{payload.res_model}'.",
                resolution_hint="Provide a distinct category code or use a different scope.",
                status_code=400,
            )

        # 3. Process accounting defaults into custom_fields
        cf = dict(payload.custom_fields or {})
        if payload.income_account_id is not None:
            cf["income_account_id"] = str(payload.income_account_id)
        if payload.expense_account_id is not None:
            cf["expense_account_id"] = str(payload.expense_account_id)
        if payload.sale_tax_ids is not None:
            cf["sale_tax_ids"] = [str(x) for x in payload.sale_tax_ids]
        if payload.purchase_tax_ids is not None:
            cf["purchase_tax_ids"] = [str(x) for x in payload.purchase_tax_ids]

        # 4. Instantiate model
        category = Category(
            company_id=company_id,
            name=payload.name,
            code=payload.code,
            res_model=payload.res_model,
            parent_id=payload.parent_id,
            description=payload.description,
            color=payload.color,
            icon=payload.icon,
            sequence=payload.sequence,
            created_by_id=user_id,
            custom_fields=cf,
        )
        db.add(category)
        await db.commit()
        await db.refresh(category)
        return category

    @classmethod
    async def update_category(
        cls,
        db: AsyncSession,
        category_id: uuid.UUID,
        payload: CategoryUpdate,
        company_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> Category:
        """Update category attributes and re-parent with strict circular reference prevention."""
        category = await cls.get_category(db, category_id, company_id)
        if not category:
            raise EntityNotFoundException("Category", category_id)

        update_data = payload.model_dump(exclude_unset=True)

        # Cycle prevention on parent_id change
        if "parent_id" in update_data and update_data["parent_id"] is not None:
            new_parent_id = update_data["parent_id"]
            if new_parent_id == category_id:
                raise PlatformException(
                    code="CIRCULAR_CATEGORY_DEPENDENCY",
                    message="A category cannot be its own parent.",
                    resolution_hint="Select a different parent category or set parent_id to null for a root category.",
                    status_code=400,
                )

            # Ensure new parent exists
            parent = await cls.get_category(db, new_parent_id, company_id)
            if not parent:
                raise EntityNotFoundException("Parent Category", new_parent_id)

            # Check if new_parent_id is any descendant of category_id
            descendant_ids = await cls._get_all_descendant_ids(db, category_id, company_id)
            if new_parent_id in descendant_ids:
                raise PlatformException(
                    code="CIRCULAR_CATEGORY_DEPENDENCY",
                    message="Cannot assign a descendant category as a parent (circular tree reference).",
                    resolution_hint="Choose an ancestor or independent category as parent.",
                    status_code=400,
                )

        # Update standard model attributes
        for field, val in update_data.items():
            if field in ("income_account_id", "expense_account_id", "sale_tax_ids", "purchase_tax_ids", "custom_fields"):
                continue
            setattr(category, field, val)

        # Update custom fields and accounting defaults
        cf = dict(category.custom_fields or {})
        if "custom_fields" in update_data and update_data["custom_fields"] is not None:
            cf.update(update_data["custom_fields"])
        if "income_account_id" in update_data:
            val = update_data["income_account_id"]
            cf["income_account_id"] = str(val) if val else None
        if "expense_account_id" in update_data:
            val = update_data["expense_account_id"]
            cf["expense_account_id"] = str(val) if val else None
        if "sale_tax_ids" in update_data:
            val = update_data["sale_tax_ids"]
            cf["sale_tax_ids"] = [str(x) for x in val] if val else []
        if "purchase_tax_ids" in update_data:
            val = update_data["purchase_tax_ids"]
            cf["purchase_tax_ids"] = [str(x) for x in val] if val else []
        category.custom_fields = cf

        category.updated_by_id = user_id
        await db.commit()
        await db.refresh(category)
        return category

    @classmethod
    async def delete_category(
        cls,
        db: AsyncSession,
        category_id: uuid.UUID,
        company_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> bool:
        """Soft delete category and cascade soft delete to descendants."""
        category = await cls.get_category(db, category_id, company_id)
        if not category:
            raise EntityNotFoundException("Category", category_id)

        descendant_ids = await cls._get_all_descendant_ids(db, category_id, company_id)
        all_to_delete = [category_id] + list(descendant_ids)

        stmt = select(Category).where(
            and_(
                Category.id.in_(all_to_delete),
                Category.company_id == company_id,
            )
        )
        records = (await db.execute(stmt)).scalars().all()
        for r in records:
            r.soft_delete(user_id)

        await db.commit()
        return True

    @classmethod
    async def _get_all_descendant_ids(
        cls,
        db: AsyncSession,
        root_id: uuid.UUID,
        company_id: uuid.UUID,
    ) -> Set[uuid.UUID]:
        """Recursively collect all descendant UUIDs for a given category."""
        stmt = select(Category).where(
            and_(
                Category.company_id == company_id,
                Category.deleted_at.is_(None),
            )
        )
        all_records = (await db.execute(stmt)).scalars().all()

        # Build parent -> children map
        children_map: Dict[uuid.UUID, List[uuid.UUID]] = {}
        for cat in all_records:
            if cat.parent_id:
                children_map.setdefault(cat.parent_id, []).append(cat.id)

        descendants: Set[uuid.UUID] = set()
        queue = [root_id]
        while queue:
            curr = queue.pop(0)
            child_ids = children_map.get(curr, [])
            for child_id in child_ids:
                if child_id not in descendants:
                    descendants.add(child_id)
                    queue.append(child_id)

        return descendants

    @classmethod
    async def list_categories(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        res_model: Optional[str] = None,
        parent_id: Optional[uuid.UUID] = None,
        root_only: bool = False,
        search: Optional[str] = None,
    ) -> List[CategoryRead]:
        """List categories with enriched path, parent name, and children count."""
        stmt = select(Category).where(
            and_(
                Category.company_id == company_id,
                Category.deleted_at.is_(None),
            )
        )
        if res_model:
            stmt = stmt.where(Category.res_model == res_model)
        if root_only:
            stmt = stmt.where(Category.parent_id.is_(None))
        elif parent_id is not None:
            stmt = stmt.where(Category.parent_id == parent_id)
        if search:
            stmt = stmt.where(Category.name.ilike(f"%{search}%"))

        stmt = stmt.order_by(Category.sequence.asc(), Category.name.asc())
        results = (await db.execute(stmt)).scalars().all()

        # Fetch all company categories to compute breadcrumbs and counts
        stmt_all = select(Category).where(
            and_(
                Category.company_id == company_id,
                Category.deleted_at.is_(None),
            )
        )
        all_company_cats = (await db.execute(stmt_all)).scalars().all()
        cat_map = {c.id: c for c in all_company_cats}

        # Calculate children counts
        counts: Dict[uuid.UUID, int] = {}
        for c in all_company_cats:
            if c.parent_id:
                counts[c.parent_id] = counts.get(c.parent_id, 0) + 1

        output: List[CategoryRead] = []
        for cat in results:
            full_path = cls._compute_full_path(cat, cat_map)
            parent_name = cat_map[cat.parent_id].name if cat.parent_id and cat.parent_id in cat_map else None
            output.append(
                CategoryRead(
                    id=cat.id,
                    company_id=cat.company_id,
                    name=cat.name,
                    code=cat.code,
                    res_model=cat.res_model,
                    parent_id=cat.parent_id,
                    parent_name=parent_name,
                    description=cat.description,
                    color=cat.color,
                    icon=cat.icon,
                    sequence=cat.sequence,
                    is_active=cat.is_active,
                    full_path=full_path,
                    children_count=counts.get(cat.id, 0),
                    income_account_id=cat.income_account_id,
                    expense_account_id=cat.expense_account_id,
                    sale_tax_ids=cat.sale_tax_ids,
                    purchase_tax_ids=cat.purchase_tax_ids,
                    custom_fields=cat.custom_fields or {},
                )
            )
        return output

    @classmethod
    async def get_category_tree(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        res_model: Optional[str] = None,
    ) -> List[CategoryTreeRead]:
        """Construct full recursive hierarchical category tree."""
        stmt = select(Category).where(
            and_(
                Category.company_id == company_id,
                Category.deleted_at.is_(None),
            )
        )
        if res_model:
            stmt = stmt.where(Category.res_model == res_model)

        stmt = stmt.order_by(Category.sequence.asc(), Category.name.asc())
        all_records = (await db.execute(stmt)).scalars().all()

        cat_map = {c.id: c for c in all_records}

        # Compute children count
        counts: Dict[uuid.UUID, int] = {}
        for c in all_records:
            if c.parent_id:
                counts[c.parent_id] = counts.get(c.parent_id, 0) + 1

        # Build node objects
        nodes: Dict[uuid.UUID, CategoryTreeRead] = {}
        for c in all_records:
            parent_name = cat_map[c.parent_id].name if c.parent_id and c.parent_id in cat_map else None
            nodes[c.id] = CategoryTreeRead(
                id=c.id,
                company_id=c.company_id,
                name=c.name,
                code=c.code,
                res_model=c.res_model,
                parent_id=c.parent_id,
                parent_name=parent_name,
                description=c.description,
                color=c.color,
                icon=c.icon,
                sequence=c.sequence,
                is_active=c.is_active,
                full_path=cls._compute_full_path(c, cat_map),
                children_count=counts.get(c.id, 0),
                children=[],
            )

        # Assemble tree
        root_nodes: List[CategoryTreeRead] = []
        for c in all_records:
            node = nodes[c.id]
            if c.parent_id and c.parent_id in nodes:
                nodes[c.parent_id].children.append(node)
            else:
                root_nodes.append(node)

        return root_nodes

    @classmethod
    def _compute_full_path(cls, category: Category, cat_map: Dict[uuid.UUID, Category]) -> str:
        """Compute human-readable breadcrumb path (e.g. 'Contracts / Vendor / NDAs')."""
        path_names = [category.name]
        visited = {category.id}
        curr = category
        while curr.parent_id and curr.parent_id in cat_map:
            if curr.parent_id in visited:
                break
            visited.add(curr.parent_id)
            curr = cat_map[curr.parent_id]
            path_names.insert(0, curr.name)
        return " / ".join(path_names)
