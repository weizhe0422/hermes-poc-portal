"""Docker SDK Adapter（docs/04：不使用 Shell、不拼接 CLI、不接受任意參數）。

只暴露受管 Instance 生命週期所需的固定操作；
Container 查找僅允許以 instance-id Label 或「名稱等於 instance_id」兩種方式，
查得的候選仍須通過 Registry 雙白名單才可操作。
"""

from dataclasses import dataclass

from docker.client import DockerClient
from docker.errors import APIError, DockerException, NotFound

from app.errors import ControllerError
from app.registry.registry import INSTANCE_ID_LABEL


@dataclass(frozen=True)
class ContainerInfo:
    container_id: str
    name: str
    status: str  # docker 原始狀態字串（created/running/exited/...）
    image: str
    labels: dict[str, str]


def _info(container) -> ContainerInfo:  # type: ignore[no-untyped-def]
    image_tags = getattr(container.image, "tags", None) or []
    return ContainerInfo(
        container_id=container.id,
        name=container.name,
        status=container.status,
        image=image_tags[0] if image_tags else str(getattr(container.image, "id", "unknown")),
        labels=container.labels or {},
    )


class DockerAdapter:
    def __init__(self, client: DockerClient):
        self._client = client

    def find_candidate(self, instance_id: str) -> ContainerInfo | None:
        """以 Label 優先、名稱其次找出對應 Container；找不到回 None。"""
        try:
            by_label = self._client.containers.list(
                all=True, filters={"label": f"{INSTANCE_ID_LABEL}={instance_id}"}
            )
            if by_label:
                return _info(by_label[0])
            try:
                return _info(self._client.containers.get(instance_id))
            except NotFound:
                return None
        except (APIError, DockerException) as exc:
            raise ControllerError("DOCKER_UNAVAILABLE") from exc

    def start(self, container_id: str) -> None:
        try:
            self._client.containers.get(container_id).start()
        except NotFound as exc:
            raise ControllerError("INSTANCE_NOT_FOUND") from exc
        except (APIError, DockerException) as exc:
            raise ControllerError("DOCKER_UNAVAILABLE") from exc

    def stop(self, container_id: str, timeout_seconds: int) -> None:
        """正常停止；不刪除 Container 或 Volume（RT-04）。"""
        try:
            self._client.containers.get(container_id).stop(timeout=timeout_seconds)
        except NotFound as exc:
            raise ControllerError("INSTANCE_NOT_FOUND") from exc
        except (APIError, DockerException) as exc:
            raise ControllerError("DOCKER_UNAVAILABLE") from exc

    def inspect(self, container_id: str) -> ContainerInfo | None:
        try:
            return _info(self._client.containers.get(container_id))
        except NotFound:
            return None
        except (APIError, DockerException) as exc:
            raise ControllerError("DOCKER_UNAVAILABLE") from exc

    def logs_tail(self, container_id: str, tail: int) -> list[str]:
        try:
            raw = self._client.containers.get(container_id).logs(tail=tail, timestamps=False)
        except NotFound as exc:
            raise ControllerError("INSTANCE_NOT_FOUND") from exc
        except (APIError, DockerException) as exc:
            raise ControllerError("DOCKER_UNAVAILABLE") from exc
        text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
        return [line for line in text.splitlines() if line]
