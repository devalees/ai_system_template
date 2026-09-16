# Frontend Platform & React Standards (Zero-Bloat & Wireframe-First)

A strict, high-performance architectural standard for building modular, metadata-driven frontend enterprise applications with zero dependency bloat, disciplined wireframe-first design, and seamless synchronization with the Sovereign backend.

---

## 1. Core Architecture & Tech Stack

* **Runtime & Bundler**: **React 19+ + Vite + TypeScript (Single-Page Application)**.
  * Native browser ES Modules (ESM) for instant development startup (<200ms) and sub-15ms Hot Module Replacement (HMR).
  * Pure client-side rendering (CSR) eliminating server-side hydration mismatches when consuming dynamic metadata schemas.
  * Minimal Docker packaging: ultra-lean Alpine Nginx static container (<25MB image size, <15MB RAM).
* **Architecture Symmetry**: Symmetrical to the backend Kernel architecture:
  * `src/kernel/`: Core routing, API client, auth/2FA, RBAC, theme provider, and event bus.
  * `src/ui/`: Reusable primitives, design tokens, resizable splitters, and dynamic schema renderers.
  * `src/modules/`: Base UI modules (`chatter`, `documents`, `settings`) and business domain modules (`sales`, `accounting`, `purchases`).

---

## 2. Zero-Bloat Dependency-Minimalist Protocol (Strict)

Frontend fatigue and supply-chain bloat are strictly forbidden. The entire frontend platform must maintain the absolute minimum number of NPM dependencies:

* **Direct Dependencies Cap**: Keep direct runtime dependencies strictly under **5–7 packages** in `package.json`.
* **Zero Heavy Component Libraries**: NEVER install bloated UI component libraries (MUI, Ant Design, Chakra). Build lean, accessible components on standard HTML5 elements.
* **Native HTML5 Drag & Drop**: Implement Kanban boards and Studio canvas using native HTML5 Drag and Drop APIs (`draggable`, `onDragStart`, `onDrop`) instead of multi-megabyte libraries like `@dnd-kit`.
* **Native Pointer Events for Splitters**: Implement fluid resizable sidebars and splitters using standard browser Pointer Events and CSS Flexbox instead of third-party splitter packages.
* **Native Form State & HTML5 Controls**: Bind dynamic form inputs directly to standard React state hooks with HTML5 semantic controls (`input`, `select`, `textarea`, native `<input type="date">`), eliminating heavy form libraries (`react-hook-form`, `formik`, `yup`).
* **Browser Fetch over Axios**: Wrap the native `window.fetch` API in a lightweight typed client class handling JWT headers and error interception.

---

## 3. The Unified Layout Architecture ("1 Invariant Shell + 4 Canvases")

Rather than reinventing ad-hoc layouts for each module, the entire ERP follows a unified architectural blueprint:

### A. The Invariant Master Shell (Identical across 100% of screens)
1. **Global App Header (Top 48px)**:
   * App Switcher (Drawer/Launcher for Sales, Accounting, Purchases, Settings).
   * Company Switcher (`X-Company-ID` context).
   * Global Command Bar (`Cmd+K` universal search).
   * User Profile, Notifications bell, and Theme toggle.
2. **Module Sub-Navigation (Contextual Sub-Menu)**:
   * Dynamically adapts to the active app (e.g. Sales: `Orders | To Invoice | Products | Reporting | Configuration`).
3. **Context & Action Control Bar**:
   * Left: Breadcrumb path (`Sales / Orders / SO-001`) + Primary action buttons (`New`, `Confirm`, `Print`).
   * Right: Universal Search / Filter box + View-type switcher (`List Table`, `Kanban`, `Pivot/Report`).

### B. The 4 Polymorphic Viewport Canvases
1. **Explorer Canvas (List / Table / Kanban)**: Default landing view for any entity with dense grids, status badges, and bulk actions.
2. **Document Canvas (Record / Form Sheet)**: Auto-adapting form view (compact 2-column or heavy tabbed sheet with child lines, plus optional Chatter/Activity side-dock).
3. **Reporting & Analytics Canvas**: Hierarchical ledger grids (P&L, Balance Sheet, Trial Balance) and KPI charts.
4. **Settings & Hub Canvas**: Left-hand category index + right-hand cards rendering Section 6.7 typed `ModuleSettings`.

