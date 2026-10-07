# Production image for the BizPilot API. Build from the repository root:
#   docker build -f apps/api/Dockerfile -t bizpilot-api .
# Migrations are not run on start (several replicas would race); run them once per release:
#   docker run --rm --env-file <prod env> bizpilot-api alembic upgrade head
FROM python:3.12-slim AS build

WORKDIR /build
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/api/app apps/api/app
RUN pip install --no-cache-dir --prefix=/install ./apps/api


FROM python:3.12-slim

# libpq is required at runtime by psycopg (pure-Python build).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 bizpilot

COPY --from=build /install /usr/local
WORKDIR /app
COPY --chown=bizpilot:bizpilot alembic.ini alembic.ini
COPY --chown=bizpilot:bizpilot alembic alembic
COPY --chown=bizpilot:bizpilot apps/api/app apps/api/app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BIZPILOT_ENVIRONMENT=production \
    BIZPILOT_DEBUG=false \
    # Trust X-Forwarded-For only from the platform ingress, so rate limits see the real client IP.
    # "*" is safe only while the container is reachable solely through that ingress (Azure Container
    # Apps internal port); set the ingress address range instead if anything else can reach it.
    FORWARDED_ALLOW_IPS="*"

USER bizpilot
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--app-dir", "apps/api", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-server-header"]
