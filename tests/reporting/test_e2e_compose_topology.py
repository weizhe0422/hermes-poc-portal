from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_portal_is_the_only_service_with_an_effective_host_port_path() -> None:
    document = yaml.safe_load(
        (REPO_ROOT / "compose.e2e.portal.yaml").read_text(encoding="utf-8")
    )
    services = document["services"]
    networks = document["networks"]

    assert services["portal-under-test"]["ports"] == [
        "${PORTAL_HOST_BIND_ADDRESS:-127.0.0.1}:${PORTAL_HOST_PORT:-8080}:8080"
    ]
    assert "ports" not in services["controller-under-test"]
    assert "ports" not in services["hermes-under-test"]
    assert networks["portal-network"].get("internal") is not True
    assert networks["e2e-network"]["internal"] is True
    assert networks["agent-network"]["internal"] is True
    assert networks["controller-engine-network"]["internal"] is True
