# Controller Production Image（BLD-01、BLD-02）
# 只含 FastAPI、Uvicorn、Pydantic、HTTPX、Docker SDK；不安裝 Docker CLI（docs/03）。
# REGISTRY_PREFIX：內部 Mirror 前綴（OD-06 未決前暫用 Docker Hub）。
ARG REGISTRY_PREFIX=""
FROM ${REGISTRY_PREFIX}python:3.13-slim

WORKDIR /srv/controller

COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

COPY app ./app

# 非 root 執行（BLD-03）；Docker Socket 存取權由 compose group_add 提供（方案 A）。
RUN useradd --uid 10001 --create-home appuser
USER 10001

# Controller Port 不發布到 Host（BLD-07 由 compose 落實）。
EXPOSE 8090
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090"]
