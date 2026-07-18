# Portal Production Image：Multi-stage（docs/03 Portal Image；BLD-01、BLD-02）
# REGISTRY_PREFIX：內部 Mirror 前綴（OD-06 未決前暫用 Docker Hub）。
ARG REGISTRY_PREFIX=""

# --- Stage frontend-build ---
FROM ${REGISTRY_PREFIX}node:24-bookworm-slim AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage runtime ---
FROM ${REGISTRY_PREFIX}python:3.13-slim AS runtime
WORKDIR /srv/portal

COPY backend/requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
COPY --from=frontend-build /build/dist ./static

# 非 root 執行（BLD-03）；/data 為 portal-data Volume 掛載點。
RUN useradd --uid 10001 --create-home appuser && \
    mkdir -p /data && chown 10001:10001 /data
USER 10001

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