---

## 4. Mandatory Wireframe-First Development Protocol (Skeleton Agreement)

To prevent AI "Big-Bang" code dumps and maintain complete design control:

1. **Skeleton / Wireframe Layout Agreement First**:
   * Before applying full CSS styling, colors, animations, or detailed components to ANY new screen or major layout, the agent MUST present a **clean structural wireframe / layout skeleton**.
   * Wireframes must be implemented with simple HTML boxes and visible borders (`border: 1px dashed/solid`), clearly labeling each structural zone (e.g. `[App Switcher]`, `[Breadcrumbs & Actions]`, `[Document Header]`, `[Line Items Table]`, `[Optional Chatter Dock]`).
2. **Review & Approval Gate**:
   * The user reviews the layout skeleton directly in the browser (`http://localhost:5173`) or via screenshot.
   * Only after the user approves the spatial arrangement, boundaries, and zones does the agent proceed to detailed visual styling and component implementation.
3. **No Unreviewed Structural Code**:
   * Structural layout changes must never be bundled silently into complex business logic tasks.

---

## 5. Design Aesthetics, Theming & Styling Standard

* **Pure Vanilla CSS & CSS Variables (Design Tokens)**:
  * NEVER use TailwindCSS or runtime CSS-in-JS (Emotion, Styled-Components).
  * Define all design tokens as CSS Custom Properties on `:root` in `index.css`.
* **Theme Presets (Aligned with Backend `UIThemeSettings`)**:
  * `sovereign-dark`: Glassmorphic dark theme, subtle borders, glowing accent rings, dark card surfaces.
  * `enterprise-light`: High-contrast, clean corporate light mode.
  * `high-density-erp`: Compact accounting theme optimized for data grids and rapid numeric data entry.
  * `nordic-minimal`: Soft-contrast modern minimalist dark theme.
* **Fluid Resizable Split-Panel Sidebar**:
  * Form views support resizable vertical split sidebars (default 65% primary form, 35% dock for Chatter and Activity feeds).
  * User-dragged splitter ratios must persist via backend `PUT /api/v1/ui/preferences/{res_model}/{view_type}`.

---

## 6. Multi-Company Context & API Protocol

* **Dual-Header Propagation**:
  * Every mutation (`POST`, `PUT`, `DELETE`) must send `X-Company-ID: <active_company_id>` for write isolation.
  * Aggregated multi-company read queries (`GET`) must send `X-Company-IDs: <id1>,<id2>` when multi-company view is activated.
* **Authentication & 2FA Lifecycle**:
  * Standard Bearer token authentication via `Authorization: Bearer <jwt>`.
  * Support intermediate 2FA challenge handshake: if login returns `mfa_required: true`, route to TOTP / recovery challenge before establishing session.

---

## 7. Disciplined Task Execution, Active Plan Sync & Atomic Git Commits

Frontend development strictly adheres to the same operational discipline as the backend (`git_and_task_workflow.md`):

1. **Persistent Implementation Plan (`docs/plans/active_plan.md`)**:
   * The Active Plan is strictly cumulative and append-only.
   * Every frontend phase and stage must be recorded with clear deliverables.
   * Immediately update `active_plan.md` upon completing and verifying each sub-task, marking `[x]` and recording the commit hash.
2. **Empirical Verification Before Commits**:
   * Always verify changes empirically on the live Vite development server before committing.
   * Zero console errors, zero unhandled promise rejections, and zero React key warnings.
3. **Atomic Git Commits After Every Sub-Task**:
   * Execute `git add` and `git commit` immediately after completing each distinct, working sub-task.
   * Follow conventional commits: `feat(frontend-...)`, `fix(frontend-...)`, `docs(frontend-...)`, `refactor(frontend-...)`.
