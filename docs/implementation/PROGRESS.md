# BizPilot AI Project Progress

**Last updated:** 2026-10-07  
**Current phase:** P0 complete and web UI redesigned to the approved design canvas (R1–R10); release gate (HARD-008) pending human approval  
**Current task status:** FIX-001 to FIX-009 and redesign R1–R10 committed (not pushed); see "Open items before release"

## Purpose

This file records completed BizPilot AI planning, architecture, engineering-system, and foundation work. It is a status record, not a replacement for the approved PRD, architecture documents, or implementation plan.

## Completed Milestones

### 1. Product requirements

- `docs/prd/PRD.md` was aligned to the founder-approved priority model.
- The PRD PDF was regenerated and verified against the Markdown source of truth.
- P0, P1, P2, and Future boundaries were preserved, including the distinction between payment recording and Payment Reconciliation, basic dashboard behavior and Advanced Analytics, and internal traceability versus user-facing Audit Logs.

### 2. System architecture

- `docs/architecture/SYSTEM-ARCHITECTURE.md` was rewritten and approved.
- P0 architecture is a modular monolith: Next.js frontend, FastAPI backend, and PostgreSQL.
- Tenant isolation, backend RBAC, deterministic business operations, transaction boundaries, conditional Redis/ARQ, and scale-triggered infrastructure evolution are documented.

### 3. AI architecture

- `docs/architecture/AI-ARCHITECTURE.md` was created and approved.
- P0 uses one read-oriented BizPilot AI Assistant with authorized domain tools.
- The eight approved read-only tools, provenance, authorization boundary, failure behavior, evaluation approach, and P2 RAG boundary are documented.
- No arbitrary SQL, direct model-to-database access, autonomous writes, or P0 vector infrastructure was introduced.

### 4. Database design

- `docs/architecture/DATABASE-DESIGN.md` was created and approved.
- The bounded P0 relational model, UUID identifiers, integer minor-unit money, UTC timestamps, tenant ownership, inventory movement/balance invariant, payment-recording boundary, secure auth persistence, AI metadata, constraints, indexing, and history preservation are documented.
- P1 and P2 schemas remain deferred.

### 5. Security design

- `docs/architecture/SECURITY-DESIGN.md` was created and approved.
- Argon2id preference, symmetric JWT baseline, refresh rotation and reuse detection, Owner/Manager/Staff RBAC, IDOR prevention, strict tenant isolation, configurable rate-limit policy, AI authorization, secret handling, redaction, backup protection, and adversarial testing are documented.

### 6. P0 implementation plan

- `docs/implementation/P0-IMPLEMENTATION-PLAN.md` was created and verified.
- The plan contains 36 sections, 82 bounded tasks, phases 0 through 12, migration sequencing, vertical frontend slices, testing/security sequences, AI sequencing, and explicit Human Gates.
- The required workflow is `SPEC -> PLAN -> IMPLEMENT -> TEST -> REVIEW -> HUMAN APPROVAL -> COMMIT`.

### 7. Project agent and skill system

- `.opencode/agents/bizpilot-engineer.md` was created as the thin OpenCode orchestrator.
- Five shared skills were created under `.agents/skills/`: `backend-engineer`, `frontend-engineer`, `security-reviewer`, `test-engineer`, and `code-reviewer`.
- `AGENTS.md` was updated with concise repository-wide workflow, authority, scope, security, testing, and commit rules.
- OpenCode discovery and read-only FND-001 dry-run validation succeeded.
- A Codex discovery dry-run was attempted but could not complete because of an account usage limit and Context7 MCP authentication failure; no repository changes resulted.

### 8. FND-001: repository foundation

FND-001 established repository boundaries only:

- `REPOSITORY-STRUCTURE.md`
- `apps/api/README.md`
- `apps/web/README.md`
- `tests/README.md` plus the unit, integration, security, AI, and E2E test-area READMEs
- `alembic/README.md`
- Directory boundaries for `apps/api`, `apps/web`, `tests/*`, and `alembic`

