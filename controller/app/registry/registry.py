"""Instance Registry 與 Name/Label 雙白名單（RT-10、RT-11；x-security-rules）。

驗證順序（controller-api.yaml managed_instance_validation）：
1. registry_match：instance_id 必須存在於 Registry，否則 404 INSTANCE_NOT_FOUND。
2. container_name_match：Container 名稱須符合白名單 Pattern。
3. managed_label_match：Container 須帶 CONTROLLER_MANAGED_LABEL 指定的 Label。
2、3 任一不符 → 403 INSTANCE_NOT_MANAGED，且不得對該 Container 執行任何 Docker 操作。

v0.1 Registry 來源：CONTROLLER_INSTANCE_REGISTRY（JSON，供測試組態多 Instance），
未設定時預設只含 DEFAULT_INSTANCE_ID 一筆（docs/02：單一預先建立 Instance）。
"""

import json
import re
from dataclasses import dataclass

from app.core.config import Settings
from app.errors import ControllerError

# Container 上標記 Instance 身分的 Label key（compose.yaml 與 E2E Fixture 使用相同 key）。
INSTANCE_ID_LABEL = "poc.instance-id"


@dataclass(frozen=True)
class RegistryEntry:
    instance_id: str
    template_id: str


class InstanceRegistry:
    def __init__(
        self,
        entries: dict[str, RegistryEntry],
        managed_label_key: str,
        managed_label_value: str,
        name_pattern: re.Pattern[str],
    ):
        self._entries = entries
        self._managed_label_key = managed_label_key
        self._managed_label_value = managed_label_value
        self._name_pattern = name_pattern

    @classmethod
    def from_settings(cls, settings: Settings) -> "InstanceRegistry":
        label_key, _, label_value = settings.controller_managed_label.partition("=")
        entries: dict[str, RegistryEntry] = {}
        if settings.controller_instance_registry:
            for item in json.loads(settings.controller_instance_registry):
                entry = RegistryEntry(
                    instance_id=item["instance_id"],
                    template_id=item.get("template_id", settings.hermes_template_id),
                )
                entries[entry.instance_id] = entry
        else:
            entries[settings.default_instance_id] = RegistryEntry(
                instance_id=settings.default_instance_id,
                template_id=settings.hermes_template_id,
            )
        return cls(
            entries=entries,
            managed_label_key=label_key,
            managed_label_value=label_value,
            name_pattern=re.compile(settings.controller_managed_name_pattern),
        )

    def instance_ids(self) -> list[str]:
        return list(self._entries)

    def require(self, instance_id: str) -> RegistryEntry:
        entry = self._entries.get(instance_id)
        if entry is None:
            raise ControllerError("INSTANCE_NOT_FOUND")
        return entry

    def is_managed_container(self, name: str, labels: dict[str, str]) -> bool:
        """Name 與 Label 雙白名單，兩者皆須通過。"""
        if not self._name_pattern.fullmatch(name):
            return False
        return labels.get(self._managed_label_key) == self._managed_label_value

    def require_managed(self, name: str, labels: dict[str, str]) -> None:
        if not self.is_managed_container(name, labels):
            raise ControllerError("INSTANCE_NOT_MANAGED")
