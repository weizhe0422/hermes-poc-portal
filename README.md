# Hermes PoC Portal 獨立黑箱測試 — T-M0 / T-M1

本目錄是 `test/t-m0-m1` branch 上的獨立測試交付。測試只讀取
`hermes-poc-specification-v0.1/` 的 Contract、Test Case 與 Fixture；不匯入或修改
Portal、Controller、Hermes 平台程式，也不依平台現況改寫 Expected Result。

## 範圍與判定來源

| Milestone | 已實作內容 | 判定來源 |
|---|---|---|
| T-M0 | Portal/Controller Runner image、合成 Hermes Fixture、Compose 隔離、JUnit/JSON/Markdown 彙整、Secret scan | Build/Test Guide、Environment Contract、Traceability Matrix |
| T-M1 | `RUNTIME-001`、`RUNTIME-003`、`RUNTIME-006`、條件式 `RUNTIME-014` | Runtime YAML cases、Controller OpenAPI、AgentInstance schema、Runtime state machine |

`SECURITY-001..003`、`EXECUTION-001..004` 與 `ARTIFACT-001` 目前是
Traceability Matrix placeholder 的 Runner 自我檢查。它們在 JUnit/metadata 中明確標為
`coverage_claim: none` 與 `acceptance_status: not-evaluated`；通過不代表平台驗收通過。

完整 Requirement/Test Case 對照位於
`tests/traceability/t-m0-t-m1.yaml`。Fixture 對照位於
`tests/fixture-manifest.yaml`。

## Container 架構

Portal E2E Runner 只加入 internal `e2e-network`，可見 Portal public boundary，但不能
直接解析或連線 Controller/Hermes。Spec 以唯讀 bind mount 提供；結果目錄是唯一可寫
mount。

Controller E2E 使用兩層隔離：外層 Compose 啟動 rootless Docker-in-Docker；
Controller-under-test 只透過 internal TCP network 控制該 Engine。Runner 只加入
`controller-e2e-network`，不連 Docker Engine、不掛 Host Docker socket。Fixture image
先由外層匯入隔離 Engine，再建立帶 `poc.test-run=<run-id>` label 的固定容器、network
與 volume。Cleanup 只刪除相同 run label 的資源。

Controller Runner 對每個 HTTP response 執行 OpenAPI 3.1 / JSON Schema 2020-12 驗證，
再比對 YAML Expected Result。`RUNTIME-003` 另驗隔離 Engine 中目標容器確實 Running
且出現 start event；`RUNTIME-006` 使用獨立事件視窗確認沒有 create/start/stop/restart
event，且容器集合與測試 labels 完全不變。`RUNTIME-014` 使用 health 由 volume
marker gate 的 `PERSISTENT` Fixture；Restart 後只有 marker 保留才可能回到 `HEALTHY`。

## 建置與執行

所有正式 E2E 入口要求：目前 branch 必須是 `test/t-m0-m1`、Git tree 必須 clean、
Docker daemon 可用。Test image 可先單獨建置：

```sh
scripts/run-controller-e2e --build-only
scripts/run-portal-e2e --build-only
```

Controller T-M1（需要外部提供 Controller production image）：

```sh
CONTROLLER_IMAGE=hermes-poc-controller:0.1.0 \
PLATFORM_COMMIT=<40-character-platform-commit> \
RUN_ID=t-m1-controller-001 \
scripts/run-controller-e2e
```

Portal T-M0 Runner/network preflight（需要外部提供 Portal production image）：

```sh
PORTAL_IMAGE=hermes-poc-portal:0.1.0 \
PLATFORM_COMMIT=<40-character-platform-commit> \
RUN_ID=t-m0-portal-001 \
scripts/run-portal-e2e
```

可用 `TEST_RESULTS_ROOT=/approved/path` 改寫 artifact root。內部 Registry 可透過
`CONTROLLER_E2E_IMAGE`、`HERMES_FIXTURE_IMAGE`、`PORTAL_E2E_IMAGE`、
`DOCKER_ENGINE_TEST_IMAGE` 與 Docker build argument `PLAYWRIGHT_IMAGE` 指向核准 mirror；
版本仍須維持 lock 與 image/package patch 一致。

開發期的 test-owned unit checks：

```sh
PYTHONPATH=tests/controller-e2e SPEC_ROOT=hermes-poc-specification-v0.1 \
  python3 -m pytest tests/controller-e2e/tests/unit
python3 -m pytest tests/hermes-fixture/tests tests/reporting
```

## Artifact

每次正式執行寫入 `test-results/<run-id>/`（或指定的 `TEST_RESULTS_ROOT`）：

