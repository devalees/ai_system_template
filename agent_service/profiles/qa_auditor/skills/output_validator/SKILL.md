---
name: output_validator
description: Performs rigorous syntax verification, compliance inspection, and quality scoring on deliverables for the QA Auditor review gate.
---

# Output Validator Skill

Used by the `qa_auditor` profile during the Kanban review stage (`hermes kanban request-review`) to empirically validate code, data payloads, and documents before sign-off.

## Capabilities
1. **Multi-Format Syntax Validation**:
   - Python files: Compiles AST to catch syntax and indentation errors.
   - JSON & YAML: Validates parsing integrity and schema correctness.
   - Markdown: Checks heading structures, malformed code fences, and links.
2. **Defect & Placeholder Trapping**:
   - Scans for unfinished placeholders (`TODO`, `FIXME`, `CHANGEME`, stubbed passes).
   - Scans for hardcoded credential leaks (API keys, secret tokens, private keys).
3. **Automated Verdict Generation & Django Review Gate**:
   - Scores deliverable quality on a 0-100 scale.
   - Emits an authoritative verdict (`APPROVED` vs `CHANGES_REQUESTED`).
   - Transmits verdict, quality score, and defect notes directly to Django REST review gate (`POST /api/tasks/<id>/submit-verdict/`) when invoked with `--submit --task-id <UUID>`.

## Usage
```bash
# Dry-run audit of file or directory
python /workspace/profiles/qa_auditor/skills/output_validator/run.py --target /workspace/path/to/file_or_dir

# Output raw JSON
python /workspace/profiles/qa_auditor/skills/output_validator/run.py --target /workspace/path/to/file_or_dir --json

# Direct review submission to Django review gate
python /workspace/profiles/qa_auditor/skills/output_validator/run.py --target /workspace/path/to/file_or_dir --task-id <TASK_UUID> --submit [--notes "Custom feedback"]
```

