# System Architecture: Sovereign Modular Frontend Platform

A production-grade, 100% sovereign, zero-bloat, and metadata-driven frontend enterprise application platform built with **React 19**, **Vite**, and **TypeScript**. Symmetrically mirrors the backend Kernel architecture, consumes declarative UI schemas, enforces pure Vanilla CSS design tokens, and operates under a strict wireframe-first development protocol.

- **Repository**: `devalees/ai_system_template`
- **Active Branch**: `main`
- **Active Implementation Plan**: [`docs/plans/active_plan.md`](file:///home/ehab/Desktop/economy_editor/docs/plans/active_plan.md)
- **Backend Architecture Reference**: [`docs/ai_wiki/architecture.md`](file:///home/ehab/Desktop/economy_editor/docs/ai_wiki/architecture.md)
- **Frontend Standards Rule**: [`frontend_standards.md`](file:///home/ehab/.gemini/config/rules/frontend_standards.md)

---

## 1. Technical Stack & Infrastructure Footprint

* **Runtime & Framework**: **React 19+ + TypeScript + Vite (Single-Page Application)**.
  * Native browser ES Modules (ESM) delivering sub-15ms Hot Module Replacement (HMR) and instantaneous dev server startup (<200ms).
  * Pure Client-Side Rendering (CSR) eliminating server-side hydration mismatches when parsing dynamic metadata schemas.
* **Styling & Theming**: **Pure Vanilla CSS & CSS Custom Properties (Design Tokens)**.
  * **Zero TailwindCSS, zero CSS-in-JS (Emotion / Styled-Components)**.
  * Dynamic theme switching applied via CSS variables directly on `:root`.
* **Zero-Bloat Dependency Budget**:
  * Strict cap: direct runtime dependencies in `package.json` must remain under **5 to 7 packages**.
  * Native browser standards prioritized over NPM libraries (Fetch, Pointer Events, HTML5 Drag & Drop, HTML5 semantic form controls).
* **Containerization & Deployment**:
  * Compiled into static assets (`dist/`) and served via an ultra-lean **Alpine Nginx Docker container**.
  * RAM footprint: $<15\text{MB}$ RAM (compared to ~150–300 MB for Node.js SSR).
  * Container Image size: $<25\text{MB}$.
  * Host Port: `3000` (Production Nginx) / `5173` (Vite Dev Server).

---

## 2. Directory Architecture & Layer Symmetry

The frontend platform directly mirrors the backend's `Kernel -> Base Modules -> Pluggable Apps` structure:

```
economy_editor/
├── frontend/
│   ├── index.html                   # Static HTML entry point with zero-FCP splash loader
│   ├── package.json                 # Minimalist dependencies (<7 runtime packages)
│   ├── tsconfig.json                # Strict TypeScript configuration with path aliases
│   ├── vite.config.ts               # Vite configuration with API reverse-proxy rules
│   ├── Dockerfile                   # Multi-stage build (Node build -> Alpine Nginx)
│   ├── nginx.conf                   # High-performance SPA routing & caching rules
│   └── src/
│       ├── main.tsx                 # React root mount
│       ├── index.css                # CSS Design tokens (:root variables) & reset
│       │
│       ├── kernel/                  # Platform Core (Invariants)
│       │   ├── api/                 # Typed Fetch client, error handling, header injection
│       │   ├── auth/                # Session lifecycle, token storage, 2FA challenge
│       │   ├── context/             # Multi-company context (X-Company-ID / X-Company-IDs)
│       │   ├── rbac/                # Permission checks & Field-Level Access Control (FLAC)
│       │   ├── theme/               # UIThemeSettings consumer & dynamic theme switcher
│       │   ├── router/              # Client-side router & route guard engine
│       │   └── events/              # Lightweight pub/sub event bus
│       │
│       ├── ui/                      # Design System & Dynamic Schema Renderers
│       │   ├── tokens/              # Theme token definitions (sovereign-dark, enterprise-light)
│       │   ├── primitives/          # Lean HTML5 wrappers (Button, Input, Badge, Dialog)
│       │   ├── layout/              # Shell components:
│       │   │   ├── MasterShell.tsx  # Outer Frame (Header, Sub-Nav, Control Bar)
│       │   │   ├── TopHeader.tsx    # App Switcher, Company Switcher, Cmd+K, Profile
│       │   │   ├── SubNav.tsx       # Contextual Module Navigation
│       │   │   └── ControlBar.tsx   # Breadcrumbs, Action Buttons, Universal Filter
│       │   ├── splitter/            # Fluid Resizable Split-Panel (35% to 100%)
│       │   └── engine/              # Dynamic Schema Renderers:
│       │       ├── DynamicForm.tsx   # Renders FormViewSchema (Tabs, Sections, Widgets)
│       │       ├── DynamicGrid.tsx   # Renders ListViewSchema (Data table, Sort, Widths)
│       │       ├── DynamicKanban.tsx # Renders KanbanViewSchema (Stage columns, Drag & Drop)
│       │       └── DynamicReport.tsx # Renders Financial Ledgers & Pivot grids
│       │
│       └── modules/                 # Modular Business Domains
│           ├── base/
│           │   ├── chatter/         # Docked Chatter & Activity feed sidebar
│           │   ├── documents/       # Document attachment drawer
│           │   ├── settings/        # Section 6.7 Typed Module Settings form
│           │   └── identity/        # User profile, password change, 2FA setup
│           └── apps/
│               ├── sales/           # Sales Orders custom workflow actions
│               ├── purchases/       # Purchase Orders & PO approvals
│               └── accounting/      # Journal moves, invoices & ledger views
```

---

## 3. The Universal Unified Layout Architecture ("1 Shell + 4 Canvases")

To maintain total visual harmony and eliminate ad-hoc layout fragmentation, all screens across all business modules conform to a strict two-tier layout hierarchy:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. GLOBAL APP HEADER (Company Switcher | App Switcher | Global Search Cmd+K | Profile)  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 2. MODULE SUB-NAVIGATION (App-specific menus: e.g. Orders | Invoicing | Reporting)     │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 3. CONTEXT & ACTION CONTROL BAR (Breadcrumbs | Action Buttons | Universal Search Filter)│
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│                                                                                        │
│                               4. THE ACTIVE CANVAS                                     │
│                     (Renders one of the 4 Universal View Types)                        │
│                                                                                        │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Tier 1: The Invariant Master Shell
1. **Global App Header (Top 48px)**:
   * **App Switcher** (Top-Left): 1-click modal drawer launching any installed business application (Sales, Accounting, Purchases, Inventory, Settings).
   * **Company Switcher**: Clearly displays the active operating company (e.g. `Acme Corp HQ`), providing instant multi-company workspace switching via `POST /api/v1/identity_rbac/auth/switch-company`.
   * **Universal Command Bar** (`Cmd+K`): Instant fuzzy search across records, documents, partners, and settings.
   * **User & Utilities Hub** (Top-Right): Notification bell, Theme selector, and User Profile menu.
2. **Module Sub-Navigation (Contextual Horizontal Menu Bar)**:
   * Dynamically reflects the active module:
     * **Sales**: `[ Quotations | Orders | Customers | To Invoice | Products | Reporting | Configuration ]`
     * **Accounting**: `[ Dashboard | Customers | Vendors | Accounting Entries | Financial Reports | Configuration ]`
     * **Purchases**: `[ Requests for Quotation | Purchase Orders | Vendors | Products | Reporting | Configuration ]`
3. **Context & Action Control Bar**:
   * **Left (Context & Actions)**: Hierarchical breadcrumbs (`Sales / Orders / SO-0042`) and primary lifecycle action buttons (`New`, `Confirm`, `Print`, `Cancel`).
   * **Right (Filters & Views)**: Universal Search / Filter input with filter chips, Group By dropdown, and **View Switcher** icons (`List Table`, `Kanban`, `Pivot/Report`).

---

### 3.2 Tier 2: The 4 Polymorphic Viewport Canvases
The viewport area below the Control Bar is polymorphic and exclusively renders one of four standard canvases:

#### Canvas 1: The Explorer Canvas (List / Table / Kanban)
* **Purpose**: Default landing page for any entity.
* **Capabilities**:
  * Dense, high-performance data table with selectable rows for bulk operations.
  * Sticky column headers with click-to-sort and draggable column borders for pixel-width resizing.
  * Toggle to Kanban view preserving search and active filters.
  * Pagination and infinite scrolling support.

#### Canvas 2: The Document Canvas (Record / Form Sheet)
* **Purpose**: Detailed single-record editing and lifecycle progression.
* **Structure**:
  * **Status Ribbon**: Visual state progression (`Draft` $\rightarrow$ `Sent` $\rightarrow$ `Confirmed` $\rightarrow$ `Done`).
  * **Document Sheet**: White card sheet container mimicking a physical business document:
    * Top section: Key identifiers, partner selection, date, currency.
    * Bottom section: Notebook tabs (`Order Lines`, `Other Info`, `Accounting`, `Notes`).
  * **Optional Docked Sidebar**: Fluid resizable split-panel (35% to 100%) housing docked Chatter, Activity timeline, and Document attachments. If Chatter is disabled for the model, the Document Sheet centers elegantly in full width.

#### Canvas 3: The Financial & Reporting Canvas
* **Purpose**: Multi-column hierarchical ledger reports (P&L, Balance Sheet, Trial Balance, Aging).
* **Capabilities**:
  * Expandable/collapsible account hierarchy trees.
  * Period comparison filters (e.g. `2026 Q1 vs 2025 Q1`).
  * Export options (Excel, CSV, PDF).
  * Interactive Pivot grids and summary KPI cards.

#### Canvas 4: The Settings & Configuration Canvas
* **Purpose**: Module settings management compliant with Section 6.7 (`ModuleSettings`).
* **Structure**:
  * Left-hand vertical tab index (`General`, `Invoicing Policy`, `Payment Terms`, `Security`).
  * Right-hand card layout dynamically rendering typed Pydantic fields (switches, numeric limits, select dropdowns, secrets) fetched from `/api/v1/settings/{module}`.

---

## 4. Mandatory Wireframe-First Development Protocol

To prevent AI "Big-Bang" code dumps, ensure zero waste, and preserve total user design control:

1. **Skeleton / Wireframe Layout Agreement First**:
   * Before applying visual CSS styling, colors, gradients, or animations to *any* screen, the agent **MUST** present a pure **structural wireframe / layout skeleton**.
   * Wireframes must be implemented with simple HTML boxes and visible borders (`border: 1px solid/dashed`), clearly labeling each structural zone (e.g. `[App Launcher]`, `[Breadcrumbs & Action Bar]`, `[Document Header]`, `[Tabbed Line Items]`, `[Chatter Dock]`).
2. **Review & Approval Gate**:
   * The user reviews the layout skeleton directly on screen (`http://localhost:5173`).
   * The agent is strictly forbidden from proceeding to detailed visual styling, component creation, or backend data binding until the user formally approves the spatial arrangement.
3. **Progressive Structural Slicing**:
   * Work moves forward in discrete, verifiable layers:
     * `Master Shell Skeleton` $\rightarrow$ Approved $\rightarrow$ Shell Styled.
     * `Sub-Nav & Menus Skeleton` $\rightarrow$ Approved $\rightarrow$ Sub-Nav Styled.
     * `Explorer Table Skeleton` $\rightarrow$ Approved $\rightarrow$ Explorer Table Styled.
     * `Document Form Skeleton` $\rightarrow$ Approved $\rightarrow$ Document Form Styled.

---

## 5. Design Tokens & Visual Theming Standard

Global UI appearance is declared via typed `UIThemeSettings` under the `ui_schema` module (Section 6.7):

* **Zero Third-Party CSS Frameworks**: Built 100% on Vanilla CSS Custom Properties declared on `:root`.
* **Standard Theme Presets**:
  1. `sovereign-dark`: Glassmorphic dark aesthetic, deep obsidian backgrounds (`#0d1117`), glowing accent borders (`#58a6ff`), elevated card surfaces (`#161b22`).
  2. `enterprise-light`: High-legibility corporate light mode (`#ffffff` surfaces, `#f6f8fa` canvas, `#0969da` accents, `#d0d7de` borders).
  3. `high-density-erp`: Compact accounting theme optimized for tabular data grids, smaller typography (12px), condensed padding (4px 8px), and rapid numeric data entry.
  4. `nordic-minimal`: Soft-contrast modern minimalist dark theme (`#1e1e24` surfaces, `#e2e2e2` typography, subtle cool gray accents).
* **Shell Archetypes**:
  * `collapsible_sidebar`: Modern icon sidebar expanding on hover or toggle.
  * `top_navbar`: Traditional top navigation bar with dropdown menus.
  * `master_detail`: Split master-detail layout with left list pane and right content viewport.
* **Fluid Resizable Split-Panel Sidebar**:
  * Native implementation using browser Pointer Events (`onPointerDown`, `onPointerMove`, `onPointerUp`).
  * Enforces backend constraints: default 65% form / 35% dock; min 35%, max 100% (collapsible).
  * Persists user-dragged widths to PostgreSQL via `PUT /api/v1/ui/preferences/{res_model}/{view_type}`.

---

## 6. Metadata-Driven Dynamic Schema Integration

The frontend operates as a high-speed declarative interpreter for backend schemas generated by `backend/modules/base/ui_schema/`:

* **Single-Bundle Endpoint**: `GET /api/v1/ui/views/{res_model}` returns the `ResolvedModelViewBundle` containing:
  * `form`: `FormViewSchema` (Tabs, Sections, Columns, Widgets, Status Bar).
  * `list`: `ListViewSchema` (Columns, Default Sort, Sequence).
  * `kanban`: `KanbanViewSchema` (Grouping field, Card template).
  * `user_preferences`: Active user's persisted split ratio, column widths, and visible columns.
* **Dynamic Introspection Fallback**:
  * Any ORM model without a custom view definition automatically renders using backend introspection metadata (`introspection.py`), ensuring Day-1 zero-code CRUD for all business entities.
* **Field-Level Access Control (FLAC) Compliance**:
  * Backend pre-filters schemas based on caller permissions. The frontend honors these flags: fields omitted from schema are never rendered; fields with `readonly: true` render as non-editable text.

---

## 7. Multi-Company Context & API Protocol

* **Dual-Header Propagation**:
  * **Write Operations (`POST`, `PUT`, `DELETE`)**: Strictly single-tenant; injects `X-Company-ID: <active_company_id>` from current context.
  * **Read Operations (`GET`)**: Aggregated multi-tenant queries; injects `X-Company-IDs: <id1>,<id2>` when multi-company view is active.
* **Authentication & 2FA Lifecycle**:
  * Standard Bearer Token authorization: `Authorization: Bearer <JWT>`.
  * Automatic handling of two-step 2FA login: if `POST /api/v1/identity_rbac/auth/login` returns `mfa_required: true`, the frontend halts and presents the 6-digit TOTP / recovery code modal.
* **Native Typed Fetch Client**:
  * Built using native `window.fetch` (zero Axios dependency).
  * Intercepts `401 Unauthorized` to attempt silent token refresh (`POST /api/v1/identity_rbac/auth/refresh`) before redirecting to login.

---

## 8. Continuous Architecture & Task State Synchronization

* **Mandatory Architecture Maintenance**:
  * Any frontend architectural pivot, layout evolution, or new platform pattern MUST be immediately documented in this file ([`docs/ai_wiki/frontend_architecture.md`](file:///home/ehab/Desktop/economy_editor/docs/ai_wiki/frontend_architecture.md)).
* **Real-Time Active Plan Synchronization**:
  * Every frontend task and milestone must be tracked in [`docs/plans/active_plan.md`](file:///home/ehab/Desktop/economy_editor/docs/plans/active_plan.md) (strictly cumulative and append-only).
  * Check off tasks (`- [x]`) and record the commit hash immediately upon completing each distinct sub-task.
* **Empirical Verification**:
  * Every change must be verified live in the browser with zero console errors before executing atomic conventional commits (`feat(frontend-...)`, `fix(frontend-...)`).
