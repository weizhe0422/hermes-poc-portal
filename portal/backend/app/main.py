"""Hermes PoC Portal Backend（portal-api.yaml v0.1.0）。

FastAPI 同時提供 REST API 與 React 靜態資產（docs/03：PoC 不使用 Nginx）。
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.correlation import CorrelationIdMiddleware
from app.core.logging import configure_logging
from app.errors import PortalError, error_response

logger = logging.getLogger("portal")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Hermes PoC Portal API",
        version="0.1.0",
        lifespan=lifespan,
        # 介面以 contracts/openapi/portal-api.yaml 為準，不公開自動產生文件。
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(CorrelationIdMiddleware)

    @app.exception_handler(PortalError)
    async def portal_error_handler(_: Request, exc: PortalError) -> JSONResponse:
        return error_response(exc)

    @app.exception_handler(Exception)
    async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error")
        return error_response(PortalError("INTERNAL_ERROR"))

    app.include_router(health_router)

    static_dir = Path(settings.static_dir)
    if static_dir.is_dir():
        # SPA 靜態資產；client-side route fallback 於 P-M2 隨 UI Route 一併實作。
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app


app = create_app()
