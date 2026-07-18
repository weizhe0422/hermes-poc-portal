ARG PYTHON_IMAGE=python:3.13.5-slim-bookworm
FROM ${PYTHON_IMAGE}

ARG PIP_INDEX_URL=https://pypi.org/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
    SPEC_ROOT=/spec \
    RESULTS_DIR=/test-results \
    CONTROLLER_BASE_URL=http://controller-under-test:8090

RUN groupadd --gid 10001 e2e \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin e2e \
    && install -d -o 10001 -g 10001 /app /test-results

COPY requirements.lock /tmp/requirements.lock
RUN python -m pip install --no-cache-dir --no-deps \
    --index-url "$PIP_INDEX_URL" --requirement /tmp/requirements.lock \
    && rm /tmp/requirements.lock

WORKDIR /app
COPY --chown=10001:10001 controller_e2e/ /app/controller_e2e/
COPY --chown=10001:10001 tests/e2e/ /app/tests/e2e/
COPY --chown=10001:10001 pytest.ini /app/pytest.ini

USER 10001:10001
ENTRYPOINT ["python", "-m", "controller_e2e.runner"]