FND-001 explicitly did not create application code, package manifests, dependencies, database connectivity, migrations, Docker configuration, CI workflows, or business functionality.

### 9. P0 implementation (2026-09-18 to 2026-09-27)

All twelve P0 modules are implemented and committed: foundation (FND), authentication (AUTH), organizations, membership, permissions and tenant context (ORG), categories and products (CAT/PROD), inventory (INV), customers (CUST), orders (ORD), payments (PAY), expenses (EXP), dashboard (DASH-001..003), AI assistant (AI-001..008), UX integration (UX-001..007) and hardening (HARD-001..007). Database migrations run linearly from `0001_initial_foundation` to `0014_auth_rate_limits`.

### 10. Post-review fixes (2026-10-03)

A full code review against the PRD found P0 gaps that HARD-007 had not caught. Each was fixed as a separate approved task:

| Task | Commit | Result |
| --- | --- | --- |
| FIX-001 | `adbcad4` | Four stale test assertions aligned with current routes, migration head and configurable token lifetime. |
| FIX-002 | `74a49e1` | CORS origins and web API proxy target are configuration; production rejects wildcard, non-https and loopback origins. |
| FIX-003 | `00ec050` | FR-001 rate limiting: login failures per email+IP, forgot-password per email, reset-password per IP (default 5 per 15 minutes, configurable); PostgreSQL-backed, subjects stored as SHA-256 digests; migration `0014`. |
| FIX-004 | `1543261` | Password-reset links delivered by configurable SMTP; non-blocking and non-enumerating; production requires TLS SMTP and an https frontend URL. |
| FIX-005 | `0708946` | Shared web API client with single-flight refresh-and-retry on 401 and sign-out when the refresh token is rejected. |
| FIX-006 | `65ffe32` | FR-003 Team Members UI (invite, change role, revoke), pending-invitation listing and acceptance, uniform invite error for missing/inactive accounts. |

### 11. Follow-up fixes (2026-10-04)

| Task | Commit | Result |
| --- | --- | --- |
| FIX-007 | `5324611` | Unverified compliance and marketing claims removed from the web UI. |
| FIX-008 | `5f09b62` | UI role derived from the member's role in the URL workspace; workspace route guard for signed-out users and non-members. |
| FIX-009 | `c985efb` | Membership changes recorded in the trace log; AI assistant requires date clarification and citations. |

### 12. Web UI redesign to the design canvas (2026-10-04 to 2026-10-07)

The web app was rebuilt screen by screen from the approved "BizPilot AI — Product Design" canvas. Each phase was planned, approved, tested and committed separately. No backend changes were made except where noted.

| Phase | Commit | Result |
| --- | --- | --- |
| R1 | `131c22a` | Design system (`bizpilot.css` tokens and components) and app shell. |
| R2 | `0a0a931` | Landing, login, register, password recovery, onboarding and workspace chooser. |
| R3 | `3daf273` | Dashboard. |
| R4 | `d97d9e0` | Products, categories, inventory and stock detail. |
| R5 | `b295d9e` | Customers list and detail; `GET /customers/balances` (Owner/Manager). AI read services count only active records. |
| R6 | `2de7588` | Orders list, full-page POS (`/orders/new`), order detail and inline correction (`/orders/[id]`). Fix: order writes now refresh inventory, dashboard and balances. |
| — | `24f40b0` | E2E mocks restored after FIX-008 (stored session + `/auth/refresh` mock) and aligned with real API shapes. |
| — | `e4e3cfa` | Fix: assistant called `/api/v1/.../ai/chat`, a route the backend never served (present since AI-008). |
| R7 | `73e1831` | Payments (record/detail sheets, pre-filled from orders and customers) and expenses (Staff restricted state, categories panel). Fix: payment methods now match the backend enum; today's totals use the business timezone. |
| R8 | `d28e0d3` | BizPilot AI: suggested questions, answers with a provenance footer, calm denied/failure states. Fix: the current question is no longer sent twice in `conversation_history`. |
| R9 | `63b59d3` | Team (Owner-only, capability table mirrors backend permissions) and a Settings page (read-only business profile and account; sign out of all devices). |
| R10a | `e04a659` | Not-found, error and offline states; before → after review step for payment and expense corrections. |
| R10b | `e969668` | 4-step phone POS under 760px; expenses as cards on phones; no horizontal overflow at 375px on any main page. |
| R10c | `30ddbb7` | Dark mode (system default, Appearance setting, no flash). Fix: sheets and dialogs now cover the viewport (a retained animation transform had trapped them). |

