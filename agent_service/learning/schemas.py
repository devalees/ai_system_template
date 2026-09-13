"""
Pydantic Schemas for Human-in-the-Loop (HITL) Correction and Knowledge Distillation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class CorrectionDiffItem(BaseModel):
    """Represents a single corrected field or record from a human reviewer."""
    item_id: str = Field(..., description="Unique identifier of the item or row, e.g. account_number or row_index")
    item_label: str = Field(..., description="Human-readable label or account name, e.g. 'Barclays Bank Overdraft'")
    field: str = Field(..., description="Name of the field modified, e.g. 'classification' or 'tax_rate'")
    ai_original_value: str = Field(..., description="Original incorrect value predicted by the AI")
    human_corrected_value: str = Field(..., description="Corrected ground-truth value chosen by the human accountant")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional row or entity metadata")


class BatchDiffInput(BaseModel):
    """Payload representing a batch of human corrections (e.g. from an edited spreadsheet or table)."""
    domain: str = Field(default="accounting", description="Operational domain, e.g. 'accounting', 'procurement', 'tax'")
    diff_items: List[CorrectionDiffItem] = Field(..., description="List of individual row/item differences")
    reviewer_notes: Optional[str] = Field(default=None, description="Optional high-level note provided by the reviewer")


class DistilledBestPractice(BaseModel):
    """An abstracted, de-identified domain rule distilled from human feedback."""
    is_best_practice: bool = Field(..., description="True if the rule is a reusable industry or domain pattern")
    title: str = Field(..., description="Concise descriptive title, e.g. 'Disambiguating Bank Overdrafts in Liabilities'")
    abstract_rule: str = Field(..., description="De-identified, generalized operational principle")
    scope: Literal["generalized", "project_local"] = Field(..., description="Target scope for memory and sync quarantine")
    category: str = Field(default="accounting_heuristic", description="Domain classification for memory storage")
    rationale: str = Field(..., description="Explanation of why this rule was synthesized from the feedback")
    stripped_entities: List[str] = Field(default_factory=list, description="List of private/company entities removed during distillation")
    suggested_action: str = Field(default="", description="Concrete guidance on how agents should apply this rule")


class DistillationResult(BaseModel):
    """Output contract for knowledge distillation passes."""
    success: bool = Field(..., description="True if distillation completed without errors")
    source_type: Literal["batch_diff", "conversational_rule", "task_friction"] = Field(..., description="Origin of the feedback")
    total_diffs_analyzed: int = Field(default=0, description="Count of corrected items analyzed")
    distilled_practices: List[DistilledBestPractice] = Field(default_factory=list, description="Extracted best practice items")
    saved_memory_ids: List[str] = Field(default_factory=list, description="IDs of memories saved to sqlite-vec memory.db")
    summary: str = Field(..., description="Human-readable overview of what was learned")
