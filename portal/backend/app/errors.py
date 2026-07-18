"""Error Catalog 對映（contracts/errors/error-catalog.yaml），Portal 側。

所有 HTTP 錯誤回應必須符合 error-response.schema.json；
禁止洩漏 stack trace、secret、host 絕對路徑。
"""

from fastapi.responses import JSONResponse

from app.core.correlation import get_correlation_id

# error_code -> (http_status, retryable, user_message)
ERROR_CATALOG: dict[str, tuple[int, bool, str]] = {
    "DOCKER_UNAVAILABLE": (503, True, "Docker服務目前無法使用。"),
    "INSTANCE_NOT_FOUND": (404, False, "指定的Hermes Instance尚未建立。"),
    "INSTANCE_NOT_MANAGED": (403, False, "指定的Container不在Portal管理範圍內。"),
    "OPERATION_CONFLICT": (409, True, "此Instance目前已有生命週期操作執行中。"),
    "INVALID_STATE_TRANSITION": (409, False, "目前狀態不允許執行此操作。"),
    "HERMES_UNHEALTHY": (503, True, "Hermes已執行但健康檢查未通過。"),
    "LLM_UNAVAILABLE": (503, True, "內部模型服務目前無法使用。"),
    "AGENT_NOT_READY": (409, True, "Hermes尚未就緒，無法提交任務。"),
    "VALIDATION_ERROR": (422, False, "輸入資料不符合要求。"),
    "SECURITY_POLICY_VIOLATION": (403, False, "此操作不符合安全政策。"),
    "INTERNAL_ERROR": (500, False, "系統發生未預期錯誤，請提供Correlation ID給管理者。"),
}

# RESOURCE_STATE delivery（保存於 TaskRun.error，不改變原 POST 狀態碼）
RESOURCE_STATE_ERRORS = frozenset(
    {
        "RUNTIME_START_TIMEOUT",
        "RUNTIME_STOP_TIMEOUT",
        "AGENT_REQUEST_TIMEOUT",
        "AGENT_RESPONSE_INVALID",
    }
)


class PortalError(Exception):
    """受控錯誤：以 Error Catalog 的 HTTP 語意回應。"""

    def __init__(
        self,
        error_code: str,
        details: dict[str, str | int | bool | None] | None = None,
        http_status_override: int | None = None,
    ):
        if error_code not in ERROR_CATALOG:
            raise ValueError(f"unknown error_code: {error_code}")
        self.error_code = error_code
        self.details = details
        self.http_status_override = http_status_override
        super().__init__(error_code)


def error_response(error: PortalError) -> JSONResponse:
    http_status, retryable, message = ERROR_CATALOG[error.error_code]
    body: dict[str, object] = {
        "error_code": error.error_code,
        "message": message,
        "correlation_id": get_correlation_id() or "unknown",
        "retryable": retryable,
    }
    if error.details:
        body["details"] = error.details
    return JSONResponse(
        status_code=error.http_status_override or http_status, content=body
    )
