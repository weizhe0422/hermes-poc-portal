"""Health Endpoints（controller-api.yaml：/health/live、/health/ready）。

HealthResponse 依 contract 必含 status 與 docker_status 兩欄位：
- /health/live：只證明 Process 存活，一律 200；docker_status 反映目前連線狀態但不影響結果。
- /health/ready：Docker Engine 不可達時回 503 DOCKER_UNAVAILABLE（error catalog）。
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.docker_adapter.client import docker_available
from app.errors import ControllerError, error_response

router = APIRouter()


def _docker_status(request: Request) -> str:
    client = request.app.state.docker_client
    if client is not None and docker_available(client):
        return "AVAILABLE"
    return "UNAVAILABLE"


@router.get("/health/live")
async def liveness(request: Request) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={"status": "OK", "docker_status": _docker_status(request)},
    )


@router.get("/health/ready")
async def readiness(request: Request) -> JSONResponse:
    if _docker_status(request) == "AVAILABLE":
        return JSONResponse(
            status_code=200,
            content={"status": "OK", "docker_status": "AVAILABLE"},
        )
    return error_response(ControllerError("DOCKER_UNAVAILABLE"))
