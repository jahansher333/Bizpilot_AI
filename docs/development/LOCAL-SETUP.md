# Local Development Setup Guide

## Overview

BizPilot AI provides a containerized local development environment orchestrating:
- **PostgreSQL 16**: Authoritative persistent relational database.
- **FastAPI Backend (`api`)**: Modular monolith with hot-reloading and automatic migrations.
- **Next.js Frontend (`web`)**: React 19 / Tailwind CSS application with hot-reloading.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & Docker Compose v2+
- Node.js 20+ (for local host frontend development / vitest)
- Python 3.12+ (for local host backend development / pytest)

---

## Quick Start with Docker Compose

### 1. Start Services

Start all development services in the background:
```bash
docker compose up -d
```

This starts:
- PostgreSQL on `localhost:5432`
- FastAPI on `http://localhost:8000`
- Next.js web application on `http://localhost:3000`

### 2. Verify Health

Check service liveness and database readiness:
```bash
# Liveness
curl http://localhost:8000/healthz

# Readiness (verifies PostgreSQL connectivity)
curl http://localhost:8000/readyz
```

Expected responses:
- `/healthz`: `{"status": "ok"}`
- `/readyz`: `{"status": "ready", "database": "connected"}`

### 3. Database Migrations

Apply Alembic migrations within the container:
```bash
docker compose exec api alembic upgrade head
```

Inspect current revision:
```bash
docker compose exec api alembic current
```

### 4. Running Tests

Run backend tests on the host:
```bash
pytest
```

Run frontend tests on the host:
```bash
cd apps/web && npm test
```

### 5. Stopping Services

Stop containers while preserving PostgreSQL data volume:
```bash
docker compose down
```

To reset the database volume completely:
```bash
docker compose down -v
```

---

## Security Notes

- The credentials in `docker-compose.yml` (`bizpilot_dev` / `bizpilot_dev_password`) are strictly for local offline development.
- Production environments use runtime secret injection and TLS. Never commit production secrets.
- Containers communicate over an isolated Docker network.
