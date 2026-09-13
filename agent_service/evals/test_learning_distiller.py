"""
Golden Benchmark Evaluation Suite: Human-in-the-Loop (HITL) Correction & Best Practice Distillation.

Certifies:
1. Batch Trial Balance diff distillation (Barclays Bank Overdraft, Bank Loan Interest) into generalized IFRS rules.
2. Company-phrased conversational rules (Acme Corp 3-way matching) are de-identified and generalized.
3. Arbitrary internal office preferences remain strictly project_local.
4. Distilled best practices are instantly retrievable by semantic memory recall.
5. FastMCP orchestrator distillation tool endpoints execute deterministically.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

from agent_service.learning.distiller import BestPracticeDistiller
from agent_service.learning.schemas import BatchDiffInput, CorrectionDiffItem
from agent_service.mcp.orchestrator_server import (
    distill_batch_diff,
    distill_conversational_feedback,
)
from agent_service.memory.vector_store import MemoryStore


# =============================================================================
# 1. Batch Diff Distillation Tests (Trial Balance Disambiguation)
# =============================================================================

def test_trial_balance_batch_diff_distillation(tmp_path: Path) -> None:
    """Verifies that human corrections on a Trial Balance are distilled into general accounting rules."""
    test_db = tmp_path / "learning_tb.db"
    distiller = BestPracticeDistiller(db_path=test_db)

    batch_diff = BatchDiffInput(
        domain="accounting",
        diff_items=[
            CorrectionDiffItem(
                item_id="acct_1042",
                item_label="Barclays Bank Overdraft Account",
                field="classification",
                ai_original_value="Cash and Cash Equivalents",
                human_corrected_value="Current Liabilities",
            ),
            CorrectionDiffItem(
                item_id="acct_6019",
                item_label="National Bank Loan Interest & Charges",
                field="classification",
                ai_original_value="Cash and Cash Equivalents",
                human_corrected_value="Finance Expenses",
            ),
        ],
        reviewer_notes="Bank is ambiguous. Overdraft is liability, interest is expense.",
    )

    result = distiller.distill_from_batch_diff(batch_diff)

    assert result.success is True
    assert result.total_diffs_analyzed == 2
    assert len(result.distilled_practices) == 2
    assert len(result.saved_memory_ids) == 2

    # Verify both practices are marked generalized
    for p in result.distilled_practices:
        assert p.is_best_practice is True
        assert p.scope == "generalized"
        assert p.category == "accounting_heuristic"

    # Verify memory store contains the newly learned vectors
    store = MemoryStore(db_path=test_db)
    assert store.count(category="accounting_heuristic") == 2

    recalled = store.recall_similar("How should bank overdraft balances be classified?", top_k=1)
    assert len(recalled) == 1
    assert "Liabilities" in recalled[0]["content"] or "Overdraft" in recalled[0]["content"]
    store.close()


# =============================================================================
# 2. Conversational Best Practice Generalization & De-Identification
# =============================================================================

def test_conversational_company_phrased_rule_generalization(tmp_path: Path) -> None:
    """Verifies that company-specific phrasing is stripped and converted to a global best practice."""
    test_db = tmp_path / "learning_conv.db"
    distiller = BestPracticeDistiller(db_path=test_db)

    raw_input = (
        "In our company Acme Corp, we always require 3-way matching between "
        "Purchase Order, Delivery Note, and Vendor Invoice before issuing payment."
    )

    result = distiller.distill_from_conversational_rule(rule_text=raw_input, domain="procurement")

    assert result.success is True
    practice = result.distilled_practices[0]

    assert practice.is_best_practice is True
    assert practice.scope == "generalized"
    assert practice.category == "procurement_best_practice"

    # Ensure Acme Corp and company phrasing were completely stripped
    assert "Acme Corp" not in practice.abstract_rule
    assert "In our company" not in practice.abstract_rule
    assert "3-way matching" in practice.abstract_rule.lower()


# =============================================================================
# 3. Private Internal Routing Quarantine
# =============================================================================

def test_arbitrary_private_rule_stays_project_local(tmp_path: Path) -> None:
    """Certifies that internal office routing is quarantined as project_local."""
    test_db = tmp_path / "learning_priv.db"
    distiller = BestPracticeDistiller(db_path=test_db)

    raw_input = "Forward all utility bills to Bob in accounting on extension 104."

    result = distiller.distill_from_conversational_rule(rule_text=raw_input, domain="general")

    assert result.success is True
    practice = result.distilled_practices[0]

    assert practice.is_best_practice is False
    assert practice.scope == "project_local"
    assert practice.category == "internal_policy"


# =============================================================================
# 4. FastMCP Tool Execution
# =============================================================================

def test_fastmcp_orchestrator_distill_tool() -> None:
    """Verifies that orchestrator FastMCP tools expose distillation cleanly."""
    res = distill_conversational_feedback(
        feedback_text="Under IFRS, calculate depreciation using the straight-line method.",
        domain="accounting",
    )
    assert res["success"] is True
    assert len(res["distilled_practices"]) == 1
    assert res["distilled_practices"][0]["scope"] == "generalized"
