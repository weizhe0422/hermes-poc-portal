"""Health Endpoints（portal-api.yaml：/health/live、/health/ready）。

Portal HealthResponse 只要求 status 欄位（additionalProperties: false）。
Readiness 只確認 Portal 與 Database 可接受要求，不要求 Hermes Healthy（NF-04）。
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.db.engine import database_ready, get_engine
from app.errors import PortalError, error_response

router = APIRouter()


@router.get("/health/live")
async def liveness() -> JSONResponse:
    return JSONResponse(status_code=200, content={"status": "OK"})


@router.get("/health/ready")
async def readiness() -> JSONResponse:
    if database_ready(get_engine()):
        return JSONResponse(status_code=200, content={"status": "OK"})
    # Error Catalog 無資料庫專屬代碼；readiness 依 portal-api 以 503 回報，
    # error_code 採 INTERNAL_ERROR（catalog 內既有代碼，不自創新代碼）。
    return error_response(PortalError("INTERNAL_ERROR", http_status_override=503))
