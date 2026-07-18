"""受管 Instance API（controller-api.yaml /v1/instances*）。

固定路由；不存在任意 Image／Command／Volume／Container ID 入口（RT-11）。
"""

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from app.state.machine import Action
from app.state.service import RuntimeService

router = APIRouter(prefix="/v1/instances")


def _service(request: Request) -> RuntimeService:
    service: RuntimeService | None = request.app.state.runtime_service
    if service is None:
        # Docker Client 於啟動時不可用且尚未恢復。
        from app.errors import ControllerError

        raise ControllerError("DOCKER_UNAVAILABLE")
    return service


@router.get("")
async def list_instances(request: Request) -> JSONResponse:
    payload = await _service(request).list_instances()
    return JSONResponse(status_code=200, content=payload)


@router.get("/{instance_id}")
async def get_instance(request: Request, instance_id: str) -> JSONResponse:
    payload = await _service(request).get_instance(instance_id)
    return JSONResponse(status_code=200, content=payload)


@router.post("/{instance_id}/start")
async def start_instance(request: Request, instance_id: str) -> JSONResponse:
    status, payload = await _service(request).request_action(instance_id, Action.START)
    return JSONResponse(status_code=status, content=payload)


@router.post("/{instance_id}/stop")
async def stop_instance(request: Request, instance_id: str) -> JSONResponse:
    status, payload = await _service(request).request_action(instance_id, Action.STOP)
    return JSONResponse(status_code=status, content=payload)


@router.post("/{instance_id}/restart")
async def restart_instance(request: Request, instance_id: str) -> JSONResponse:
    status, payload = await _service(request).request_action(instance_id, Action.RESTART)
    return JSONResponse(status_code=status, content=payload)


@router.get("/{instance_id}/logs")
async def get_instance_logs(
    request: Request,
    instance_id: str,
    tail: int = Query(default=200, ge=1, le=1000),
) -> JSONResponse:
    payload = await _service(request).get_logs(instance_id, tail)
    return JSONResponse(status_code=200, content=payload)