```text
manifest.yaml
summary.json
summary.md
junit/*.xml
controller-e2e/
  core-start/{junit.xml,http-trace.jsonl,summary.json,summary.md}
  core-idempotency/{junit.xml,http-trace.jsonl,summary.json,summary.md}
  persistence/{junit.xml,http-trace.jsonl,summary.json,summary.md}
  docker-snapshots/{containers.jsonl,persistence.json,invariants-*.json,events-*.jsonl,cleanup.json,outer-cleanup.json}
  logs/*.log
  runner-status.json
portal-e2e/
  junit/portal-e2e.xml
  metadata.json
  playwright-report/
  compose.log
  cleanup.json
  runner-status.json
  preflight/artifact-write-probe.json
  screenshots/  # failure 時選擇性產生
  traces/       # failure 時選擇性產生
  videos/       # failure 時選擇性產生
```

`manifest.yaml` 同時記錄測試 Commit、40 字元 Platform candidate Commit、所有
image tag 與執行當下不可變的 `sha256` image ID；正式 product run 缺少
`PLATFORM_COMMIT`，或 production image 的 `org.opencontainers.image.revision`
label 與該 Commit 不相等時，會在建立 acceptance artifact 前 fail closed。Controller
manifest 也記錄隔離 Docker Engine image。

`scripts/collect-test-results <run-id>` 將各 Runner 的 JUnit 複製至 canonical
`junit/`、產生機器可讀 `summary.json` 與人工摘要 `summary.md`，並在以下任一情況以
exit 80 fail-closed：JUnit 缺失/損毀或沒有 testcase、case/requirement/Engine metadata
缺失、suite case inventory 不完整或重複、必要 artifact/cleanup 缺失、Critical case 未通過、
測試失敗或 artifact 出現合成
Secret 的原始 byte（含 ZIP member）。Screenshot/video 內容未做 OCR，保留為 Coverage Gap。
Matrix placeholder 即使 Runner check 成功也標為 `INFRA_PASS` / `NOT_EVALUATED`，
不計入 acceptance passed 數量。

## Fixture 清單

合成 Runtime image `hermes-poc-hermes-fixture:0.1.0` 支援 `HEALTHY`、
`SLOW_START`、`UNHEALTHY`、`CRASH`、`SECRET_LOG`、`PERSISTENT` 六種固定 mode。
T-M1 使用：

- `hermes-fixture-001`：初始為 stopped；供 `RUNTIME-001/003/006`。
- `hermes-fixture-persistent`：掛 run-scoped volume 並預置固定 marker；供
  `RUNTIME-014`。

Bundle 內 Control Wafer、Deployment knowledge、SVG 與 verified skill Fixture 保持唯讀，
屬 T-M4，本階段不載入。

## Coverage Gap 與 Contract Ambiguity

- `RUNTIME-002/004/005/007/010/011/015/016` 只在 Traceability Matrix 出現，沒有
  YAML Expected Result；不自行生成 assertion。
- `RUNTIME-014` 已存在 Bundle Draft Runtime Case，但需 Controller registry 能以
  `DEFAULT_INSTANCE_ID` 指向 persistent Fixture；Harness 以獨立 phase/recreated
  Controller 滿足此前置條件。
- RT-06 提到 Restart idempotency，但 Runtime state machine 沒有 Restart idempotent
  response；列為 `CONTRACT_AMBIGUITY`，不以 Start 案例代替。
- RUNTIME-003 YAML 凍結 accepted HTTP status；RUNTIME-014 的 202 來自 OpenAPI；
  兩者都沒有規定 202 AgentInstance snapshot 必須仍為 `STARTING`/`STOPPING`。
  Runner 仍驗 schema、action-specific 有序可達路徑、最終狀態及 Engine events，
  不自行增加 accepted-body Expected。
- Instance Registry 的資料格式/載入 Contract 未凍結；Harness 只使用目前已定義的
  `DEFAULT_INSTANCE_ID` 單一 Instance 介面，不假設未發布的 registry schema。
- OD-03 尚未選定核准 LLM probe protocol；`RUNTIME-003` 會驗證 Contract schema 與
  `llm_status: AVAILABLE`，但不宣告已獨立證明 Controller 呼叫了特定 LLM endpoint。
- Docker/Playwright/Python base image 的內部 Registry digest 尚未由 Bundle 凍結；目前
  固定 patch tag，整合環境應提供核准 mirror/digest。
- Artifact Secret scan 會掃描文字、原始二進位 byte 與 ZIP member；不會對 screenshot/
  video 做 OCR，因此不宣告完整媒體內容 Secret acceptance。
- Test Dockerfile 可用 `TEST_PYTHON_IMAGE`、`PIP_INDEX_URL`、`PLAYWRIGHT_IMAGE`、
  `NPM_REGISTRY` 指向內部 mirror，但本次未在完全封閉網路執行 Build acceptance。

T-M2 的 `RUNTIME-008/009/012/013`，以及 T-M3 Portal product E2E、T-M4
Control Wafer/Deployment Golden Cases，均明確不在本次交付範圍。
