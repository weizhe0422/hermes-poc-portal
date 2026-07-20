# Hermes PoC Portal 獨立黑箱測試 — Frozen T-M0 / T-M1

本 repository 的驗收基準是 `contract-m0-m1-v0.2.1`（Contract v0.2.1，
commit `febdea906a51bab59e582755c495ed2253fb64b8`）。Runner 會在正式執行前
確認 tag 可解析，並拒絕 Contract、Infrastructure/Runtime Case 或 Expected Result
相對於該 tag 有差異的工作樹。

測試只從 `hermes-poc-specification-v0.1/` 讀取 Contract、Test Case 與合成
Fixture；不匯入、不修改、也不依候選平台行為重寫 Portal、Controller、Contract、
Test Case 或 Expected Result。

## 驗收 Inventory

Master Acceptance 固定輸出 31 個 Case：

| 分類 | 數量 | Case ID |
|---|---:|---|
| Portal Infrastructure（執行） | 8 | `SECURITY-001..003`、`EXECUTION-001..004`、`ARTIFACT-001` |
| Controller Environment（執行） | 1 | `CONTROLLER-ENV-001` |
| Runtime（執行） | 12 | `RUNTIME-001/003/004/005/006/007/008/009/012/013/014/017` |
| T-M4（不執行） | 10 | `CW-001..005`、`DEPLOY-001..005` |

前 21 個 Case 是 `contracts/versions.yaml` 的 Frozen M0/M1 scope，逐案執行並
產生 JUnit。後 10 個 Case 僅為 31-case master inventory 的里程碑邊界，固定分類為
`DEFERRED_BY_MILESTONE`；它們不會被執行，也不視為 PASS、FAIL 或
`NOT_EVALUATED`。完整 Requirement/Test Case 對照見
`tests/traceability/t-m0-t-m1.yaml`。

每個已執行 JUnit row 都包含 `test_case_id`、`requirement_ids`、`critical`、
Frozen Contract provenance、case-level coverage 與 evidence kind。這是 Case-level
驗收證據，不代表相關 Requirement 的其他 Portal、Golden Case 或後續里程碑切面也已完成。

## 外部 Container 與隔離架構

Portal Infrastructure Runner 是外部 Playwright container，只加入 internal
`e2e-network`。它可存取 Portal public boundary，不能解析或連線 Controller/Hermes；
沒有 Docker socket、Git metadata、Knowledge/Skill/Formal volume 或可寫 source mount。
Portal 是唯一對 Host 發布的服務，Host port 固定為 `8080`（預設綁定
`127.0.0.1`）。Runner 內觀察與外部
orchestrator 的 Host/container inspection 會合併後再判定 8 個 Infrastructure Case。

Controller Runtime 使用專用 rootless Docker-in-Docker Engine。Controller-under-test
只透過 internal TCP network 控制該 Engine；Runtime Runner 只透過 Controller OpenAPI
操作，不掛 Host Docker socket，也不能直接控制隔離 Engine。外部 orchestrator 為每個
Case 建立 event window、收集 container/volume/cleanup 證據，資源以
`poc.test-run=<run-id>` 限定，結束時只清除此 run 的資源。

兩個 Runner 均把 Frozen spec 唯讀掛到 `/spec`，並把結果寫到獨立 named volume；
外部 orchestrator 在 Runner 退出後複製到指定的 artifact root。Controller HTTP response
先依 Controller OpenAPI / referenced schema 驗證，再依 Runtime YAML Expected 與 State
Machine 判定；Engine-only Expected 由隔離 Engine 證據 gate，不能由 API 推測。

## 建置與執行

正式入口先執行 `scripts/verify-acceptance-source`。它在任何 Docker、build、trap 或
artifact 建立前，要求固定 Integration commit/ref、Contract/Platform/Test ancestry、
各 ownership tree、Fixture tree 與 clean working tree 全部相符。Detached HEAD 與指向
同一 Integration commit 的 branch checkout 都可使用；branch 只記錄，不參與 verdict。
Image 身分以執行時 reference 與 immutable `sha256:` image ID 保存，不依賴 OCI
revision label。

正式執行與 `--build-only` 共用下列必填 provenance：

```sh
export EXPECTED_INTEGRATION_COMMIT=<40-character-integration-commit>
export EXPECTED_INTEGRATION_REF=origin/integration/poc-rc-001
export PLATFORM_COMMIT=<40-character-platform-commit>
export TEST_COMMIT=<40-character-test-commit>
export CONTRACT_TAG=contract-m0-m1-v0.2.1
export EXPECTED_CONTRACT_COMMIT=febdea906a51bab59e582755c495ed2253fb64b8
```

只建置 Runner/Fixture images：

```sh
scripts/run-portal-e2e --build-only
scripts/run-controller-e2e --build-only
```

執行完整 31-case master acceptance：

```sh
RUN_ID=m0m1-v021-001 \
TEST_RESULTS_ROOT=/absolute/path/to/test-results \
PLATFORM_COMMIT=<40-character-platform-commit> \
PORTAL_IMAGE=<portal-candidate-image> \
CONTROLLER_IMAGE=<controller-candidate-image> \
scripts/run-m0-m1-acceptance
```

入口依序建立 `<RUN_ID>-infra` 與 `<RUN_ID>-runtime` child run，即使 child nonzero
也會產生 `<RUN_ID>` master JUnit/summary。只有 21 個 Frozen Case 全部 PASS 且 artifact
驗證通過時 master exit 0；只有明確 Contract ambiguity 阻擋時 master status 為
`CONTRACT_BLOCKED`，否則為 `FAIL`，兩者 exit 80。

