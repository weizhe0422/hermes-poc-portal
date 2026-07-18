# Hermes Fixture Image（Test Only；BLD-01）
# REGISTRY_PREFIX：內部 Mirror 前綴（OD-06 未決前暫用 Docker Hub）。
ARG REGISTRY_PREFIX=""
FROM ${REGISTRY_PREFIX}python:3.13-slim

WORKDIR /srv/fixture

COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

COPY app ./app

# 非 root 執行（BLD-03）
RUN useradd --uid 10001 --create-home appuser
USER 10001

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
