"""Correlation ID：每個 Request 一個，寫入 Log 與 ErrorResponse。"""

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")

CORRELATION_HEADER = "X-Correlation-Id"


def get_correlation_id() -> str:
    return _correlation_id.get()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        correlation_id = request.headers.get(CORRELATION_HEADER) or uuid.uuid4().hex
        token = _correlation_id.set(correlation_id)
        try:
            response: Response = await call_next(request)
        finally:
            _correlation_id.reset(token)
        response.headers[CORRELATION_HEADER] = correlation_id
        return response
