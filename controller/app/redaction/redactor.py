"""Log Secret Redaction（RT-13、NF-03；docs/04 Secret 管理）。

最低涵蓋：Bearer Token、API Key、Password、Private Key 與測試 Secret Pattern。
遮蔽採白名單式規則逐條套用；規則對應 E2E 固定假 Secret（TEST_SECRET_*）。
"""

import re

MASK = "****"

# key=value / key: value 形式的敏感鍵（保留 key，遮蔽 value）
_KV_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|secret|password|passwd|pwd|token|authorization|credential)\b"
    r"(\s*[=:]\s*)\S+"
)
_BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/\-]+=*")
_TEST_SECRET_PATTERN = re.compile(r"TEST_SECRET_[A-Za-z0-9_]+")
_PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN[A-Z ]*PRIVATE KEY-----")
# 常見金鑰樣式（如 sk- 開頭的 API Key）
_KEY_STYLE_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}\b")


def redact_line(line: str) -> str:
    if _PRIVATE_KEY_PATTERN.search(line):
        return MASK
    # Bearer 必須先於 KV 規則：否則「Authorization: Bearer <token>」的 KV 規則
    # 只會遮到「Bearer」一字，token 本體會漏遮。
    line = _BEARER_PATTERN.sub(f"Bearer {MASK}", line)
    line = _KV_PATTERN.sub(lambda m: f"{m.group(1)}{m.group(2)}{MASK}", line)
    line = _TEST_SECRET_PATTERN.sub(MASK, line)
    line = _KEY_STYLE_PATTERN.sub(MASK, line)
    return line


def redact_lines(lines: list[str]) -> list[str]:
    return [redact_line(line) for line in lines]
