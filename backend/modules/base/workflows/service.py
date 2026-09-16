"""Workflow state machine service orchestrating transitions, guards, RBAC, and record freezing."""

import uuid
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from fastapi import status
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from core.event_bus import event_bus
from core.exceptions import PlatformException, EntityNotFoundException, PermissionDeniedException
from modules.base.identity_rbac.flac_service import FLACService
from modules.base.automated_actions.introspection import find_model_class
from modules.base.automated_actions.engine.evaluator import ASTConditionEvaluator

from modules.base.workflows.models import (
    WorkflowDefinition,
    WorkflowTransition,
    WorkflowExecutionLog,
)
from modules.base.workflows.schemas import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionUpdate,
    WorkflowTransitionCreate,
    WorkflowTransitionUpdate,
    WorkflowTransitionResult,
    AvailableTransitionResponse,
)

logger = logging.getLogger("sovereign.workflows.service")


class WorkflowTransitionException(PlatformException):
    """Raised when an invalid or rejected state transition is triggered."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="WORKFLOW_TRANSITION_ERROR",
            message=message,
            resolution_hint="Check current record state, trigger name, permissions, and guard conditions.",
            details=details or {},
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class WorkflowService:
    """Core engine orchestrating declarative workflows, guards, and record lock transitions."""

    @classmethod
    async def create_definition(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        data: WorkflowDefinitionCreate,
    ) -> WorkflowDefinition:
        """Create a new workflow definition with optional initial transitions."""
        # 1. Check uniqueness of (company_id, res_model, code)
        existing_stmt = select(WorkflowDefinition).where(
            and_(
                WorkflowDefinition.company_id == company_id,
                WorkflowDefinition.res_model.ilike(data.res_model.strip()),
                WorkflowDefinition.code.ilike(data.code.strip()),
            )
        )
        existing_res = await db.execute(existing_stmt)
        if existing_res.scalar_one_or_none():
            raise WorkflowTransitionException(
                f"Workflow definition with code '{data.code}' for model '{data.res_model}' already exists."
            )

        # 2. Instantiate workflow definition
        states_dicts = [s.model_dump() for s in data.states]
        wf = WorkflowDefinition(
            company_id=company_id,
            name=data.name,
            code=data.code.strip().lower(),
            res_model=data.res_model.strip().lower(),
            state_field=data.state_field.strip().lower(),
            initial_state=data.initial_state.strip().lower(),
            states=states_dicts,
            is_active=data.is_active,
        )
        db.add(wf)
        await db.flush()

        # 3. Add initial transitions if provided
        for t_data in data.transitions:
            transition = WorkflowTransition(
                company_id=company_id,
                workflow_id=wf.id,
                trigger_name=t_data.trigger_name.strip().lower(),
                from_state=t_data.from_state.strip().lower(),
                to_state=t_data.to_state.strip().lower(),
                required_permission=t_data.required_permission.strip() if t_data.required_permission else None,
                guard_condition=t_data.guard_condition,
                freeze_record=t_data.freeze_record,
                sequence=t_data.sequence,
            )
            db.add(transition)

        await db.commit()
        return await cls.get_definition(db, company_id, wf.id)  # type: ignore

    @classmethod
    async def get_definition(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        workflow_id: uuid.UUID,
    ) -> Optional[WorkflowDefinition]:
        """Fetch workflow definition with all configured transitions."""
        stmt = (
            select(WorkflowDefinition)
            .where(
                and_(
                    WorkflowDefinition.id == workflow_id,
                    WorkflowDefinition.company_id == company_id,
                )
            )
            .options(selectinload(WorkflowDefinition.transitions))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def get_active_definition_for_model(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        res_model: str,
    ) -> Optional[WorkflowDefinition]:
        """Retrieve the primary active workflow definition governing a model."""
        stmt = (
            select(WorkflowDefinition)
            .where(
                and_(
                    WorkflowDefinition.company_id == company_id,
                    WorkflowDefinition.res_model.ilike(res_model.strip()),
                    WorkflowDefinition.is_active.is_(True),
                )
            )
            .options(selectinload(WorkflowDefinition.transitions))
            .order_by(WorkflowDefinition.created_at.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    @classmethod
    async def list_definitions(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        res_model: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[WorkflowDefinition]:
        """List workflow definitions for a tenant."""
        stmt = (
            select(WorkflowDefinition)
            .where(WorkflowDefinition.company_id == company_id)
            .options(selectinload(WorkflowDefinition.transitions))
            .order_by(WorkflowDefinition.res_model, WorkflowDefinition.name)
        )
        if res_model:
            stmt = stmt.where(WorkflowDefinition.res_model.ilike(res_model.strip()))
        if is_active is not None:
            stmt = stmt.where(WorkflowDefinition.is_active.is_(is_active))

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def update_definition(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        workflow_id: uuid.UUID,
        data: WorkflowDefinitionUpdate,
    ) -> WorkflowDefinition:
        """Update workflow definition metadata."""
        wf = await cls.get_definition(db, company_id, workflow_id)
        if not wf:
            raise EntityNotFoundException("WorkflowDefinition", workflow_id)

        if data.name is not None:
            wf.name = data.name
        if data.state_field is not None:
            wf.state_field = data.state_field.strip().lower()
        if data.initial_state is not None:
            wf.initial_state = data.initial_state.strip().lower()
        if data.states is not None:
            wf.states = [s.model_dump() for s in data.states]
        if data.is_active is not None:
            wf.is_active = data.is_active

        await db.commit()
        return await cls.get_definition(db, company_id, workflow_id)  # type: ignore

    @classmethod
    async def delete_definition(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        workflow_id: uuid.UUID,
    ) -> bool:
        """Delete workflow definition and its transitions."""
        wf = await cls.get_definition(db, company_id, workflow_id)
        if not wf:
            raise EntityNotFoundException("WorkflowDefinition", workflow_id)

        await db.delete(wf)
        await db.commit()
        return True

    @classmethod
    async def add_transition(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        workflow_id: uuid.UUID,
        data: WorkflowTransitionCreate,
    ) -> WorkflowTransition:
        """Add a state transition to an existing workflow definition."""
        wf = await cls.get_definition(db, company_id, workflow_id)
        if not wf:
            raise EntityNotFoundException("WorkflowDefinition", workflow_id)

        transition = WorkflowTransition(
            company_id=company_id,
            workflow_id=wf.id,
            trigger_name=data.trigger_name.strip().lower(),
            from_state=data.from_state.strip().lower(),
            to_state=data.to_state.strip().lower(),
            required_permission=data.required_permission.strip() if data.required_permission else None,
            guard_condition=data.guard_condition,
            freeze_record=data.freeze_record,
            sequence=data.sequence,
        )
        db.add(transition)
        await db.commit()
        await db.refresh(transition)
        return transition

    @classmethod
    async def delete_transition(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        transition_id: uuid.UUID,
    ) -> bool:
        """Remove a transition rule."""
        stmt = select(WorkflowTransition).where(
            and_(
                WorkflowTransition.id == transition_id,
                WorkflowTransition.company_id == company_id,
            )
        )
        res = await db.execute(stmt)
        transition = res.scalar_one_or_none()
        if not transition:
            raise EntityNotFoundException("WorkflowTransition", transition_id)

        await db.delete(transition)
        await db.commit()
        return True

    @classmethod
    async def _load_target_record(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        res_model: str,
        record_id: uuid.UUID,
    ) -> Any:
        """Dynamically resolve model mapper and load entity by ID."""
        model_cls = find_model_class(res_model)
        if not model_cls:
            raise EntityNotFoundException("ModelClass", res_model)

        stmt = select(model_cls).where(
            and_(
                model_cls.id == record_id,
                model_cls.company_id == company_id,
            )
        )
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()
        if not record:
            raise EntityNotFoundException(res_model, record_id)
        return record

    @classmethod
    async def get_available_transitions(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        user: Any,
        res_model: str,
        record_id: uuid.UUID,
    ) -> List[AvailableTransitionResponse]:
        """Compute the list of currently valid state triggers for an entity."""
        record = await cls._load_target_record(db, company_id, res_model, record_id)
        wf = await cls.get_active_definition_for_model(db, company_id, res_model)
        if not wf:
            return []

        # Read current state
        current_state = (
            getattr(record, wf.state_field, None)
            or (record.custom_fields.get(wf.state_field) if hasattr(record, "custom_fields") else None)
            or wf.initial_state
        )
        current_state = str(current_state).lower()

        record_dict = record.to_dict() if hasattr(record, "to_dict") else {}
        available: List[AvailableTransitionResponse] = []

        for t in wf.transitions:
            # 1. State matching
            if t.from_state != "*" and t.from_state != current_state:
                continue

            # 2. RBAC Permission Check
            if t.required_permission and user:
                has_perm = await FLACService.has_permission(user, t.required_permission, db)
                if not has_perm:
                    continue

            # 3. AST Guard Condition Check
            if t.guard_condition:
                if not ASTConditionEvaluator.evaluate(t.guard_condition, record_dict):
                    continue

            available.append(
                AvailableTransitionResponse(
                    trigger_name=t.trigger_name,
                    from_state=t.from_state,
                    to_state=t.to_state,
                    freeze_record=t.freeze_record,
                    required_permission=t.required_permission,
                    sequence=t.sequence,
                )
            )

        available.sort(key=lambda x: x.sequence)
        return available

    @classmethod
    async def execute_transition(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        user: Any,
        res_model: str,
        record_id: uuid.UUID,
        trigger_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkflowTransitionResult:
        """Execute a state transition trigger on a target entity."""
        record = await cls._load_target_record(db, company_id, res_model, record_id)
        wf = await cls.get_active_definition_for_model(db, company_id, res_model)
        if not wf:
            raise WorkflowTransitionException(
                f"No active workflow definition configured for model '{res_model}'."
            )

        # 1. Determine current state
        current_state = (
            getattr(record, wf.state_field, None)
            or (record.custom_fields.get(wf.state_field) if hasattr(record, "custom_fields") else None)
            or wf.initial_state
        )
        current_state = str(current_state).lower()
        trigger_clean = trigger_name.strip().lower()

        # 2. Locate matching transition
        matched_transition: Optional[WorkflowTransition] = None
        for t in wf.transitions:
            if t.trigger_name == trigger_clean:
                if t.from_state == "*" or t.from_state == current_state:
                    matched_transition = t
                    break

        if not matched_transition:
            raise WorkflowTransitionException(
                f"Trigger '{trigger_clean}' is not permitted from current state '{current_state}' for '{res_model}'."
            )

        # 3. RBAC Permission verification
        if matched_transition.required_permission and user:
            has_perm = await FLACService.has_permission(user, matched_transition.required_permission, db)
            if not has_perm:
                raise PermissionDeniedException(
                    action=matched_transition.required_permission,
                    resource=res_model,
                )

        # 4. AST Guard condition verification
        record_dict = record.to_dict() if hasattr(record, "to_dict") else {}
        if matched_transition.guard_condition:
            guard_ok = ASTConditionEvaluator.evaluate(matched_transition.guard_condition, record_dict)
            if not guard_ok:
                raise WorkflowTransitionException(
                    f"Guard condition failed for trigger '{trigger_clean}'. Record attributes do not satisfy criteria.",
                    details={"condition": matched_transition.guard_condition},
                )

        # 5. Check if destination state or transition is frozen
        should_freeze = matched_transition.freeze_record
        if not should_freeze and wf.states:
            for s in wf.states:
                if isinstance(s, dict) and s.get("code") == matched_transition.to_state:
                    if s.get("is_frozen"):
                        should_freeze = True
                        break

        # 6. Apply state transition with record lock bypass authorized for this mutation
        record._allow_workflow_mutation = True
        try:
            # Update state attribute
            if hasattr(record, wf.state_field):
                setattr(record, wf.state_field, matched_transition.to_state)
            elif hasattr(record, "set_custom_field"):
                record.set_custom_field(wf.state_field, matched_transition.to_state)

            # Update record freeze status
            if should_freeze:
                if hasattr(record, "set_custom_field"):
                    record.set_custom_field("_is_locked", True)
                    record.set_custom_field("_frozen_state", matched_transition.to_state)
                if hasattr(record, "is_locked"):
                    record.is_locked = True
            else:
                if hasattr(record, "set_custom_field"):
                    record.set_custom_field("_is_locked", False)
                    if hasattr(record, "remove_custom_field"):
                        record.remove_custom_field("_frozen_state")
                    elif hasattr(record, "custom_fields") and isinstance(record.custom_fields, dict):
                        record.custom_fields.pop("_frozen_state", None)
                if hasattr(record, "is_locked"):
                    record.is_locked = False

            # 7. Record execution log
            log_entry = WorkflowExecutionLog(
                company_id=company_id,
                workflow_id=wf.id,
                transition_id=matched_transition.id,
                res_model=res_model.lower(),
                res_id=record.id,
                from_state=current_state,
                to_state=matched_transition.to_state,
                trigger_name=trigger_clean,
                actor_id=user.id if user else None,
                metadata_snapshot=metadata or {},
            )
            db.add(log_entry)

            # 8. Dispatch event on EventBus
            try:
                await event_bus.publish(
                    f"workflow.{res_model.lower()}.state_changed",
                    {
                        "company_id": str(company_id),
                        "res_model": res_model.lower(),
                        "res_id": str(record.id),
                        "from_state": current_state,
                        "to_state": matched_transition.to_state,
                        "trigger": trigger_clean,
                        "is_frozen": should_freeze,
                        "actor_id": str(user.id) if user else None,
                    },
                )
            except Exception as exc:
                logger.warning(f"Workflow event broadcast failed: {exc}")

            await db.commit()
            await db.refresh(record)
        finally:
            record._allow_workflow_mutation = False

        return WorkflowTransitionResult(
            res_model=res_model.lower(),
            record_id=record.id,
            from_state=current_state,
            to_state=matched_transition.to_state,
            trigger_name=trigger_clean,
            is_frozen=should_freeze,
            state_field=wf.state_field,
            transition_time=datetime.now(timezone.utc),
        )

    @classmethod
    async def unfreeze_record(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        user: Any,
        res_model: str,
        record_id: uuid.UUID,
        reason: str = "",
    ) -> bool:
        """Administrative unlock for a frozen record."""
        # Check permissions: superuser or 'workflow:override_freeze'
        if user and not getattr(user, "is_superuser", False):
            has_perm = await FLACService.has_permission(user, "workflow:override_freeze", db)
            if not has_perm:
                raise PermissionDeniedException(
                    action="workflow:override_freeze",
                    resource=res_model,
                )

        record = await cls._load_target_record(db, company_id, res_model, record_id)

        record._allow_workflow_mutation = True
        try:
            if hasattr(record, "set_custom_field"):
                record.set_custom_field("_is_locked", False)
                if hasattr(record, "remove_custom_field"):
                    record.remove_custom_field("_frozen_state")
                elif hasattr(record, "custom_fields") and isinstance(record.custom_fields, dict):
                    record.custom_fields.pop("_frozen_state", None)
            if hasattr(record, "is_locked"):
                record.is_locked = False

            # Add audit log of unfreeze
            log_entry = WorkflowExecutionLog(
                company_id=company_id,
                workflow_id=None,
                transition_id=None,
                res_model=res_model.lower(),
                res_id=record.id,
                from_state="frozen",
                to_state="unfrozen",
                trigger_name="administrative_unfreeze",
                actor_id=user.id if user else None,
                metadata_snapshot={"reason": reason},
            )
            db.add(log_entry)

            await db.commit()
            await db.refresh(record)
        finally:
            record._allow_workflow_mutation = False
        return True

    @classmethod
    async def get_transition_history(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        res_model: str,
        res_id: uuid.UUID,
    ) -> List[WorkflowExecutionLog]:
        """Fetch chronological audit history of state transitions on a record."""
        stmt = (
            select(WorkflowExecutionLog)
            .where(
                and_(
                    WorkflowExecutionLog.company_id == company_id,
                    WorkflowExecutionLog.res_model.ilike(res_model.strip()),
                    WorkflowExecutionLog.res_id == res_id,
                )
            )
            .order_by(WorkflowExecutionLog.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
