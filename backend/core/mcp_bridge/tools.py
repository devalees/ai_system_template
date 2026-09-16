"""Core business capability execution functions for FastMCP Dynamic Tool Reflection."""

import uuid
import logging
from decimal import Decimal
from datetime import datetime, date, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.context import get_active_company_id
from core.exceptions import PlatformException
from modules.base.automated_actions.introspection import find_model_class
from modules.base.fiscal_calendar.service import FiscalCalendarService, FiscalPeriodNotFoundException
from modules.base.parties.service import PartyService
from modules.base.pricing.service import PricingService
from modules.base.pricing.schemas import PriceEvaluateRequest
from modules.base.taxes.service import TaxService
from modules.base.taxes.schemas import TaxComputeRequest, TaxLineInput

from modules.base.payments.service import PaymentTermsService
from modules.base.payments.schemas import ComputePaymentScheduleRequest
from modules.base.approvals.service import ApprovalService
from modules.base.approvals.schemas import ApprovalRequestCreate
from modules.base.workflows.service import WorkflowService
from modules.base.resources.service import ResourceService
from modules.base.resources.schemas import CheckAvailabilityRequest

logger = logging.getLogger("sovereign.mcp_bridge.tools")


# ---------------------------------------------------------------------------
# Helper: Serialization
# ---------------------------------------------------------------------------

