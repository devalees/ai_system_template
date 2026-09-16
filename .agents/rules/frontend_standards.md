# Frontend Platform & React Standards (Zero-Bloat & Metadata-Driven)

A strict, high-performance architectural standard for building modular, metadata-driven frontend enterprise applications with zero dependency bloat.

---

## 1. Core Architecture & Tech Stack

* **Runtime & Bundler**: **React 19+ + Vite + TypeScript (Single-Page Application)**.
  * Native browser ES Modules (ESM) for sub-15ms Hot Module Replacement (HMR).
  * Pure client-side rendering (CSR) eliminating server-side hydration mismatches for dynamic metadata schemas.
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

## 3. Metadata-Driven Dynamic Schema Rendering

To ensure infinite scalability without hand-coding hundreds of static CRUD pages, the frontend consumes backend declarative schemas (`ui_schema`):

* **Generic Schema Renderers**:
  * `DynamicForm`: Interprets `FormViewSchema` (tabs, sections, columns, widgets, and status bars).
  * `DynamicGrid`: Interprets `ListViewSchema` (sortable columns, user-ordered sequences, resizable pixel widths).
  * `DynamicKanban`: Interprets `KanbanViewSchema` (stage columns, grouped cards, drag-and-drop state transitions).
* **Dynamic Introspection Fallback**: Any model registered in the backend ORM without explicit view templates must automatically render via dynamic introspection metadata.
* **Field-Level Access Control (FLAC) Adherence**: Dynamic renderers must strictly respect backend FLAC flags: omitted fields are never rendered; fields marked `readonly: true` must render as immutable display values.

---

## 4. Design Aesthetics, Theming & Styling Standard

* **Pure Vanilla CSS & CSS Variables (Design Tokens)**:
  * NEVER use TailwindCSS or runtime CSS-in-JS (Emotion, Styled-Components).
  * Define all design tokens as CSS Custom Properties on `:root` in `index.css`.
* **Theme Presets (Aligned with Backend `UIThemeSettings`)**:
  * `sovereign-dark`: Glassmorphic dark theme, subtle borders, glowing accent rings, dark card surfaces.
  * `enterprise-light`: High-contrast, clean corporate light mode.
  * `high-density-erp`: Compact accounting theme optimized for data grids and rapid numeric data entry.
  * `nordic-minimal`: Soft-contrast modern minimalist dark theme.
* **Shell Archetypes**: Support the 3 backend shell layout archetypes:
  * `collapsible_sidebar`: Modern icon rail expanding on hover or toggle.
  * `top_navbar`: Traditional top navigation bar with dropdown menus.
  * `master_detail`: Split list pane on the left with content viewport on the right.
* **Fluid Resizable Split-Panel Sidebar**:
  * Form views must render a resizable vertical split sidebar (default 65% primary form, 35% dock for Chatter and Activity feeds).
  * User-dragged splitter ratios must be persisted to the backend via `PUT /api/v1/ui/preferences/{res_model}/{view_type}`.

---

## 5. Multi-Company Context & API Protocol

* **Dual-Header Propagation**:
  * Every mutation (`POST`, `PUT`, `DELETE`) must send `X-Company-ID: <active_company_id>` for write isolation.
  * Aggregated multi-company read queries (`GET`) must send `X-Company-IDs: <id1>,<id2>` when multi-company view is activated.
* **Authentication & 2FA Lifecycle**:
  * Standard Bearer token authentication via `Authorization: Bearer <jwt>`.
  * Support intermediate 2FA challenge handshake: if login returns `mfa_required: true`, the frontend routes to the TOTP / recovery code challenge modal before storing the session.

---

## 6. Verification & Quality Gates

* **Zero Hydration or Console Errors**: Every screen must load with zero runtime errors, unhandled rejections, or missing key warnings.
* **Strict TypeScript**: Build with strict type checking enabled (`noImplicitAny: true`). Zero `any` escapes in core kernel contracts.
