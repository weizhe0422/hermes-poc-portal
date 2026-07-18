"""Hermes Runtime Controller（controller-api.yaml v0.1.0）。

只提供固定 Lifecycle API；不提供任意 Docker 管理、動態 Instance 建立或 Shell 入口。
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
from app.api.instances import router as instances_router
from app.core.config import get_settings
from app.core.correlation import CorrelationIdMiddleware
from app.core.logging import configure_logging
from app.docker_adapter.adapter import DockerAdapter
from app.docker_adapter.client import create_docker_client
from app.errors import ControllerError, error_response
from app.health.probes import HealthProbes
from app.registry.registry import InstanceRegistry
from app.state.service import RuntimeService
from app.state.store import InstanceStore

logger = logging.getLogger("controller")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    try:
        app.state.docker_client = create_docker_client()
    except Exception:
        # Docker 不可達時 Controller 仍須存活（liveness 200、readiness 503）。
        logger.warning("docker engine unreachable at startup")
        app.state.docker_client = None

    app.state.instance_store = InstanceStore()
    app.state.registry = InstanceRegistry.from_settings(settings)
    app.state.probes = HealthProbes(settings)
    if app.state.docker_client is not None:
        app.state.docker_adapter = DockerAdapter(app.state.docker_client)
        app.state.runtime_service = RuntimeService(
            settings=settings,
            registry=app.state.registry,
            adapter=app.state.docker_adapter,
            probes=app.state.probes,
            store=app.state.instance_store,
        )
    else:
        app.state.docker_adapter = None
        app.state.runtime_service = None
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Hermes Runtime Controller API",
        version="0.1.0",
        lifespan=lifespan,
        # 內部 API：不公開 swagger/openapi 頁面，介面以 contracts/ 為準。
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(CorrelationIdMiddleware)

    @app.exception_handler(ControllerError)
    async def controller_error_handler(_: Request, exc: ControllerError) -> JSONResponse:
        return error_response(exc)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return error_response(ControllerError("VALIDATION_ERROR"))

    @app.exception_handler(Exception)
    async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error")
        return error_response(ControllerError("INTERNAL_ERROR"))

    app.include_router(health_router)
    app.include_router(instances_router)
    return app


app = create_app()
