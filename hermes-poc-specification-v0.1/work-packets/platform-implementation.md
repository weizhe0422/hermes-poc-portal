# 工作包：平台實作

> 文件目的：提供任何程式開發代理或工程師實作Portal、Controller、Dockerfile、Compose與白箱測試所需的完整任務邊界；不綁定特定AI、IDE或開發平台。
>
> 執行角色：Platform Implementer。
>
> 前置條件：已閱讀Project Charter、System Requirements、Architecture、Tech Stack、Security及已凍結Contract。
>
> 預期產出：可Build、可啟動、符合Contract且具Unit/Integration Test的Production平台。

## 任務目標

實作一個Container化Portal與一個獨立Runtime Controller，使本機使用者能啟停既有Hermes、執行兩個業務情境、保存可追溯結果並供外部E2E驗證。

## 唯一輸入

- `docs/00-project-charter.md`
- `docs/01-system-requirements.md`
- `docs/02-architecture.md`
- `docs/03-tech-stack.md`
- `docs/04-security-and-data-handling.md`
- `contracts/`
- `test-cases/`（了解驗收，不可自行改Expected）

若文件矛盾，停止相關工作並提出`CONTRACT_AMBIGUITY`，不得自行選擇較容易實作的版本。

## 允許修改

```text
portal/
controller/
tests/hermes-fixture/
compose.yaml
.dockerignore
.env.example
scripts/build-all*
scripts/run-unit-tests*
資料庫Migration
```

若需修改`contracts/`或`test-cases/`，必須先提交Change Request並取得核准。

## 必要交付

### Portal

- React/TypeScript UI及FastAPI Backend。
- Runtime首頁、兩個情境頁、History及Evaluation頁。
- Controller Client及Hermes Adapter。
- SQLite Model、Migration與Persistence。
- JSON Schema/Pydantic驗證及Raw Response保存。
- Structured Log及Correlation ID。
- `portal/Dockerfile`與Health Endpoint。

### Controller

- FastAPI內部API。
- Docker SDK Adapter，不使用Shell。
- Instance Registry、Label/Name雙白名單。
- Start/Stop/Restart冪等、Lock、Timeout與Health Probe。
- Log Tail與Secret Redaction。
- `controller/Dockerfile`與Health Endpoint。

### Deployment

- `compose.yaml`。
- Portal/Controller/Agent Network。
- Portal/Hermes持久化Volume。
- Knowledge/Verified Skill唯讀Mount。
- Host只發布Portal Port。
- 不設定Hermes固定`container_name`或Host Port。

### 白箱測試

- Frontend Component Test。
- Portal Backend Unit/Repository/API Test。
- Controller Docker Client Mock Test。
- State Machine、Idempotency、Lock、Redaction與Error Mapping Test。
- Hermes Adapter有效、無效及Timeout Response Test。

## 里程碑

| Milestone | 產出 | 完成條件 |
|---|---|---|
| P-M0 | Repo骨架、Lockfile、Dockerfile、Compose | 全部Image可Build |
| P-M1 | Controller API與Runtime State | Unit/Integration通過 |
| P-M2 | Portal Runtime首頁 | 可透過Portal啟停Hermes |
| P-M3 | Task/History/Persistence | Raw/Normalized/Version可查 |
| P-M4 | 控片Knowledge情境 | 三種Knowledge狀態可呈現 |
| P-M5 | 上線檢查情境 | 結構化結果及禁止行為呈現 |
| P-M6 | Evaluation與Artifact整合 | 可供外部E2E使用 |

每個Milestone完成即合併並交由獨立測試實作者驗證，不等全部功能完成才第一次整合。

## 穩定測試介面

- 必須符合`contracts/openapi/`。
- UI Route及Accessible Name／`data-testid`符合`contracts/ui/ui-contract.yaml`。
- 不得要求E2E查內部DB或共享程式Library。
- 錯誤回應必須符合Error Schema及Catalog。

## 禁止事項

- 不得修改Golden Cases讓現有行為通過。
- 不得提供任意Docker Command API。
- 不得把Docker Socket掛給Portal。
- 不得把Secret或真實KnowledgeBuild進Image。
- 不得為E2E加入只在測試中繞過安全控制的公開Backdoor。
- 不得提前實作動態任意Instance Create/Delete。

## 完成報告格式

```yaml
role: platform-implementer
git_commit: "..."
implemented_requirements: []
deferred_requirements: []
contract_deviations: []
images:
  portal: "tag@digest"
  controller: "tag@digest"
unit_test_summary: "..."
known_limitations: []
security_notes: []
```

完成宣告需符合`docs/07-definition-of-done.md`的「平台實作Done」。
