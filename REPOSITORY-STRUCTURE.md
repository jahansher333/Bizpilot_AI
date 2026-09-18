# BizPilot AI Repository Structure

This document records the FND-001 repository and runtime boundaries. It does not initialize application functionality.

## Approved Boundaries

- apps/api/: FastAPI modular-monolith backend boundary. Backend domain modules, application services, persistence, and API routes belong here in later approved tasks.
- apps/web/: Next.js frontend boundary. Responsive product workflows belong here in later approved tasks.
- tests/: Shared verification boundary with unit, integration, security, AI, and end-to-end categories.
- alembic/: Reserved migration boundary for later approved database tasks. FND-001 creates no migrations.
- docs/: Product, architecture, security, and implementation source documents.

## Approved Runtime Direction

- Frontend: Next.js, TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, and Zod.
- Backend: Python, FastAPI, Pydantic, SQLAlchemy, and Alembic.
- Database: PostgreSQL as the authoritative business data source.
- Initial architecture: one frontend, one FastAPI modular monolith, and one PostgreSQL database.

Redis, ARQ, Kafka, Kubernetes, Terraform, pgvector, RAG, microservices, extra databases, and other infrastructure are not established by FND-001.

## Ownership Rules

- Product scope is defined by docs/prd/PRD.md.
- System, AI, database, and security boundaries are defined by the approved architecture documents.
- Task sequencing and gates are defined by docs/implementation/P0-IMPLEMENTATION-PLAN.md.
- FND-001 creates boundaries only. Configuration, framework shells, dependencies, database connectivity, migrations, and business functionality belong to later approved tasks.
