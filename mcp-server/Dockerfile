# syntax=docker/dockerfile:1

# ---- Build stage: install dependencies and build the database from seed SQL ----
FROM python:3.12-slim AS build

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /srv

COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

COPY app ./app
COPY data/seed.sql ./data/seed.sql
RUN python -m app.database build --seed data/seed.sql --db /out/finance.db

# ---- Runtime stage ----
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MCP_DB_PATH=/data/finance.db \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000

# /data is created up front as root:root 0755. Otherwise COPY --chmod would also
# apply 0444 to the parent directory and the runtime user could not enter it.
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin mcp \
    && mkdir -m 0755 /data

COPY --from=build /install /usr/local
WORKDIR /srv
COPY app ./app
# Owned by root and mode 0444: the runtime user can read it but not change it.
COPY --from=build --chown=root:root --chmod=0444 /out/finance.db /data/finance.db

USER 10001
# This server returns sensitive fields unmasked; masking is enforced by the
# gateway. Never publish this port to the host. Reach it only through agentgateway.
EXPOSE 8000
CMD ["python", "-m", "app.server"]
