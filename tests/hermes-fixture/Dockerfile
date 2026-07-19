# syntax=docker/dockerfile:1
ARG PYTHON_IMAGE=python:3.13.5-slim-bookworm
FROM ${PYTHON_IMAGE}

ARG PIP_INDEX_URL=https://pypi.org/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/hermes-fixture/src \
    FIXTURE_HOST=0.0.0.0 \
    FIXTURE_PORT=8000

RUN groupadd --gid 10001 fixture \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin fixture

WORKDIR /opt/hermes-fixture

COPY requirements.lock /tmp/requirements.lock
RUN python -m pip install --no-cache-dir --no-deps \
    --index-url "$PIP_INDEX_URL" --requirement /tmp/requirements.lock \
    && rm /tmp/requirements.lock

RUN mkdir -p /opt/hermes-fixture/src /state \
    && chown -R 10001:10001 /opt/hermes-fixture /state

COPY --chown=10001:10001 src/ /opt/hermes-fixture/src/

USER 10001:10001

EXPOSE 8000
STOPSIGNAL SIGTERM

HEALTHCHECK --interval=2s --timeout=1s --start-period=1s --retries=3 \
  CMD ["python", "-c", "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('FIXTURE_PORT','8000')+'/health',timeout=0.8).read()"]

ENTRYPOINT ["python", "-m", "hermes_fixture"]
