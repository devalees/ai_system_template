# Sovereign Platform Workspace Guidelines

This repository follows standard Antigravity customization rules located in `.agents/rules/`:

1. **Coding & Communication Standards**: [`coding_and_communication_standards.md`](file:///home/ehab/.gemini/config/rules/coding_and_communication_standards.md)
2. **Git & Task Execution Protocol**: [`git_and_task_workflow.md`](file:///home/ehab/.gemini/config/rules/git_and_task_workflow.md)
3. **LLM Wiki Maintenance Protocol**: [`llm_wiki.md`](file:///home/ehab/.gemini/config/rules/llm_wiki.md)
4. **FastAPI Development & Postman Sync Protocol**: [`fastapi_standards.md`](file:///home/ehab/.gemini/config/rules/fastapi_standards.md)
5. **Frontend Platform & React Standards**: [`frontend_standards.md`](file:///home/ehab/.gemini/config/rules/frontend_standards.md) — Strict React 19 + Vite + TypeScript Single-Page Application (SPA) architecture with zero dependency bloat (cap under 7 packages), metadata-driven dynamic schema rendering (`ui_schema`), pure Vanilla CSS design tokens (`UIThemeSettings`), native HTML5 controls/drag-and-drop, fluid splitters, and multi-company context propagation.
6. **Modular Settings & Configuration Standard**: Section 6.7 in [`architecture.md`](file:///home/ehab/Desktop/economy_editor/docs/ai_wiki/architecture.md) — All operational policies, switches, thresholds, and business rules MUST be declared as typed Module Settings (`ModuleSettings` JSONB + Redis) with rich metadata (`title`, `description`, `type`, `default`, `options`). NEVER add ad-hoc boolean flags or policy columns directly to `Company` or other core models.
7. **Event-Driven Automation & Action Handler Protocol**: Section 6.10 in [`architecture.md`](file:///home/ehab/Desktop/economy_editor/docs/ai_wiki/architecture.md) — NEVER hardcode cross-module business side-effects, notification dispatches, or state-change emails directly inside API route handlers. Implement reusable business capabilities as typed `BaseActionHandler` classes with Pydantic configuration schemas in the appropriate module, and declare business workflows as declarative `AutomatedAction` seed fixtures (`fixtures.py`).


