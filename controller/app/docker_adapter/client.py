"""Docker Engine 連線（Docker SDK for Python；禁止 Shell／CLI，docs/04）。

連線目標由 DOCKER_HOST 環境變數決定（docker.from_env）：
方案 A 預設為掛載給 Controller 的 unix socket；
之後可改指向 docker-socket-proxy 而不需修改程式碼。
"""

import docker
from docker.client import DockerClient


def create_docker_client() -> DockerClient:
    return docker.from_env()


def docker_available(client: DockerClient) -> bool:
    try:
        return bool(client.ping())
    except Exception:
        return False
