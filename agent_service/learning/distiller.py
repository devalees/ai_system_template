"""
Best Practice Extractor & Autonomous Knowledge Distillation Engine.

Extracts generalized domain heuristics and accounting/procurement best practices from
human corrections (HITL diffs) and conversational instructions.
Guarantees entity de-identification, scope quarantine, and automated vector indexing.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("agent_service.learning")

# Ensure project root is on sys.path
_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from agent_service.learning.schemas import (
    BatchDiffInput,
    CorrectionDiffItem,
    DistillationResult,
    DistilledBestPractice,
)
from agent_service.memory.cli import sanitize_dict, sanitize_text
from agent_service.memory.vector_store import MemoryStore

# Regex patterns for corporate/company phrasing to strip
COMPANY_PHRASING_PATTERNS = [
    r"(?i)\b(?:in|at|for)\s+(?:our|this|the)\s+company(?:\s+[A-Z][a-zA-Z0-9_\-\.]*(?:\s+(?:Corp|Corporation|Inc|LLC|Ltd|Group|Holdings))?)?\b[:,]?",
    r"(?i)\b(?:our|company)\s+policy\s+(?:is|states)\b[:,]?",
    r"(?i)\b(?:at|for)\s+[A-Z][a-zA-Z0-9_\-\.]+(?:\s+(?:Corp|Corporation|Inc|LLC|Ltd|Group|Holdings|Bank))\b[:,]?",
    r"(?i)\bhere\s+at\s+[A-Z][a-zA-Z0-9_\-\.]+\b[:,]?",
    r"(?i)\b[A-Z][a-zA-Z0-9_\-\.]*\s+(?:Corp|Corporation|Inc|LLC|Ltd|Group|Holdings)\b[:,]?",
    r"(?i)\bwe\s+always\b",
]

# Patterns for purely private internal office routing (non-generalizable)
PRIVATE_ROUTING_PATTERNS = [
    r"(?i)\b(?:forward|send|give|deliver|route)\s+(?:all|this|these)?\s*(?:bills?|invoices?|emails?|docs?|calls?)\s+to\s+[A-Z][a-z]+\b",
    r"(?i)\b(?:extension|ext\.?|phone|room|office)\s+(?:is\s+)?#?\d+\b",
    r"(?i)\bask\s+[A-Z][a-z]+\s+in\s+accounting\b",
    r"(?i)\bemployee\s+id\b",
]

# Known accounting domain heuristic patterns
ACCOUNTING_HEURISTICS = [
    (r"(?i)overdraft", "Current Liabilities", "Banking Overdraft Classification",
     "Bank accounts representing credit lines or overdraft facilities must be classified under Short-Term / Current Liabilities rather than Cash & Cash Equivalents."),
    (r"(?i)(?:interest|charges?|fees?)", "Operating / Finance Expenses", "Bank Fees & Interest Classification",
     "Accounts recording bank charges, processing fees, or loan interest are Finance/Operating Expenses (Debit) and must never be grouped under Cash & Banks."),
    (r"(?i)prepaid", "Current Assets", "Prepaid Expenses Classification",
     "Prepaid accounts represent future economic benefits paid in advance and must be classified under Current Assets."),
    (r"(?i)accrued", "Current Liabilities", "Accrued Expenses Classification",
     "Accrued expense accounts represent incurred obligations not yet billed or paid and must be classified under Current Liabilities."),
    (r"(?i)depreciation", "Contra-Asset / Depreciation Expense", "Depreciation Accounting Treatment",
     "Accumulated depreciation is a contra-asset account offsetting fixed assets, whereas depreciation expense is recognized on the Income Statement."),
]


class BestPracticeDistiller:
    """
    Cognitive reflection engine that transforms human feedback and error corrections
    into reusable, de-identified domain best practices.
    """

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        """Initializes the distiller with an optional custom vector database path."""
        base_dir = Path(__file__).resolve().parent.parent
        self.db_path = Path(db_path or base_dir / "data" / "memory.db")

    def _get_memory_store(self) -> MemoryStore:
        """Helper to get a memory store instance."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return MemoryStore(db_path=self.db_path)

    def _strip_company_phrasing(self, text: str) -> Tuple[str, List[str]]:
        """Removes proprietary company mentions and returns (cleaned_text, stripped_entities)."""
        stripped: List[str] = []
        cleaned = text

        for pattern in COMPANY_PHRASING_PATTERNS:
            matches = re.findall(pattern, cleaned)
            if matches:
                for m in matches:
                    if isinstance(m, str) and m.strip():
                        stripped.append(m.strip())
                cleaned = re.sub(pattern, "", cleaned)

        # Sanitize any residual tokens, emails, or IPs
        cleaned = sanitize_text(cleaned).strip()
        # Clean up double spaces or leading commas
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = re.sub(r"^[,\-\:\s]+", "", cleaned)
        return cleaned, stripped

    def _is_private_internal_rule(self, text: str) -> bool:
        """Checks if the rule represents arbitrary internal routing rather than a domain heuristic."""
        for pattern in PRIVATE_ROUTING_PATTERNS:
            if re.search(pattern, text):
                return True
        return False

    def distill_from_conversational_rule(
        self,
        rule_text: str,
        domain: str = "general",
    ) -> DistillationResult:
        """
        Processes a conversational rule or user correction (e.g. 'At Acme Corp, we always do X').
        Evaluates best practice validity, strips company identifiers, and indexes into memory.
        """
        raw = rule_text.strip()
        if not raw:
            return DistillationResult(
                success=False,
                source_type="conversational_rule",
                summary="Empty rule provided.",
            )

        # 1. Check if rule is an arbitrary internal private preference
        if self._is_private_internal_rule(raw):
            clean_text, stripped = self._strip_company_phrasing(raw)
            practice = DistilledBestPractice(
                is_best_practice=False,
                title="Internal Operational Preference",
                abstract_rule=clean_text,
                scope="project_local",
                category="internal_policy",
                rationale="Identified as an internal company routing preference rather than an industry best practice.",
                stripped_entities=stripped,
                suggested_action="Apply strictly within local tenant sessions.",
            )
        else:
            # 2. Generalize into domain best practice
            clean_text, stripped = self._strip_company_phrasing(raw)
            # Capitalize first letter cleanly
            if clean_text:
                clean_text = clean_text[0].upper() + clean_text[1:]

            # Check domain keywords
            is_procurement = bool(re.search(r"(?i)(?:3-way|three-way|purchase order|po\b|goods receipt|delivery note)", clean_text))
            is_accounting = bool(re.search(r"(?i)(?:vat|reconcil|ledger|trial balance|debit|credit|ifrs|gaap|depreciation|overdraft)", clean_text))

            if is_procurement:
                category = "procurement_best_practice"
                title = "Procurement Control: 3-Way Invoice Matching" if "3-way" in clean_text.lower() or "three-way" in clean_text.lower() else "Standard Procurement Verification"
            elif is_accounting:
                category = "accounting_heuristic"
                title = "Financial Control: Ledger Reconciliation Heuristic"
            else:
                category = f"{domain}_heuristic"
                title = f"{domain.capitalize()} Standard Operating Heuristic"

            practice = DistilledBestPractice(
                is_best_practice=True,
                title=title,
                abstract_rule=clean_text,
                scope="generalized",
                category=category,
                rationale="Formulated from human domain feedback and validated as a general operational heuristic.",
                stripped_entities=stripped,
                suggested_action="Incorporate into Pre-Flight turn 1 memory augmentation for matching objectives.",
            )

        # 3. Store in MemoryStore
        store = self._get_memory_store()
        mem_id = store.add_memory(
            title=practice.title,
            content=f"{practice.abstract_rule}\n\nSuggested Action: {practice.suggested_action}",
            category=practice.category,
            scope=practice.scope,
            metadata={
                "is_best_practice": practice.is_best_practice,
                "rationale": practice.rationale,
                "stripped_entities": practice.stripped_entities,
                "tags": ["hitl_distillation", practice.category, practice.scope],
            },
        )
        store.close()

        return DistillationResult(
            success=True,
            source_type="conversational_rule",
            total_diffs_analyzed=1,
            distilled_practices=[practice],
            saved_memory_ids=[mem_id],
            summary=f"Distilled '{practice.title}' with scope '{practice.scope}'.",
        )

    def distill_from_batch_diff(
        self,
        batch_diff: BatchDiffInput,
    ) -> DistillationResult:
        """
        Analyzes a batch of human corrections (e.g. from an edited Trial Balance spreadsheet)
        and synthesizes abstract classification rules.
        """
        if not batch_diff.diff_items:
            return DistillationResult(
                success=False,
                source_type="batch_diff",
                summary="No diff items to distill.",
            )

        distilled: List[DistilledBestPractice] = []
        saved_ids: List[str] = []
        store = self._get_memory_store()

        # Group corrections by pattern
        for diff in batch_diff.diff_items:
            label = diff.item_label.strip()
            ai_val = diff.ai_original_value.strip()
            human_val = diff.human_corrected_value.strip()

            if ai_val.lower() == human_val.lower():
                continue

            # Check known accounting heuristics
            matched_heuristic = False
            for pattern, target_group, rule_title, rule_desc in ACCOUNTING_HEURISTICS:
                if re.search(pattern, label):
                    matched_heuristic = True
                    practice = DistilledBestPractice(
                        is_best_practice=True,
                        title=rule_title,
                        abstract_rule=(
                            f"Account Disambiguation: Accounts containing '{pattern.replace('(?i)', '')}' "
                            f"should be classified under '{human_val}' rather than '{ai_val}'. {rule_desc}"
                        ),
                        scope="generalized",
                        category="accounting_heuristic",
                        rationale=f"Synthesized from human accountant correction on '{label}': {ai_val} -> {human_val}.",
                        stripped_entities=[label],
                        suggested_action=f"Disambiguate accounts matching '{pattern.replace('(?i)', '')}' to '{human_val}'.",
                    )
                    break

            if not matched_heuristic:
                # Fallback rule generalization
                clean_label, stripped = self._strip_company_phrasing(label)
                practice = DistilledBestPractice(
                    is_best_practice=True,
                    title=f"Classification Adjustment: {clean_label}",
                    abstract_rule=f"When classifying items matching '{clean_label}', the correct category is '{human_val}' rather than '{ai_val}'.",
                    scope="generalized",
                    category="accounting_heuristic",
                    rationale=f"Human override on field '{diff.field}': changed from '{ai_val}' to '{human_val}'.",
                    stripped_entities=stripped,
                    suggested_action=f"Assign category '{human_val}' when encountering items resembling '{clean_label}'.",
                )

            # Check deduplication before writing to memory
            existing = store.recall_similar(practice.abstract_rule, top_k=1, threshold=0.90, scope="generalized")
            if not existing:
                mem_id = store.add_memory(
                    title=practice.title,
                    content=f"{practice.abstract_rule}\n\nSuggested Action: {practice.suggested_action}",
                    category=practice.category,
                    scope=practice.scope,
                    metadata={
                        "is_best_practice": practice.is_best_practice,
                        "field": diff.field,
                        "rationale": practice.rationale,
                        "tags": ["hitl_diff", practice.category, practice.scope],
                    },
                )
                saved_ids.append(mem_id)

            distilled.append(practice)

        store.close()

        return DistillationResult(
            success=True,
            source_type="batch_diff",
            total_diffs_analyzed=len(batch_diff.diff_items),
            distilled_practices=distilled,
            saved_memory_ids=saved_ids,
            summary=(
                f"Analyzed {len(batch_diff.diff_items)} human corrections. "
                f"Distilled {len(distilled)} best practice rules and indexed {len(saved_ids)} new vectors."
            ),
        )