Design items deliberately not built because the backend has no support yet: the eight structured AI result cards (answers show text plus provenance instead), renaming the business, editing a profile, changing a password while signed in, resending invitations, leaving a workspace, restoring archived expense categories, and date filter/search on orders and payments.

## Current Status

| Area | Status | Notes |
| --- | --- | --- |
| Approved product and architecture documents | Complete | Human-approved source documents are in place. |
| P0 backend modules (FR-001 to FR-013) | Complete | Including FIX-003 rate limiting, FIX-004 email delivery and FIX-006 invitation discovery. |
| P0 web application | Complete; redesigned (R1–R10) | All screens follow the design canvas, including mobile and dark mode. |
| P0 AI assistant | Complete | Read-only, eight grounded tools, kill switch, redacted metadata. Web client route fixed in `e4e3cfa`. |
| Hardening (HARD-001 to HARD-007) | Complete | Readiness review corrected by DOC-001 on 2026-10-03. |
| Release gate (HARD-008) | Pending | Requires human review of the open items below. |

## Verification Recorded (2026-10-03)

- Backend full suite before fixes: 746 passed, 4 failed (stale assertions fixed in FIX-001).
- After fixes, targeted runs: backend unit + auth + recovery + organization + migration suites passed (latest run 423 passed); security, auth and cross-module suites 189 passed.
- Web: TypeScript check clean; Vitest 18 files, 138 tests passed.
- A full backend re-run after FIX-006 has not been recorded yet.
- No push was performed.

## Verification Recorded (2026-10-07, after R10c)

- Web: TypeScript check clean; production build succeeds; Vitest 22 files, 194 tests passed; Playwright E2E 33 passed (desktop, 375px phone and dark mode).
- Backend: only the R5 change was re-tested (customer balances, AI read services and app routes: 16 passed). A full backend run has not been recorded since FIX-006.
- No push was performed.

## Next Controlled Step

HARD-008 (release gate) needs explicit human approval. No task advances automatically from this file.

## Open Items Before Release

Resolved since 2026-10-03: unverified marketing copy (FIX-007), hard-coded `userRole="owner"` and the missing workspace route guard (FIX-008).


- Security decision: the AI tool `get_customer_balance` requires only `customers:read`, so Staff can ask the AI for a customer's balance, while the Customers page (R5, `dashboard:read_operational`) hides balances from Staff. One of the two needs to change.
- Expense date filters (`start_date`/`end_date`) are applied as UTC days, so "This month" can include or miss expenses from the first five hours of a month in Pakistan time.
- A full backend test run should be recorded before release (last full run predates FIX-006).
- Invitations require the invitee to already have an account, so an Owner can still tell whether an email is registered; inviting unregistered emails is a new feature needing a product decision.
- No per-IP limit across many emails on login, and rate-limit rows are not pruned.
- Tokens remain in `localStorage` (founder decision 2026-10-03); moving to httpOnly cookies is a later security task.
- Error parsing is still duplicated across web API modules (nine `ApiError` classes in `apps/web/lib/api`).
- No production Dockerfiles exist; only `Dockerfile.dev` for API and web.

## Deferred Decisions

- Redis and ARQ remain conditional P0 dependencies and require a concrete requirement plus Human Approval.
- Production secret-manager choice, retention policies and backup retention remain deployment/release decisions.
- AI provider privacy and data terms must be reviewed before live business/customer data is sent.
- Production rate-limit thresholds should be tuned from real usage.

## Scope Guard

This progress record does not authorize implementation. P1, P2, and Future features remain outside P0, and no progress entry should be interpreted as approval to begin another Task ID.
