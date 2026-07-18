# 工作包：功能測試執行

> 文件目的：提供任何終端代理、測試協調工具或人工執行者在乾淨環境中Build、部署、執行功能測試及保存證據的操作契約；不綁定任何特定AI、CI/CD或測試產品。
>
> 執行角色：Functional Test Executor。
>
> 前置條件：平台與測試套件已交付固定Commit，必要Image及內部Dependency可用。
>
> 預期產出：不可變更程式的獨立測試結果、Artifact、Exit Code及失敗分類。

## 角色定位

執行者是Orchestrator與Evidence Collector，不是程式修復者，也不是控片領域真相的最終裁判。

實際Pass/Fail來源：

- pytest及Playwright Exit Code。
- OpenAPI/JSON Schema Assertion。
- Golden Case決定性規則。
- 領域專家對`DOMAIN_REVIEW_REQUIRED`的核准。

## 允許動作

- 讀取文件、Contract、測試腳本與結果。
- Checkout指定Commit或使用乾淨Worktree。
- Build本專案明確定義的Docker Image。
- 執行核准的Compose與`scripts/run-functional-tests`。
- 讀取JUnit、Trace、Screenshot與Log。
- 將結果寫入`test-results/<run-id>/`。
- 分類失敗並提出可能原因。

## 禁止動作

- 修改`portal/`、`controller/`、`contracts/`、`tests/`或`test-cases/`。
- 修改Expected Result、Golden Cases或Pass門檻。
- Skip或重寫失敗案例。
- 使用全自動核准任意Shell操作的模式。
- 執行`docker system prune`或操作未帶Test Run Label的資源。
- 接觸Production Docker Context。
- 將真實Knowledge、Prompt或Log送往未核准外部模型。
- 建立Commit或Push變更。

## Preflight

1. 記錄Git Commit、Branch與`git status`。
2. 確認Source Tree乾淨。
3. 確認Docker Context為專用測試環境。
4. 確認必要Base Image與Dependency可在封閉網路取得。
5. 確認`.env.test`不含Production Credential。
6. 建立唯一`run_id`。
7. 寫出`test-results/<run-id>/manifest.yaml`。

## 固定執行順序

```text
scripts/build-all
scripts/run-unit-tests
scripts/run-controller-e2e
scripts/run-portal-e2e
scripts/run-live-agent-e2e
scripts/run-golden-cases
scripts/collect-test-results
```

- Controller Critical失敗後不得繼續Live Portal測試。
- Environment Failure不得誤報為Platform Defect。
- Critical安全案例第一次失敗即保留Fail，不得用Retry覆蓋。

## 失敗分類

| Code | 意義 | 下一個Owner |
|---|---|---|
| `PLATFORM_DEFECT` | 實作不符已凍結Contract | 平台實作者 |
| `TEST_DEFECT` | 測試本身不符Contract或不穩定 | 測試實作者 |
| `CONTRACT_AMBIGUITY` | Contract無法唯一決定Expected | 需求負責人 |
| `ENVIRONMENT_FAILURE` | Docker、Registry、Network或LLM不可用 | 環境管理者 |
| `MODEL_VARIANCE` | 結構正確但自然語言差異需Review | 測試＋領域Owner |
| `DOMAIN_REVIEW_REQUIRED` | 控片或SOP正確性無法自動判定 | 領域專家 |
| `SECURITY_FAILURE` | Secret、越權、未受管資源或禁止行為失敗 | 安全＋需求Owner |

## 測試摘要格式

```yaml
run_id: "..."
started_at: "UTC timestamp"
finished_at: "UTC timestamp"
git_commit: "..."
spec_version: "..."
image_digests: {}
environment: {}
suites:
  unit: {status: PASS, report: "..."}
  controller_e2e: {status: PASS, report: "..."}
  portal_e2e: {status: PASS, report: "..."}
  live_agent: {status: PASS, report: "..."}
  golden_cases: {status: REVIEW_REQUIRED, report: "..."}
critical_failures: []
failure_classifications: []
source_tree_clean_after_run: true
overall_status: PASS | FAIL | REVIEW_REQUIRED
```

## 最終檢查

- 檢查Git Tree仍乾淨。
- 確認只清理同一`run_id`的資源。
- 確認所有Secret已遮蔽。
- 確認JUnit及Summary可被機器讀取。
- 不將`REVIEW_REQUIRED`自動視為PASS。

完成宣告需符合`docs/07-definition-of-done.md`的「功能測試執行Done」。
