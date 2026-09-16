"""Pydantic schemas and contracts for the Sovereign FastMCP Dynamic Tool Bridge."""

import uuid
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field


class MCPToolDefinition(BaseModel):
    """Metadata describing an exposed FastMCP tool for AI Agent reflection."""

    name: str = Field(..., description="Unique tool identifier name")
    description: str = Field(..., description="Semantic purpose and instructions for agent tool selection")
    parameters: Dict[str, Any] = Field(..., description="JSON Schema object describing required and optional arguments")
    category: str = Field(default="business_capability", description="Functional category (e.g. accounting, commercial, workflow)")
    module: str = Field(..., description="Originating base module")


class MCPToolCallRequest(BaseModel):
    """Unified invocation payload for FastMCP dynamic tool execution."""

    tool: str = Field(..., description="Target tool identifier (e.g. 'calculate_pricing', 'check_fiscal_period')")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Dictionary of typed keyword arguments")
    company_id: Optional[uuid.UUID] = Field(None, description="Optional tenant context override (defaults to session company)")


class MCPToolCallResponse(BaseModel):
    """Standardized result envelope returned by FastMCP tool execution."""

    tool: str
    status: str = Field(..., description="'success' | 'error'")
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: float = 0.0


# ---------------------------------------------------------------------------
# Specific Core Tool Input Schemas
# ---------------------------------------------------------------------------

class QueryRecordsInput(BaseModel):
    model: str = Field(..., description="Model name or table name (e.g. 'Party', 'Contract', 'WorkItem', 'Resource', 'Sequence')")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Key-value equality filters or query criteria")
    limit: int = Field(default=50, ge=1, le=200, description="Max records to return")


class CheckFiscalPeriodInput(BaseModel):
    date: str = Field(..., description="Target transaction date formatted as YYYY-MM-DD")


class GetPartyProfileInput(BaseModel):
    party_id: str = Field(..., description="UUID of the customer, vendor, or parent entity")


class PricingItemInput(BaseModel):
    res_model: str = Field(default="Product", description="Target entity type")
    res_id: str = Field(..., description="UUID of the product or item")
    quantity: float = Field(default=1.0, gt=0, description="Quantity being evaluated")
    base_price: Optional[float] = Field(default=None, description="Optional catalog base price override")


class CalculatePricingInput(BaseModel):
    price_list_id: str = Field(..., description="UUID of the active PriceList")
    items: List[PricingItemInput] = Field(..., description="List of items/products to evaluate")


class TaxLineInput(BaseModel):
    amount: float = Field(..., description="Line net or gross amount")
    tax_ids: List[str] = Field(..., description="List of Tax UUIDs applying to this line")


class CalculateTaxesInput(BaseModel):
    lines: List[TaxLineInput] = Field(..., description="Invoice or order lines to compute taxes for")
    fiscal_position_id: Optional[str] = Field(default=None, description="Optional TaxFiscalPosition UUID for tax mapping/exemptions")


class CalculatePaymentTermsInput(BaseModel):
    amount: float = Field(..., gt=0, description="Total invoice or contract amount to partition into installments")
    terms_id: str = Field(..., description="UUID of the PaymentTerms definition")
    invoice_date: Optional[str] = Field(default=None, description="Optional base invoice date (YYYY-MM-DD), defaults to today")


class SubmitApprovalRequestInput(BaseModel):
    res_model: str = Field(..., description="Target model (e.g. 'Contract', 'PaymentTransaction', 'WorkItem')")
    res_id: str = Field(..., description="UUID of the record requiring sign-off")
    reason: str = Field(..., description="Business justification for approval")
    requested_by_id: Optional[str] = Field(default=None, description="Optional user UUID requesting approval")


class TransitionWorkflowStateInput(BaseModel):
    res_model: str = Field(..., description="Target record model name (e.g. 'Contract', 'WorkItem')")
    res_id: str = Field(..., description="UUID of the target record")
    trigger_name: str = Field(..., description="Workflow transition trigger (e.g. 'confirm', 'activate', 'submit', 'close')")
    actor_id: Optional[str] = Field(default=None, description="Optional user UUID initiating transition")


class CheckResourceAvailabilityInput(BaseModel):
    resource_id: str = Field(..., description="UUID of the Resource (human, equipment, space)")
    start_time: str = Field(..., description="Booking start timestamp (ISO 8601, e.g. '2026-10-01T09:00:00Z')")
    end_time: str = Field(..., description="Booking end timestamp (ISO 8601, e.g. '2026-10-01T17:00:00Z')")
