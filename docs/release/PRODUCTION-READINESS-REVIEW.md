# Production Configuration and Deployment Readiness Review (HARD-007)

**Document Status:** Corrected by DOC-001 on 2026-10-03 — release gate pending  
**Scope:** BizPilot AI — P0 MVP Pilot Deployment  
**Authoritative Reference:** `docs/implementation/P0-IMPLEMENTATION-PLAN.md`

---

## 1. Executive Summary

The original HARD-007 review (2026-09-27) marked every item "Verified" and reported no blockers. A code review on 2026-10-03 found that several items were not true at that time (hard-coded CORS, no login/recovery rate limiting, no real password-reset email, no Team Members UI, no production Dockerfiles). FIX-001 to FIX-006 closed the code gaps. This revision records the actual state and the items that still need a human decision before HARD-008.

---

## 2. Configuration Audit Checklist

| Item | Requirement | Production Value / Behavior | Status |
| :--- | :--- | :--- | :--- |
| **Environment Mode** | Strict production mode validation | `BIZPILOT_ENVIRONMENT=production` | Verified |
| **Debug Mode** | Debug mode prohibited in production | `BIZPILOT_DEBUG=false` (enforced by validator) | Verified |
| **Database Transport** | TLS/SSL required for PostgreSQL | `sslmode=require`, `verify-ca` or `verify-full` enforced | Verified |
| **Database Credentials** | Runtime credentials non-placeholder | Validated with length and marker heuristics | Verified |
| **Authentication Secret** | Minimum 32-character non-placeholder secret | Enforced by `_reject_placeholder` | Verified |
| **Password Policy** | Argon2id hashing | Time cost 3, memory 64 MiB, parallelism 4 (defaults) | Verified |
| **Token Lifetimes** | Short-lived access + rotated refresh tokens | Access 15 min, refresh 30 days (defaults; SHA-256 stored); web client refreshes on 401 (FIX-005) | Verified |
| **Credential Rate Limiting** | FR-001: login and recovery rate-limited | PostgreSQL-backed counters, default 5 per 15 min (FIX-003); requires uvicorn `--proxy-headers --forwarded-allow-ips` behind a proxy | Verified (FIX-003) |
| **Password Recovery Delivery** | Recovery reaches the user | SMTP with starttls/ssl and https reset link required in production (FIX-004) | Verified in code; needs a live SMTP account |
| **Multi-Tenant Isolation** | Server-verified RequestContext precedence | Path parameter precedence over headers; strict 404/403 rejection | Verified |
| **Team Members** | FR-003 invite, role change, revoke | API plus owner-only Team page and invitation acceptance (FIX-006) | Verified (FIX-006) |
| **AI Assistant Boundary** | Read-only P0 copilot | Bounded system prompt; no write tools; kill switch | Verified |
| **AI Credentials** | Independent provider credentials | Separate `BIZPILOT_AI__API_KEY` (never browser-exposed) | Verified |
| **Observability & Redaction** | Structured logging without secrets | Raw prompts/completions not stored; passwords/tokens scrubbed | Verified |
| **CORS Policy** | Allowlisted production origins | `BIZPILOT_CORS_ORIGINS`; production rejects `*`, non-https and loopback origins (FIX-002) | Verified (FIX-002) |
| **Browser Token Storage** | Minimize XSS impact | Tokens in `localStorage` (founder decision 2026-10-03) | Accepted risk |
| **Containerization** | Production images | Only `Dockerfile.dev` exists for API and web | **Open** |
| **Customer-facing UI copy** | No claims beyond P0 scope | Uncommitted redesign shows SBP/FBR/SOC-2 compliance, reconciliation and WhatsApp automation claims | **Open — blocker** |

---

## 3. Dependency Scope Invariant (No Deferred Scope Leakage)

The following components are **excluded** from the P0 MVP:
- **No Redis / Celery / ARQ:** Workflows, including rate limiting, run synchronously against PostgreSQL.
- **No Vector DB / Pinecone / pgvector:** The AI assistant is grounded only through deterministic SQL read services.
- **No Autonomous Write Tools:** AI cannot create, update or void orders, inventory, customers, payments or expenses.
- **No Forecasting / ML Models:** Future predictions and arbitrary document RAG are refused.
- **No External Bank APIs:** Payments are recorded as user-reported receipts, not bank settlements.

---

## 4. Disaster Recovery & Backup Invariants

- **Storage Engine:** PostgreSQL 16+.
- **Snapshot Frequency, RPO and RTO:** Targets (nightly snapshot, RPO ≤ 1 hour, RTO ≤ 4 hours) are proposals; the hosting provider and retention policy are still deployment decisions.
- **Restore Validation:** Migration chain verified linearly from `0001` through `0014_auth_rate_limits`.

---

## 5. Deployment Readiness Verdict

**VERDICT: NOT READY FOR RELEASE GATE (HARD-008).**

Blocking before customer pilot:
1. Remove or approve the out-of-scope compliance and automation claims in the UI.
2. Provide production container images (or document the chosen non-container deployment).
3. Configure and test a real SMTP account for password recovery.
4. Run the full backend suite once more after FIX-006 and record the result.

Non-blocking follow-ups are tracked in `docs/implementation/PROGRESS.md` under "Open Items Before Release".
