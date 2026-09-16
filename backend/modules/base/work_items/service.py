"""Business logic and DAG cycle detection engine for Universal Work Items, Tasks & Dependencies."""

import uuid
from typing import Optional, List, Set
from collections import deque
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import EntityNotFoundException, ValidationException
from modules.base.work_items.models import WorkItemStage, WorkItem, WorkItemDependency
from modules.base.work_items.schemas import (
    WorkItemStageCreate,
    WorkItemStageUpdate,
    WorkItemCreate,
    WorkItemUpdate,
    WorkItemDependencyCreate,
    WorkItemTreeNode,
)


class WorkItemService:
    """Service managing work items, sub-task hierarchies, dependency DAGs, and Kanban pipelines."""

    # -----------------------------------------------------------------------
    # Stage CRUD
    # -----------------------------------------------------------------------

    @classmethod
    async def create_stage(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        payload: WorkItemStageCreate,
    ) -> WorkItemStage:
        """Create new workflow pipeline stage."""
        stage = WorkItemStage(
            company_id=company_id,
            name=payload.name,
            code=payload.code,
            sequence=payload.sequence,
            is_closed=payload.is_closed,
            color=payload.color,
            description=payload.description,
        )
        db.add(stage)
        await db.commit()
        await db.refresh(stage)
        return stage

    @classmethod
    async def get_stage(
        cls,
        db: AsyncSession,
        stage_id: uuid.UUID,
    ) -> WorkItemStage:
        """Fetch pipeline stage by ID."""
        stmt = select(WorkItemStage).where(WorkItemStage.id == stage_id)
        result = await db.execute(stmt)
        stage = result.scalar_one_or_none()
        if not stage:
            raise EntityNotFoundException("WorkItemStage", stage_id)
        return stage

    @classmethod
    async def list_stages(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
    ) -> List[WorkItemStage]:
        """List pipeline stages for tenant company in sequence order."""
        stmt = (
            select(WorkItemStage)
            .where(WorkItemStage.company_id == company_id)
            .order_by(WorkItemStage.sequence.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def update_stage(
        cls,
        db: AsyncSession,
        stage_id: uuid.UUID,
        payload: WorkItemStageUpdate,
    ) -> WorkItemStage:
        """Update stage parameters or sequence."""
        stage = await cls.get_stage(db, stage_id)
        for field, val in payload.model_dump(exclude_unset=True).items():
            setattr(stage, field, val)
        await db.commit()
        await db.refresh(stage)
        return stage

    @classmethod
    async def delete_stage(
        cls,
        db: AsyncSession,
        stage_id: uuid.UUID,
    ) -> bool:
        """Soft-delete pipeline stage."""
        stage = await cls.get_stage(db, stage_id)
        await db.delete(stage)
        await db.commit()
        return True

    # -----------------------------------------------------------------------
    # Work Item CRUD
    # -----------------------------------------------------------------------

    @classmethod
    async def create_work_item(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        payload: WorkItemCreate,
    ) -> WorkItem:
        """Create new work item or sub-task."""
        item_number = payload.item_number or f"WI-{uuid.uuid4().hex[:8].upper()}"

        # If stage provided, verify and check if closed
        is_closed = False
        if payload.stage_id:
            stage = await cls.get_stage(db, payload.stage_id)
            if stage.is_closed:
                is_closed = True

        # If parent provided, verify parent exists
        if payload.parent_id:
            await cls.get_work_item(db, payload.parent_id)

        item = WorkItem(
            company_id=company_id,
            item_number=item_number,
            title=payload.title,
            description=payload.description,
            res_model=payload.res_model,
            res_id=payload.res_id,
            parent_id=payload.parent_id,
            priority=payload.priority,
            stage_id=payload.stage_id,
            assigned_to_id=payload.assigned_to_id,
            estimated_hours=payload.estimated_hours,
            spent_hours=payload.spent_hours,
            due_date=payload.due_date,
            is_closed=is_closed,
        )
        db.add(item)
        await db.commit()
        return await cls.get_work_item(db, item.id)

    @classmethod
    async def get_work_item(
        cls,
        db: AsyncSession,
        item_id: uuid.UUID,
    ) -> WorkItem:
        """Fetch work item with stage and dependencies loaded."""
        stmt = (
            select(WorkItem)
            .where(WorkItem.id == item_id)
            .options(
                selectinload(WorkItem.stage),
                selectinload(WorkItem.dependencies).selectinload(WorkItemDependency.predecessor),
            )
        )
        result = await db.execute(stmt)
        item = result.scalar_one_or_none()
        if not item:
            raise EntityNotFoundException("WorkItem", item_id)
        return item

    @classmethod
    async def list_work_items(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        stage_id: Optional[uuid.UUID] = None,
        assigned_to_id: Optional[uuid.UUID] = None,
        priority: Optional[str] = None,
        is_closed: Optional[bool] = None,
        res_model: Optional[str] = None,
        res_id: Optional[uuid.UUID] = None,
        parent_id: Optional[uuid.UUID] = None,
    ) -> List[WorkItem]:
        """List work items for tenant company with flexible filters."""
        stmt = (
            select(WorkItem)
            .where(WorkItem.company_id == company_id)
            .options(
                selectinload(WorkItem.stage),
                selectinload(WorkItem.dependencies).selectinload(WorkItemDependency.predecessor),
            )
        )
        if stage_id:
            stmt = stmt.where(WorkItem.stage_id == stage_id)
        if assigned_to_id:
            stmt = stmt.where(WorkItem.assigned_to_id == assigned_to_id)
        if priority:
            stmt = stmt.where(WorkItem.priority == priority)
        if is_closed is not None:
            stmt = stmt.where(WorkItem.is_closed == is_closed)
        if res_model:
            stmt = stmt.where(WorkItem.res_model == res_model)
        if res_id:
            stmt = stmt.where(WorkItem.res_id == res_id)
        if parent_id:
            stmt = stmt.where(WorkItem.parent_id == parent_id)
        stmt = stmt.order_by(WorkItem.created_at.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def update_work_item(
        cls,
        db: AsyncSession,
        item_id: uuid.UUID,
        payload: WorkItemUpdate,
    ) -> WorkItem:
        """Update work item parameters."""
        item = await cls.get_work_item(db, item_id)
        update_dict = payload.model_dump(exclude_unset=True)

        # Handle stage change sync
        if "stage_id" in update_dict and update_dict["stage_id"]:
            stage = await cls.get_stage(db, update_dict["stage_id"])
            item.stage = stage
            if stage.is_closed:
                item.is_closed = True

        for field, val in update_dict.items():
            setattr(item, field, val)

        await db.commit()
        return await cls.get_work_item(db, item.id)

    @classmethod
    async def delete_work_item(
        cls,
        db: AsyncSession,
        item_id: uuid.UUID,
    ) -> bool:
        """Soft-delete work item and cascade delete children."""
        item = await cls.get_work_item(db, item_id)
        await db.delete(item)
        await db.commit()
        return True

    # -----------------------------------------------------------------------
    # Sub-task Hierarchy Tree
    # -----------------------------------------------------------------------

    @classmethod
    async def get_subtask_tree(
        cls,
        db: AsyncSession,
        item_id: uuid.UUID,
    ) -> WorkItemTreeNode:
        """Recursively fetch sub-task tree rooted at item_id."""
        stmt = (
            select(WorkItem)
            .where(WorkItem.id == item_id)
            .options(
                selectinload(WorkItem.stage),
                selectinload(WorkItem.children).selectinload(WorkItem.stage),
                selectinload(WorkItem.children).selectinload(WorkItem.children),
            )
        )
        result = await db.execute(stmt)
        root = result.scalar_one_or_none()
        if not root:
            raise EntityNotFoundException("WorkItem", item_id)

        async def _build_node(item: WorkItem) -> WorkItemTreeNode:
            # Query direct children to ensure full recursion
            c_stmt = (
                select(WorkItem)
                .where(WorkItem.parent_id == item.id)
                .options(selectinload(WorkItem.stage))
            )
            c_res = await db.execute(c_stmt)
            children = list(c_res.scalars().all())

            child_nodes = []
            for child in children:
                child_nodes.append(await _build_node(child))

            return WorkItemTreeNode(
                id=item.id,
                item_number=item.item_number,
                title=item.title,
                priority=item.priority,
                is_closed=item.is_closed,
                stage_name=item.stage_name,
                children=child_nodes,
            )

        return await _build_node(root)

    # -----------------------------------------------------------------------
    # Dependencies & Cycle Detection
    # -----------------------------------------------------------------------

    @classmethod
    async def add_dependency(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        successor_id: uuid.UUID,
        payload: WorkItemDependencyCreate,
    ) -> WorkItemDependency:
        """Add predecessor -> successor dependency with DAG cycle prevention."""
        predecessor_id = payload.predecessor_id

        if predecessor_id == successor_id:
            raise ValidationException("A work item cannot depend on itself.")

        # Ensure both items exist in same company
        pred = await cls.get_work_item(db, predecessor_id)
        succ = await cls.get_work_item(db, successor_id)
        if pred.company_id != company_id or succ.company_id != company_id:
            raise ValidationException("Work items do not belong to active company.")

        # Cycle detection: traverse forward from successor. If we can reach predecessor, cycle exists!
        # Edge: A -> B means A is predecessor, B is successor.
        # Candidate edge: predecessor_id -> successor_id.
        # Path exists from successor_id -> ... -> predecessor_id?
        # BFS traversal:
        queue = deque([successor_id])
        visited: Set[uuid.UUID] = set([successor_id])

        while queue:
            current = queue.popleft()
            if current == predecessor_id:
                raise ValidationException(
                    "Circular dependency detected in work item DAG: adding this dependency creates a cycle."
                )

            # Query all successors of current
            stmt = select(WorkItemDependency.successor_id).where(
                WorkItemDependency.predecessor_id == current
            )
            edges_res = await db.execute(stmt)
            for next_node in edges_res.scalars().all():
                if next_node not in visited:
                    visited.add(next_node)
                    queue.append(next_node)

        # Safe to add
        dep = WorkItemDependency(
            company_id=company_id,
            predecessor_id=predecessor_id,
            successor_id=successor_id,
            dependency_type=payload.dependency_type,
        )
        db.add(dep)
        await db.commit()

        # Eager load related work items
        stmt = (
            select(WorkItemDependency)
            .where(WorkItemDependency.id == dep.id)
            .options(
                selectinload(WorkItemDependency.predecessor),
                selectinload(WorkItemDependency.successor),
            )
        )
        res = await db.execute(stmt)
        return res.scalar_one()

    @classmethod
    async def delete_dependency(
        cls,
        db: AsyncSession,
        dependency_id: uuid.UUID,
    ) -> bool:
        """Remove a dependency edge."""
        stmt = select(WorkItemDependency).where(WorkItemDependency.id == dependency_id)
        res = await db.execute(stmt)
        dep = res.scalar_one_or_none()
        if not dep:
            raise EntityNotFoundException("WorkItemDependency", dependency_id)
        await db.delete(dep)
        await db.commit()
        return True

    # -----------------------------------------------------------------------
    # Stage Transition
    # -----------------------------------------------------------------------

    @classmethod
    async def transition_stage(
        cls,
        db: AsyncSession,
        item_id: uuid.UUID,
        stage_id: uuid.UUID,
    ) -> WorkItem:
        """Transition work item to another stage and synchronize closed state."""
        item = await cls.get_work_item(db, item_id)
        stage = await cls.get_stage(db, stage_id)

        item.stage_id = stage.id
        item.stage = stage
        if stage.is_closed:
            item.is_closed = True

        await db.commit()
        return await cls.get_work_item(db, item.id)

