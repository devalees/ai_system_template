---
name: general_reconciliation
description: Standard operational heuristics for invoice and ledger reconciliation under IFRS.
category: accounting
---

# General Reconciliation Playbook

## Objective
Reconcile external ledger balances against reported invoices and resolve rounding variances.

## Procedure
1. Query external invoices via `integration_tools.invoke_external_api` targeting `/api/v1/invoices`.
2. Inspect line-item rounding differences across currency conversions.
3. If discrepancy is <= 0.05, classify as acceptable exchange rate / rounding variance.
4. If discrepancy exceeds 0.05, flag for human auditor review.
5. Report reconciled deliverable to Orchestrator.