def _json_serialize_value(val: Any) -> Any:
    """Helper to convert date, datetime, UUID, Decimal to JSON-safe primitives."""
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, uuid.UUID):
        return str(val)
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, dict):
        return {k: _json_serialize_value(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_json_serialize_value(v) for v in val]
    return val


# ---------------------------------------------------------------------------
# Tool 1: Query Records
# ---------------------------------------------------------------------------

async def tool_query_records(
    db: AsyncSession,
    company_id: uuid.UUID,
    model: str,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """Query platform business entity records with multi-tenant filtering."""
    model_cls = find_model_class(model)
    if not model_cls:
        raise ValueError(f"Unknown or unregistered model class '{model}'.")

    stmt = select(model_cls)
    if hasattr(model_cls, "company_id"):
        stmt = stmt.where(model_cls.company_id == company_id)
    if hasattr(model_cls, "deleted_at"):
        stmt = stmt.where(model_cls.deleted_at.is_(None))


    if filters:
        for k, v in filters.items():
            if hasattr(model_cls, k):
                column = getattr(model_cls, k)
                if isinstance(v, list):
                    stmt = stmt.where(column.in_(v))
                else:
                    stmt = stmt.where(column == v)

    stmt = stmt.limit(min(limit, 200))
    results = list((await db.execute(stmt)).scalars().all())

    records: List[Dict[str, Any]] = []
    for r in results:
        if hasattr(r, "to_dict"):
            r_dict = r.to_dict()
        elif hasattr(r, "__dict__"):
            r_dict = {k: v for k, v in r.__dict__.items() if not k.startswith("_")}
        else:
            r_dict = {"id": str(getattr(r, "id", ""))}
        records.append(_json_serialize_value(r_dict))

    return {
        "model": model,
        "count": len(records),
        "records": records,
    }


# ---------------------------------------------------------------------------
# Tool 2: Check Fiscal Period
# ---------------------------------------------------------------------------

async def tool_check_fiscal_period(
    db: AsyncSession,
    company_id: uuid.UUID,
    date_str: str,
) -> Dict[str, Any]:
    """Check fiscal calendar period status (open, locked, closed) for financial safety."""
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        raise ValueError(f"Invalid date format '{date_str}', expected YYYY-MM-DD.")

    try:
        period = await FiscalCalendarService.get_period_for_date(db, company_id, target_date)
        is_year_closed = bool(period.fiscal_year and period.fiscal_year.is_closed)
        is_open = (period.state == "open") and not is_year_closed
        return {
            "period_id": str(period.id),
            "code": period.code,
            "name": period.name,
            "state": period.state,
            "date_from": str(period.date_from),
            "date_to": str(period.date_to),
            "is_open": is_open,
            "is_year_closed": is_year_closed,
            "can_post": is_open,
        }
    except FiscalPeriodNotFoundException:
        return {
            "period_id": None,
            "state": "not_found",
            "is_open": False,
            "can_post": False,
            "message": f"No fiscal calendar period configured covering {date_str}.",
        }


# ---------------------------------------------------------------------------
# Tool 3: Get Party Profile
# ---------------------------------------------------------------------------

async def tool_get_party_profile(
    db: AsyncSession,
    company_id: uuid.UUID,
    party_id: str,
) -> Dict[str, Any]:
    """Retrieve full partner dossier, contacts, credit limit, and hierarchy."""
    party_uuid = uuid.UUID(party_id)
    party_dto = await PartyService.get_party(db, company_id, party_uuid)
    return party_dto.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Tool 4: Calculate Pricing
# ---------------------------------------------------------------------------

async def tool_calculate_pricing(
    db: AsyncSession,
    company_id: uuid.UUID,
    price_list_id: str,
    items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Evaluate commercial pricing rules, volume breaks, and discounts."""
    pl_uuid = uuid.UUID(price_list_id)
    results = []

    for item in items:
        res_model = item.get("res_model", "Product")
        res_id = uuid.UUID(item["res_id"])
        qty = Decimal(str(item.get("quantity", 1.0)))
        base_p = Decimal(str(item.get("base_price") or 1.0))

        req = PriceEvaluateRequest(
            price_list_id=pl_uuid,
            res_model=res_model,
            res_id=res_id,
            quantity=qty,
            base_price=base_p,
        )
        resp = await PricingService.evaluate_price(db, company_id, req)
        results.append(resp.model_dump(mode="json"))

    return {
        "price_list_id": str(pl_uuid),
        "item_count": len(results),
        "evaluations": results,
    }


# ---------------------------------------------------------------------------
# Tool 5: Calculate Taxes
# ---------------------------------------------------------------------------

async def tool_calculate_taxes(
    db: AsyncSession,
    company_id: uuid.UUID,
    lines: List[Dict[str, Any]],
    fiscal_position_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute multi-jurisdiction taxes, exemptions, and gross/net amounts."""
    fp_uuid = uuid.UUID(fiscal_position_id) if fiscal_position_id else None
    compute_lines = []
    for line in lines:
        price = Decimal(str(line.get("amount") or line.get("price_unit") or 0.0))
        qty = Decimal(str(line.get("quantity", 1.0)))
        disc = Decimal(str(line.get("discount_percentage", 0.0)))
        tax_ids = [uuid.UUID(t) for t in line.get("tax_ids", [])]
        compute_lines.append(
            TaxLineInput(
                price_unit=price,
                quantity=qty,
                discount_percentage=disc,
                tax_ids=tax_ids,
            )
        )

    req = TaxComputeRequest(
        lines=compute_lines,
        fiscal_position_id=fp_uuid,
    )
    resp = await TaxService.compute_taxes(db, company_id, req)
    return resp.model_dump(mode="json")



# ---------------------------------------------------------------------------
# Tool 6: Calculate Payment Terms
# ---------------------------------------------------------------------------

async def tool_calculate_payment_terms(
    db: AsyncSession,
    company_id: uuid.UUID,
    amount: float,
    terms_id: str,
    invoice_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate cash flow installment schedules and due dates."""
    t_uuid = uuid.UUID(terms_id)
    inv_date = datetime.strptime(invoice_date, "%Y-%m-%d").date() if invoice_date else None

    req = ComputePaymentScheduleRequest(
        terms_id=t_uuid,
        total_amount=Decimal(str(amount)),
        invoice_date=inv_date,
    )
    resp = await PaymentTermsService.compute_due_dates(db, company_id, req)
    return resp.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Tool 7: Submit Approval Request
# ---------------------------------------------------------------------------

async def tool_submit_approval_request(
    db: AsyncSession,
    company_id: uuid.UUID,
    res_model: str,
    res_id: str,
    reason: str,
    requested_by_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Submit a record for multi-tier governance sign-off."""
    from modules.base.identity_rbac.models import User

    # Resolve or mock system actor
    user_uuid = uuid.UUID(requested_by_id) if requested_by_id else None
    user = None
    if user_uuid:
        user = await db.get(User, user_uuid)
    if not user:
        # Fetch first admin user in tenant
        stmt = select(User).where(User.company_id == company_id).limit(1)
        user = (await db.execute(stmt)).scalar_one_or_none()

    if not user:
        raise ValueError("Cannot submit approval request without active user in tenant.")

    req_data = ApprovalRequestCreate(
        res_model=res_model,
        res_id=uuid.UUID(res_id),
        summary=reason,
    )
    req = await ApprovalService.submit_request(db, company_id, user, req_data)
    return {
        "request_id": str(req.id),
        "res_model": req.res_model,
        "res_id": str(req.res_id),
        "state": req.state,
        "tier": req.tier,
        "summary": req.summary,
    }


# ---------------------------------------------------------------------------
# Tool 8: Transition Workflow State
# ---------------------------------------------------------------------------

async def tool_transition_workflow_state(
    db: AsyncSession,
    company_id: uuid.UUID,
    res_model: str,
    res_id: str,
    trigger_name: str,
    actor_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a lifecycle state transition trigger on a business entity."""
    from modules.base.identity_rbac.models import User

    actor_uuid = uuid.UUID(actor_id) if actor_id else None
    user = await db.get(User, actor_uuid) if actor_uuid else None
    if not user:
        stmt = select(User).where(User.company_id == company_id).limit(1)
        user = (await db.execute(stmt)).scalar_one_or_none()

    res = await WorkflowService.execute_transition(
        db=db,
        company_id=company_id,
        user=user,
        res_model=res_model,
        record_id=uuid.UUID(res_id),
        trigger_name=trigger_name,
    )
    return res.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Tool 9: Check Resource Availability
# ---------------------------------------------------------------------------

async def tool_check_resource_availability(
    db: AsyncSession,
    company_id: uuid.UUID,
    resource_id: str,
    start_time: str,
    end_time: str,
) -> Dict[str, Any]:
    """Detect booking collisions and capacity availability for a resource."""
    r_uuid = uuid.UUID(resource_id)
    s_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    e_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

    req = CheckAvailabilityRequest(
        resource_id=r_uuid,
        start_time=s_dt,
        end_time=e_dt,
    )
    resp = await ResourceService.check_availability(db, company_id, req)
    return resp.model_dump(mode="json")
