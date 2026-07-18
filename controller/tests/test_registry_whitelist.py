"""Instance Registry 與 Name/Label 雙白名單測試（RT-10、RT-11）。"""

import pytest

from app.core.config import Settings
from app.errors import ControllerError
from app.registry.registry import InstanceRegistry


def make_registry(**overrides) -> InstanceRegistry:
    return InstanceRegistry.from_settings(Settings(**overrides))


def test_default_registry_contains_default_instance():
    registry = make_registry(default_instance_id="hermes-poc-001")
    assert registry.instance_ids() == ["hermes-poc-001"]
    entry = registry.require("hermes-poc-001")
    assert entry.template_id == "hermes-poc-template-v1"


def test_unknown_instance_raises_not_found():
    registry = make_registry()
    with pytest.raises(ControllerError) as exc_info:
        registry.require("no-such-instance")
    assert exc_info.value.error_code == "INSTANCE_NOT_FOUND"


def test_registry_from_json_env():
    registry = make_registry(
        controller_instance_registry=(
            '[{"instance_id": "hermes-fixture-001", "template_id": "tpl-x"},'
            ' {"instance_id": "unmanaged-fixture-001"}]'
        )
    )
    assert set(registry.instance_ids()) == {"hermes-fixture-001", "unmanaged-fixture-001"}
    assert registry.require("hermes-fixture-001").template_id == "tpl-x"
    # 未給 template_id 時使用預設
    assert registry.require("unmanaged-fixture-001").template_id == "hermes-poc-template-v1"


MANAGED_LABELS = {"poc.managed": "true", "poc.instance-id": "hermes-poc-001"}


def test_dual_whitelist_pass():
    registry = make_registry()
    assert registry.is_managed_container("hermes-poc-hermes-1", MANAGED_LABELS)


def test_name_whitelist_rejects_non_matching_name():
    registry = make_registry()
    # Label 正確但名稱不含 hermes → 拒絕（雙白名單皆須通過）
    assert not registry.is_managed_container("unmanaged-fixture-001", MANAGED_LABELS)


def test_label_whitelist_rejects_missing_or_wrong_label():
    registry = make_registry()
    assert not registry.is_managed_container("hermes-poc-hermes-1", {})
    assert not registry.is_managed_container("hermes-poc-hermes-1", {"poc.managed": "false"})


def test_require_managed_raises_not_managed():
    registry = make_registry()
    with pytest.raises(ControllerError) as exc_info:
        registry.require_managed("unmanaged-fixture-001", {})
    assert exc_info.value.error_code == "INSTANCE_NOT_MANAGED"


def test_custom_name_pattern_from_environment():
    registry = make_registry(controller_managed_name_pattern=r"agent-[0-9]+")
    assert registry.is_managed_container("agent-42", MANAGED_LABELS)
    assert not registry.is_managed_container("hermes-poc-hermes-1", MANAGED_LABELS)
