"""Multi-Level Governance and Approval Engine business service."""

import uuid
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from core.event_bus import event_bus
from core.exceptions import (
    PlatformException,
    EntityNotFoundException,
    PermissionDeniedException,
    ValidationException,
)
from modules.base.identity_rbac.models import User, UserGroupLink
from modules.base.identity_rbac.flac_service import FLACService
from modules.base.automated_actions.introspection import find_model_class
from modules.base.automated_actions.engine.evaluator import ASTConditionEvaluator

from modules.base.approvals.models import (
    ApprovalRule,
    ApprovalRequest,
    ApprovalAction,
)
from modules.base.approvals.schemas import (
    ApprovalRuleCreate,
    ApprovalRuleUpdate,
    ApprovalRequestCreate,
    ApprovalDecisionResponse,
)

logger = logging.getLogger("sovereign.approvals.service")


class ApprovalService:
    """Enterprise service orchestrating multi-tier approval gates and governance actions."""

    # ---------------------------------------------------------------------------
    # Approval Rules Management
    # ---------------------------------------------------------------------------

    @classmethod
    async def create_rule(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        data: ApprovalRuleCreate,
    ) -> ApprovalRule:
        """Register a new approval gate rule."""
        existing = await db.execute(
            select(ApprovalRule).where(
                and_(
                    ApprovalRule.company_id == company_id,
                    ApprovalRule.res_model.ilike(data.res_model.strip()),
                    ApprovalRule.code.ilike(data.code.strip()),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValidationException(
                f"Approval rule with code '{data.code}' already exists for model '{data.res_model}'."
            )

        rule = ApprovalRule(
            company_id=company_id,
            name=data.name,
            code=data.code.strip().lower(),
            res_model=data.res_model.strip().lower(),
            tier=data.tier,
            condition=data.condition,
            approver_group_id=data.approver_group_id,
            approver_user_id=data.approver_user_id,
            is_active=data.is_active,
        )
        db.add(rule)
        await db.commit()
        await db.refresh(rule)
        return rule

    @classmethod
    async def get_rule(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        rule_id: uuid.UUID,
    ) -> Optional[ApprovalRule]:
        """Fetch approval rule by ID."""
        stmt = select(ApprovalRule).where(
            and_(
                ApprovalRule.id == rule_id,
                ApprovalRule.company_id == company_id,
            )
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @classmethod
    async def list_rules(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        res_model: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[ApprovalRule]:
        """List configured approval rules for tenant."""
        stmt = select(ApprovalRule).where(ApprovalRule.company_id == company_id)
        if res_model:
            stmt = stmt.where(ApprovalRule.res_model.ilike(res_model.strip()))
        if is_active is not None:
            stmt = stmt.where(ApprovalRule.is_active.is_(is_active))

        stmt = stmt.order_by(ApprovalRule.res_model, ApprovalRule.tier.asc())
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def update_rule(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        rule_id: uuid.UUID,
        data: ApprovalRuleUpdate,
    ) -> ApprovalRule:
        """Update an existing approval rule."""
        rule = await cls.get_rule(db, company_id, rule_id)
        if not rule:
            raise EntityNotFoundException("ApprovalRule", rule_id)

        update_dict = data.model_dump(exclude_unset=True)
        for key, val in update_dict.items():
            setattr(rule, key, val)

        await db.commit()
        await db.refresh(rule)
        return rule

    @classmethod
    async def delete_rule(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        rule_id: uuid.UUID,
    ) -> bool:
        """Delete an approval rule."""
        rule = await cls.get_rule(db, company_id, rule_id)
        if not rule:
            raise EntityNotFoundException("ApprovalRule", rule_id)

        await db.delete(rule)
        await db.commit()
        return True

    # ---------------------------------------------------------------------------
    # Approval Requests Lifecycle
    # ---------------------------------------------------------------------------

    @classmethod
    async def submit_request(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        user: User,
        data: ApprovalRequestCreate,
    ) -> ApprovalRequest:
        """Initiate an approval request for a business entity against active rules."""
        # 1. Resolve and inspect target record
        model_cls = find_model_class(data.res_model)
        if not model_cls:
            raise EntityNotFoundException("ModelClass", data.res_model)

        record_stmt = select(model_cls).where(
            and_(
                model_cls.id == data.res_id,
                model_cls.company_id == company_id,
            )
        )
        record = (await db.execute(record_stmt)).scalar_one_or_none()
        if not record:
            raise EntityNotFoundException(data.res_model, data.res_id)

        record_dict = record.to_dict() if hasattr(record, "to_dict") else {}

        # 2. Find matching active approval rules
        rules_stmt = (
            select(ApprovalRule)
            .where(
                and_(
                    ApprovalRule.company_id == company_id,
                    ApprovalRule.res_model.ilike(data.res_model.strip()),
                    ApprovalRule.is_active.is_(True),
                )
            )
            .order_by(ApprovalRule.tier.asc())
        )
        all_rules = (await db.execute(rules_stmt)).scalars().all()

        matched_rule: Optional[ApprovalRule] = None
        for r in all_rules:
            if not r.condition:
                matched_rule = r
                break
            if ASTConditionEvaluator.evaluate(r.condition, record_dict):
                matched_rule = r
                break

        # 3. Create ApprovalRequest
        req = ApprovalRequest(
            company_id=company_id,
            rule_id=matched_rule.id if matched_rule else None,
            res_model=data.res_model.strip().lower(),
            res_id=data.res_id,
            requested_by_id=user.id,
            approver_group_id=matched_rule.approver_group_id if matched_rule else None,
            approver_user_id=matched_rule.approver_user_id if matched_rule else None,
            tier=matched_rule.tier if matched_rule else 1,
            state="pending",
            summary=data.summary or f"Approval required for {data.res_model} ({data.res_id})",
            target_snapshot=record_dict,
        )
        db.add(req)
        await db.commit()
        await db.refresh(req)

        # 4. Dispatch EventBus notification
        try:
            await event_bus.publish(
                "approval.request.created",
                {
                    "company_id": str(company_id),
                    "request_id": str(req.id),
                    "res_model": req.res_model,
                    "res_id": str(req.res_id),
                    "requested_by_id": str(user.id),
                    "tier": req.tier,
                },
            )
        except Exception as exc:
            logger.warning(f"Approval EventBus broadcast failed: {exc}")

        return await cls.get_request(db, company_id, req.id)  # type: ignore

    @classmethod
    async def get_request(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        request_id: uuid.UUID,
    ) -> Optional[ApprovalRequest]:
        """Retrieve approval request with action audit trail."""
        stmt = (
            select(ApprovalRequest)
            .where(
                and_(
                    ApprovalRequest.id == request_id,
                    ApprovalRequest.company_id == company_id,
                )
            )
            .options(
                selectinload(ApprovalRequest.rule),
                selectinload(ApprovalRequest.actions),
            )
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @classmethod
    async def list_inbox(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        user: User,
        state: str = "pending",
    ) -> List[ApprovalRequest]:
        """Query pending approval tickets assigned to the active user or user's groups."""
        stmt = (
            select(ApprovalRequest)
            .where(
                and_(
                    ApprovalRequest.company_id == company_id,
                    ApprovalRequest.state == state,
                )
            )
            .options(
                selectinload(ApprovalRequest.rule),
                selectinload(ApprovalRequest.actions),
            )
            .order_by(ApprovalRequest.created_at.desc())
        )

        # Superusers see all pending approvals for the company
        if getattr(user, "is_superuser", False):
            res = await db.execute(stmt)
            return list(res.scalars().all())

        # Resolve user's group IDs
        group_links_stmt = select(UserGroupLink.group_id).where(UserGroupLink.user_id == user.id)
        group_ids = (await db.execute(group_links_stmt)).scalars().all()

        # Build assignment predicate
        predicates = [
            ApprovalRequest.approver_user_id == user.id,
        ]
        if group_ids:
            predicates.append(ApprovalRequest.approver_group_id.in_(group_ids))

        # Check if user has global 'approval:view_all' permission
        has_view_all = await FLACService.has_permission(user, "approval:view_all", db)
        if not has_view_all:
            # Also allow unassigned tickets if user has 'approval:act' permission
            has_act = await FLACService.has_permission(user, "approval:act", db)
            if has_act:
                predicates.append(
                    and_(
                        ApprovalRequest.approver_user_id.is_(None),
                        ApprovalRequest.approver_group_id.is_(None),
                    )
                )
            stmt = stmt.where(or_(*predicates))

        res = await db.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def decide_request(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        user: User,
        request_id: uuid.UUID,
        action: str,
        comments: Optional[str] = None,
    ) -> ApprovalDecisionResponse:
        """Execute approve, reject, or cancel decision on an approval ticket."""
        req = await cls.get_request(db, company_id, request_id)
        if not req:
            raise EntityNotFoundException("ApprovalRequest", request_id)

        if req.state != "pending":
            raise ValidationException(f"Cannot execute '{action}' on ticket currently in '{req.state}' state.")

        # 1. Authorization check
        is_authorized = False
        if getattr(user, "is_superuser", False):
            is_authorized = True
        elif req.approver_user_id and req.approver_user_id == user.id:
            is_authorized = True
        elif req.approver_group_id:
            # Check user membership
            member_stmt = select(UserGroupLink).where(
                and_(
                    UserGroupLink.group_id == req.approver_group_id,
                    UserGroupLink.user_id == user.id,
                )
            )
            is_member = (await db.execute(member_stmt)).scalar_one_or_none()
            if is_member:
                is_authorized = True
        else:
            # General approval:act capability
            is_authorized = await FLACService.has_permission(user, "approval:act", db)

        if not is_authorized:
            raise PermissionDeniedException(action=f"approval:{action}", resource=req.res_model)

        # 2. Update state
        action_clean = action.strip().lower()
        if action_clean == "approve":
            req.state = "approved"
        elif action_clean == "reject":
            req.state = "rejected"
        elif action_clean == "cancel":
            req.state = "cancelled"
        else:
            raise ValidationException(f"Invalid approval action '{action}'. Permitted: approve, reject, cancel.")

        # 3. Add action log
        act_entry = ApprovalAction(
            company_id=company_id,
            request_id=req.id,
            actor_id=user.id,
            action=action_clean,
            comments=comments,
        )
        db.add(act_entry)

        # 4. Dispatch EventBus notification
        try:
            await event_bus.publish(
                f"approval.request.{action_clean}d",
                {
                    "company_id": str(company_id),
                    "request_id": str(req.id),
                    "res_model": req.res_model,
                    "res_id": str(req.res_id),
                    "actor_id": str(user.id),
                    "action": action_clean,
                    "comments": comments,
                },
            )
        except Exception as exc:
            logger.warning(f"Approval EventBus broadcast failed: {exc}")

        await db.commit()
        await db.refresh(req)

        return ApprovalDecisionResponse(
            request_id=req.id,
            res_model=req.res_model,
            res_id=req.res_id,
            state=req.state,
            action=action_clean,
            actor_id=user.id,
            comments=comments,
            action_time=datetime.now(timezone.utc),
        )

    @classmethod
    async def get_requests_for_entity(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        res_model: str,
        res_id: uuid.UUID,
    ) -> List[ApprovalRequest]:
        """Fetch all historical approval tickets associated with an entity."""
        stmt = (
            select(ApprovalRequest)
            .where(
                and_(
                    ApprovalRequest.company_id == company_id,
                    ApprovalRequest.res_model.ilike(res_model.strip()),
                    ApprovalRequest.res_id == res_id,
                )
            )
            .options(
                selectinload(ApprovalRequest.rule),
                selectinload(ApprovalRequest.actions),
            )
            .order_by(ApprovalRequest.created_at.desc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())