也可單獨執行 child suite：

```sh
RUN_ID=m0m1-infra-001 PLATFORM_COMMIT=<commit> \
PORTAL_IMAGE=<image> CONTROLLER_IMAGE=<image> scripts/run-portal-e2e

RUN_ID=m0m1-runtime-001 PLATFORM_COMMIT=<commit> \
CONTROLLER_IMAGE=<image> scripts/run-controller-e2e
```

Test-owned unit/static checks：

```sh
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=tests/controller-e2e:tests/hermes-fixture/src \
SPEC_ROOT=hermes-poc-specification-v0.1 \
python3 -m pytest tests/controller-e2e/tests/unit tests/hermes-fixture/tests tests/reporting

cd tests/portal-e2e
npm run test:unit
npm run typecheck
```

可用 `CONTROLLER_E2E_IMAGE`、`PORTAL_E2E_IMAGE`、`HERMES_FIXTURE_IMAGE`、
`DOCKER_ENGINE_TEST_IMAGE` 與 build arguments `TEST_PYTHON_IMAGE`、
`PIP_INDEX_URL`、`PLAYWRIGHT_IMAGE`、`NPM_REGISTRY` 指向核准 registry/mirror。

## JUnit 與 Artifact

假設 `TEST_RESULTS_ROOT=/results`、`RUN_ID=m0m1-v020-001`：

```text
/results/m0m1-v020-001/
├── manifest.yaml
├── summary.json
├── summary.md
└── junit/m0-m1-acceptance.xml       # 31 rows

/results/m0m1-v020-001-infra/
├── manifest.yaml
├── summary.{json,md}
├── junit/*.xml                       # canonical 8 rows
└── portal-e2e/
    ├── junit/portal-e2e.xml
    ├── metadata.json
    ├── runner-observations.json
    ├── infrastructure-evidence.json
    ├── evidence/*.json
    ├── execution-probe/**            # injected-failure JUnit/trace/log/attempt
    ├── playwright-report/index.html
    ├── preflight/artifact-write-probe.json
    ├── compose.log
    ├── cleanup.json
    └── runner-status.json

/results/m0m1-v020-001-runtime/
├── manifest.yaml
├── summary.{json,md}
├── junit/*.xml                       # canonical 13 rows
└── controller-e2e/
    ├── infrastructure/junit.xml      # CONTROLLER-ENV-001
    ├── runtime-*/{junit.xml,http-trace.jsonl,summary.json,summary.md}
    ├── docker-snapshots/{controller-environment.json,containers.jsonl,
    │   persistence.json,evidence-RUNTIME-*.json,events-RUNTIME-*.jsonl,
    │   cleanup.json,outer-cleanup.json}
    ├── logs/*.log
    ├── phase-status.jsonl
    └── runner-status.json
```

Manifest 的 `git_commit` 記錄 Integration commit，`test_commit`、`platform_commit`、
Contract tag/commit 分別保存各 Candidate；`git_branch` 在 detached checkout 為 JSON
`null`，在 branch checkout 則是純記錄字串。每個 child 的 candidate identity 必須一致。
Image 以 reference 與執行時 immutable image ID 成對記錄；不要求 OCI revision label。
Collector fail-closed 檢查 inventory、metadata、必要 artifact、cleanup、source-tree
cleanliness、Critical verdict，並掃描文字、binary byte 與 ZIP member 中的合成 Secret。
Screenshot/video 未做 OCR，仍是明確的 Coverage Gap。

既有 `BASELINE_FAIL_OLD_PLATFORM` 證據不會被新 schema 改寫；archival validation 使用
其 producer Test commit 的 schema 與既有 `SHA256SUMS`，不能把舊 baseline 升格為本次
Acceptance input。

## Synthetic Fixture

`tests/fixture-manifest.yaml` 是 test-owned inventory；Runtime image
`hermes-poc-hermes-fixture:0.1.0` 提供固定 mode。正式 Runtime 使用：

- `hermes-fixture-001`：一般 lifecycle；`RUNTIME-017` 前重建為 `SLOW_START`。
- `hermes-fixture-slow`：`RUNTIME-008/009` 的併發與 timeout。
- `unmanaged-fixture-001`：故意無 managed label，供 `RUNTIME-012`。
- `hermes-fixture-secret`：只輸出合成值 `TEST_SECRET_123456`，供 `RUNTIME-013`。
- `hermes-fixture-persistent`：run-scoped volume marker，供 `RUNTIME-014`。

Control Wafer、Deployment knowledge、SVG 與 skill Fixture 保持唯讀，僅供 T-M4，
本階段不載入。

## Contract Notes 與 Known Flakiness

- `RUNTIME-009` 依 v0.2.1 Frozen Expected，先等待 `state == ERROR`，再以同名欄位
  驗證 `AgentInstance.last_error_code == RUNTIME_START_TIMEOUT`；Runner 不建立
  `error_code` alias。
- `RUNTIME-008` 要求平行 Start/Stop 一次 accepted、一次
  `OPERATION_CONFLICT`，但未凍結哪個 request 必須勝出。Runner 使用同步 barrier 且
  `NO_RETRY`；scheduler 若先送出 Stop，會照實回報，不以 retry 掩蓋，因此是已知競態風險。
- Frozen `versions.yaml` 把 `RUNTIME-008/009/012/013` 納入 M0/M1；它優先於仍把
  這些 Case 標為 T-M2 的 legacy work packet。

不在 Frozen 21-case scope 的 Matrix-only Runtime ID、Portal product flow、Control
Wafer/Deployment Golden Case，不會由本測試自行補 Expected 或宣告驗收。
