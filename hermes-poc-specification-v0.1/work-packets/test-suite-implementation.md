# 工作包：獨立測試套件實作

> 文件目的：提供任何測試開發代理或工程師建立Portal E2E、Controller E2E、Fixture及測試Artifact所需規格；測試應只依賴公開Contract，不綁定平台內部實作或特定AI工具。
>
> 執行角色：Independent Test Suite Implementer。
>
> 前置條件：API/UI/Schema/State/Error Contract已凍結，合成Fixture可使用。
>
> 預期產出：Container化、可重現、能獨立判Pass/Fail的黑箱測試套件。

## 任務目標

建立兩套獨立E2E：

1. Portal E2E：從使用者可見介面驗證完整功能。
2. Controller E2E：從內部Controller API驗證Docker生命週期與安全邊界。

## 唯一輸入

- `docs/01-system-requirements.md`
- `docs/02-architecture.md`
- `docs/04-security-and-data-handling.md`
- `docs/05-build-and-test-guide.md`
- `contracts/`
- `test-cases/`
- `test-fixtures/`

平台目前行為不是Expected的來源。若實際行為不符Contract，測試必須Fail或標記Contract Ambiguity。

## 允許修改

```text
tests/portal-e2e/
tests/controller-e2e/
tests/hermes-fixture/（與平台實作者協調Ownership）
compose.e2e.portal.yaml
compose.e2e.controller.yaml
scripts/run-controller-e2e*
scripts/run-portal-e2e*
scripts/run-live-agent-e2e*
scripts/run-golden-cases*
scripts/run-functional-tests*
scripts/collect-test-results*
```

不得直接修改Portal、Controller、Contract或已核准Expected Result。

## Portal E2E交付

- `tests/portal-e2e/Dockerfile`。
- Playwright TypeScript Test Suite。
- UI及Portal API黑箱測試。
- Runtime、Knowledge、Deployment、History、Feedback及Artifact案例。
- Network Isolation負向案例。
- JUnit、HTML Report、Screenshot、Video、Trace。
- Runner只能加入`e2e-network`，不得加入Controller或Agent Network。

## Controller E2E交付

- `tests/controller-e2e/Dockerfile`。
- pytest/HTTPX黑箱測試。
- 隔離Docker Engine或專用Rootless Test Context。
- Healthy、Slow Start、Unhealthy、Crash、Secret Log與Persistent Fixture。
- Start/Stop/Restart、冪等、Lock、Timeout、Redaction、Whitelist及Cleanup案例。
- JUnit、HTTP Trace、Docker Snapshot、Controller Log。

## Fixture規則

- Fixture行為由環境變數決定且可重現。
- Fixture與真實Hermes使用不同Image名稱及Label。
- Synthetic Knowledge必須明確標示`TEST ONLY`。
- Unmanaged Fixture不得帶`poc.managed=true`，用於保護測試。
- 所有測試資源帶`poc.test-run=<run_id>`。

## Assertion規則

| 類型 | 做法 |
|---|---|
| API | Status Code＋JSON Schema＋Error Code |
| UI | Accessible Role/Name優先，必要時使用穩定`data-testid` |
| Runtime | 狀態轉移、時間界線、Container Snapshot |
| LLM結果 | Schema、Domain Status、Source ID、必要／禁止行為 |
| 自然語言 | 不做整段Exact Match；不得放寬Critical語意 |
| Secret | Assert完整測試Secret在所有Artifact中不存在 |

## 不允許的測試方式

- 直接讀Portal SQLite判定UI成功。
- 直接呼叫Hermes跳過Portal作為Portal E2E。
- Controller E2E Runner直接操作Docker API後宣稱Controller成功。
- 使用Sleep取代有上限的狀態Polling。
- Retry Critical Case直到通過。
- 因實作不同而修改Expected Result。

## 里程碑

| Milestone | 產出 | 可與平台並行的依據 |
|---|---|---|
| T-M0 | Runner Dockerfile、Report、Fixture | Machine Contract |
| T-M1 | Controller基本Lifecycle E2E | Controller OpenAPI＋State Machine |
| T-M2 | Controller安全／失敗E2E | Error Catalog＋Security Contract |
| T-M3 | Portal Runtime E2E | UI＋Portal OpenAPI |
| T-M4 | Knowledge/Deployment E2E | Domain Schemas＋Synthetic Fixture |
| T-M5 | Live Hermes與Golden Cases Runner | 核准環境與真實Fixture |

## 完成報告格式

```yaml
role: independent-test-implementer
git_commit: "..."
covered_requirements: []
uncovered_requirements: []
test_images: []
critical_cases: []
known_flakiness: []
contract_questions: []
artifact_formats: []
```

完成宣告需符合`docs/07-definition-of-done.md`的「測試套件Done」。
