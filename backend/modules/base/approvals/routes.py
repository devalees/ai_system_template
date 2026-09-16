"""FastAPI route endpoints for Multi-Level Governance and Approval Engine."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.context import get_active_company_id
from core.exceptions import EntityNotFoundException, ValidationException
from modules.base.identity_rbac.models import User
from modules.base.identity_rbac.dependencies import get_current_user, require_permission

from modules.base.approvals.service import ApprovalService
from modules.base.approvals.schemas import (
    ApprovalRuleCreate,
    ApprovalRuleUpdate,
    ApprovalRuleResponse,
    ApprovalRequestCreate,
    ApprovalRequestResponse,
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
)

router = APIRouter(prefix="", tags=["Multi-Level Governance & Approval Engine"])


def _resolve_company_id(user: User) -> uuid.UUID:
    """Resolve active company context."""
    cid = get_active_company_id() or user.company_id
    if not cid:
        raise ValidationException("Active company context (X-Company-ID) is required.")
    return cid


# ---------------------------------------------------------------------------
# Approval Rules Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/rules",
    response_model=ApprovalRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Approval Rule",
    description="Configures a new tiered approval gate with optional AST conditions and designated approvers.",
)
async def create_approval_rule(
    payload: ApprovalRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = _resolve_company_id(current_user)
    return await ApprovalService.create_rule(db, company_id, payload)


@router.get(
    "/rules",
    response_model=List[ApprovalRuleResponse],
    summary="List Approval Rules",
    description="Retrieves approval rules for the active tenant, with optional model filtering.",
)
async def list_approval_rules(
    res_model: Optional[str] = Query(None, description="Filter rules by target model name"),
    is_active: Optional[bool] = Query(None, description="Filter rules by operational status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = _resolve_company_id(current_user)
    return await ApprovalService.list_rules(db, company_id, res_model, is_active)


@router.get(
    "/rules/{id}",
    response_model=ApprovalRuleResponse,
    summary="Get Approval Rule",
    description="Fetches details of a specific approval rule.",
)
async def get_approval_rule(
    id: uuid.UUID = Path(..., description="Approval rule UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = _resolve_company_id(current_user)
    rule = await ApprovalService.get_rule(db, company_id, id)
    if not rule:
        raise EntityNotFoundException("ApprovalRule", id)
    return rule


@router.put(
    "/rules/{id}",
    response_model=ApprovalRuleResponse,
    summary="Update Approval Rule",
    description="Updates criteria, tier level, or assigned approver for a rule.",
)
async def update_approval_rule(
    payload: ApprovalRuleUpdate,
    id: uuid.UUID = Path(..., description="Approval rule UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = _resolve_company_id(current_user)
    return await ApprovalService.update_rule(db, company_id, id, payload)


@router.delete(
    "/rules/{id}",
    summary="Delete Approval Rule",
    description="Permanently deletes an approval rule.",
)
async def delete_approval_rule(
    id: uuid.UUID = Path(..., description="Approval rule UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = _resolve_company_id(current_user)
    await ApprovalService.delete_rule(db, company_id, id)
    return {"status": "success", "message": "Approval rule deleted successfully."}


# ---------------------------------------------------------------------------
# Approval Requests & Decision Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/requests",
    response_model=ApprovalRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Approval Request",
    description="Submits an entity for approval, evaluating active rules to assign tiers and approvers.",
)
async def submit_approval_request(
    payload: ApprovalRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = _resolve_company_id(current_user)
    return await ApprovalService.submit_request(db, company_id, current_user, payload)


@router.get(
    "/inbox",
    response_model=List[ApprovalRequestResponse],
    summary="Approver Inbox",
    description="Lists pending approval tickets assigned to the active user or their groups.",
)
async def get_approver_inbox(
    state: str = Query(default="pending", description="Filter inbox by state (pending, approved, rejected)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = _resolve_company_id(current_user)
    return await ApprovalService.list_inbox(db, company_id, current_user, state=state)


@router.get(
    "/requests/{id}",
    response_model=ApprovalRequestResponse,
    summary="Get Approval Request",
    description="Retrieves an approval ticket with its full sign-off audit trail.",
)
async def get_approval_request(
    id: uuid.UUID = Path(..., description="Approval request UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = _resolve_company_id(current_user)
    req = await ApprovalService.get_request(db, company_id, id)
    if not req:
        raise EntityNotFoundException("ApprovalRequest", id)
    return req


@router.post(
    "/requests/{id}/approve",
    response_model=ApprovalDecisionResponse,
    summary="Approve Request",
    description="Records an approval sign-off decision with audited commentary.",
)
async def approve_request(
    payload: ApprovalDecisionRequest,
    id: uuid.UUID = Path(..., description="Approval request UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = _resolve_company_id(current_user)
    return await ApprovalService.decide_request(
        db, company_id, current_user, id, action="approve", comments=payload.comments
    )


@router.post(
    "/requests/{id}/reject",
    response_model=ApprovalDecisionResponse,
    summary="Reject Request",
    description="Records a rejection decision with audited commentary.",
)
async def reject_request(
    payload: ApprovalDecisionRequest,
    id: uuid.UUID = Path(..., description="Approval request UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = _resolve_company_id(current_user)
    return await ApprovalService.decide_request(
        db, company_id, current_user, id, action="reject", comments=payload.comments
    )


@router.get(
    "/entity/{res_model}/{res_id}",
    response_model=List[ApprovalRequestResponse],
    summary="Get Record Approval History",
    description="Retrieves all historical and pending approval tickets associated with a business record.",
)
async def get_record_approval_history(
    res_model: str = Path(..., description="Target model name (e.g. 'party', 'invoice')"),
    res_id: uuid.UUID = Path(..., description="Target record UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = _resolve_company_id(current_user)
    return await ApprovalService.get_requests_for_entity(db, company_id, res_model, res_id)
