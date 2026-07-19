# CR-002-RUNTIME-009-OBSERVABILITY

> 文件目的：保存 Frozen Contract 修改的決策與稽核軌跡，不屬於 Open Decision。

| 欄位 | 內容 |
|---|---|
| CR ID | CR-002-RUNTIME-009-OBSERVABILITY |
| Status | APPROVED_FOR_IMPLEMENTATION |
| Decision Date | 2026-07-19 |
| Baseline | contract-m0-m1-v0.2.0 |
| Target | contract-m0-m1-v0.2.1 |
| Approval | Requirement Owner approved |

## Root Cause

RUNTIME-009 為非同步 Start Timeout 案例。依 `contracts/errors/error-catalog.yaml`，`RUNTIME_START_TIMEOUT` 的 `delivery` 為 `RESOURCE_STATE`(`http_status: null`)：初始 POST 維持 HTTP 202,Timeout 發生後錯誤保存於 AgentInstance，並經由 `contracts/schemas/agent-instance.schema.json` 的 `last_error_code` 欄位對外暴露；`contracts/state-machines/hermes-runtime.yaml` 亦已定義 STARTING --START_TIMEOUT--> ERROR，且 ERROR 狀態描述「錯誤已被保存」。

然而 Frozen RUNTIME-009 的 Expected 使用 `expected.error_code`。該鍵名在 Frozen Suite 其他案例（如 RUNTIME-008、RUNTIME-012）中指同步 `ErrorResponse.error_code`,Contract 從未定義 RESOURCE_STATE 類錯誤下 `expected.error_code` 與 AgentInstance 觀察欄位之間的 mapping。Test Suite 無法在不自行推測的情況下判定，故標記 BLOCKED_BY_CONTRACT。

## Before / After Expected

Before:

```yaml
expected:
  initial_http_status: 202
  final_state: ERROR
  error_code: RUNTIME_START_TIMEOUT
```

After:

```yaml
expected:
  initial_http_status: 202
  final_state: ERROR
  last_error_code: RUNTIME_START_TIMEOUT
```

## Decision

依 Requirement Owner 裁定，RUNTIME-009 Expected 由 `expected.error_code` 改為 `expected.last_error_code`，直接命名 AgentInstance 終態快照上的觀察欄位。不建立通用 alias，不要求測試程式推測 mapping。

- 首次 Start 仍回傳 HTTP 202（不變）。
- Timeout 發生後透過 AgentInstance 終態快照觀察：`state = ERROR`、`last_error_code = RUNTIME_START_TIMEOUT`。
- 錯誤碼值、Timeout 行為、Preconditions、Purpose 及其他欄位均不變。

## 修改範圍

- `test-cases/runtime/cases.yaml`:RUNTIME-009 `expected.error_code` → `expected.last_error_code`（僅鍵名，值不變）。
- `contracts/versions.yaml`:`m0_m1_acceptance_contract.version` 0.2.0 → 0.2.1;`test_suite_version` 0.2.0 → 0.2.1；表頭 M0/M1 Frozen 版本註解同步更新為 v0.2.1。
- 新增本文件 `docs/change-requests/CR-002-RUNTIME-009-OBSERVABILITY.md`。

版本配套：`spec_version` 維持 0.1.0 DRAFT;`controller_api_version` 維持 0.2.0;`runtime_state_machine_version` 維持 0.2.0（本次無 normative change);Frozen Case ID 集合維持原 21 個不變；Deferred Case 集合與狀態全部不變。

## 明確未修改範圍

- `contracts/openapi/controller-api.yaml`
- `contracts/state-machines/hermes-runtime.yaml`
- `contracts/schemas/agent-instance.schema.json`
- `contracts/schemas/evaluation-case.schema.json`
- `contracts/errors/error-catalog.yaml`
- `docs/08-open-decisions.md`
- 其他 30 個 Test Case 的 Expected 與語意
- Platform / Portal / Controller / Bundle B Test Runner
- Bundle A / Bundle B Branch

## Impact

- Platform Impact:NONE。RESOURCE_STATE 錯誤本就必須保存於 AgentInstance，且 `last_error_code` 已存在於對外 Schema；本 CR 不要求 Platform 任何程式變更。
- Test Impact:RUNTIME-009 改由 AgentInstance 終態快照的 `last_error_code` 觀察：初始 POST 回 HTTP 202 後，輪詢 `GET /v1/instances/{instance_id}` 至 `state == ERROR`，斷言 `last_error_code == RUNTIME_START_TIMEOUT`。

## Validation Plan

1. 解析全部 JSON / YAML。
2. 全部 31 個 Test Case 依 `contracts/schemas/evaluation-case.schema.json` 驗證。
3. 全部 Case ID 唯一性檢查。
4. 以 `contract-m0-m1-v0.2.0` 為比較基準：其餘 30 個 Test Case 完整 Dictionary Deep Equality;RUNTIME-009 僅允許 `expected.error_code` → `expected.last_error_code`，值、其他欄位及結構完全一致。
5. Frozen Case ID 集合仍精確為原 21 個；10 個 Deferred Case 完全未改變。
6. 下列檔案相對 v0.2.0 Diff 為空：`contracts/openapi/controller-api.yaml`、`contracts/state-machines/hermes-runtime.yaml`、`contracts/schemas/agent-instance.schema.json`、`contracts/errors/error-catalog.yaml`。
7. `git diff --check`。

## Approval

Requirement Owner approved(2026-07-19)。Commit 與 PR 由 Git 歷史保存，本文件不預先填入 Commit Hash。
