# BizPilot AI Project Progress

**Last updated:** 2026-10-03  
**Current phase:** P0 hardening complete; release gate (HARD-008) pending human approval  
**Current task status:** FIX-001 through FIX-006 committed after the 2026-10-03 code review; see "Open items before release"

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

## Current Status

| Area | Status | Notes |
| --- | --- | --- |
| Approved product and architecture documents | Complete | Human-approved source documents are in place. |
| P0 backend modules (FR-001 to FR-013) | Complete | Including FIX-003 rate limiting, FIX-004 email delivery and FIX-006 invitation discovery. |
| P0 web application | Complete with open items | Team Members added in FIX-006; see open items below for UI copy and role gating. |
| P0 AI assistant | Complete | Read-only, eight grounded tools, kill switch, redacted metadata. |
| Hardening (HARD-001 to HARD-007) | Complete | Readiness review corrected by DOC-001 on 2026-10-03. |
| Release gate (HARD-008) | Pending | Requires human review of the open items below. |

## Verification Recorded (2026-10-03)

- Backend full suite before fixes: 746 passed, 4 failed (stale assertions fixed in FIX-001).
- After fixes, targeted runs: backend unit + auth + recovery + organization + migration suites passed (latest run 423 passed); security, auth and cross-module suites 189 passed.
- Web: TypeScript check clean; Vitest 18 files, 138 tests passed.
- A full backend re-run after FIX-006 has not been recorded yet.
- No push was performed.

## Next Controlled Step

HARD-008 (release gate) needs explicit human approval. No task advances automatically from this file.

## Open Items Before Release

- Uncommitted UI redesign (working tree) contains marketing copy that contradicts the PRD and must be removed or approved before any customer sees it, e.g. "100% SBP/Raast Compliant", "SOC-2 Type II Certified", "STATE BANK OF PAKISTAN & FBR COMPLIANT", "Real-time reconciliation", "Automated WhatsApp & SMS" and a hard-coded "₨ 0" balance.
- Several workspace pages pass a hard-coded `userRole="owner"`, so Staff see owner-only buttons; the backend still rejects the actions.
- The workspace has no client-side route guard for signed-out users opening a workspace URL directly.
- Invitations require the invitee to already have an account, so an Owner can still tell whether an email is registered; inviting unregistered emails is a new feature needing a product decision.
- No per-IP limit across many emails on login, and rate-limit rows are not pruned.
- Tokens remain in `localStorage` (founder decision 2026-10-03); moving to httpOnly cookies is a later security task.
- Error parsing is still duplicated across web API modules (`ApiError` signatures differ).
- No production Dockerfiles exist; only `Dockerfile.dev` for API and web.

## Deferred Decisions

- Redis and ARQ remain conditional P0 dependencies and require a concrete requirement plus Human Approval.
- Production secret-manager choice, retention policies and backup retention remain deployment/release decisions.
- AI provider privacy and data terms must be reviewed before live business/customer data is sent.
- Production rate-limit thresholds should be tuned from real usage.

## Scope Guard

This progress record does not authorize implementation. P1, P2, and Future features remain outside P0, and no progress entry should be interpreted as approval to begin another Task ID.
