"""Controller 不得含 Shell 型 Docker 操作（docs/04、DoD：無 os.system／shell=True）。"""

from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent / "app"

FORBIDDEN_FRAGMENTS = [
    "subprocess",
    "os.system",
    "shell=True",
    "os.popen",
    "pty.spawn",
    "docker exec",  # 禁 CLI 字串拼接
    "docker run",
]


def test_app_source_has_no_shell_usage():
    violations: list[str] = []
    for path in sorted(APP_DIR.rglob("*.py")):
        content = path.read_text(encoding="utf-8")
        for fragment in FORBIDDEN_FRAGMENTS:
            if fragment in content:
                violations.append(f"{path.name}: {fragment}")
    assert violations == []
