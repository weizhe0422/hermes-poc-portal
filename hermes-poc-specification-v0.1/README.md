# Hermes PoC Portal 開工文件包

> 文件目的：提供平台實作者、獨立測試實作者及功能測試執行者共用的唯一規格入口，使三個角色可以分工開發而不依賴特定 AI、IDE、雲端平台或程式開發工具。
>
> 適用角色：需求負責人、領域專家、平台實作者、測試實作者、功能測試執行者、審查者。
>
> 文件狀態：Draft v0.1；Contract 尚未經需求負責人正式凍結前，不得視為最終驗收依據。

## 專案目標

建立一個在封閉網路、本機 Docker 環境執行的 Hermes PoC Portal。Portal 本身、Runtime Controller、Hermes Agent 與測試程式皆以 Container 執行。

PoC 必須證明以下完整流程：

1. Portal 可以顯示 Hermes Runtime 狀態。
2. 使用者可以透過 Portal 啟動、停止及重新啟動既有 Hermes Container。
3. 使用者可以操作「控片知識助手」及「系統上線流程檢查」兩個情境。
4. 回答及檢查結果可以追溯 Knowledge、Skill、模型與 Runtime 版本。
5. Portal 與 Controller 都有獨立、Container 化的黑箱 E2E。
6. 功能測試可以在乾淨的外部測試環境中，以固定指令執行並產生機器可讀報告。

## 文件入口

| 讀者 | 先閱讀 | 接著閱讀 |
|---|---|---|
| 所有人 | `docs/00-project-charter.md` | `docs/01-system-requirements.md` |
| 平台實作者 | `work-packets/platform-implementation.md` | Architecture、Tech Stack、API Contract |
| 獨立測試實作者 | `work-packets/test-suite-implementation.md` | Test Plan、API/UI Contract、Test Cases |
| 功能測試執行者 | `work-packets/functional-test-execution.md` | Build/Test Guide、Security Guide |
| 需求負責人 | `docs/06-traceability-matrix.md` | `docs/07-definition-of-done.md`、Open Decisions |

完整索引位於 [`docs/INDEX.md`](docs/INDEX.md)。

## 唯一真相與優先順序

當文件內容衝突時，依下列順序判定：

1. 已核准的 `contracts/` 機器可讀 Contract。
2. `docs/01-system-requirements.md` 的 Must Requirement。
3. `test-cases/` 中已核准的 Golden Cases。
4. Architecture、Tech Stack 與工作包。
5. 實作者自行推論或目前程式行為。

目前程式行為不得反過來改寫 Expected Result。若 Contract 有歧義，必須先建立 Decision，再修改 Contract、實作及測試。

## 三角色分工原則

| 角色 | 主要交付 | 禁止事項 |
|---|---|---|
| 平台實作者 | Portal、Controller、Dockerfile、Compose、Unit/Integration Test | 不得自行弱化 Contract 或 Golden Cases |
| 獨立測試實作者 | Portal E2E、Controller E2E、Fixture、測試報告 | 不得為配合現有實作而改 Expected Result |
| 功能測試執行者 | Build、Deploy、Execute、Collect Evidence、Failure Classification | 驗證階段不得修改平台、測試或 Contract |

## 開工前必要動作

1. 需求負責人填完 `docs/08-open-decisions.md` 中的 Blocker。
2. 領域專家以真實但去敏感資料取代或補充測試 Fixture。
3. 核准 `contracts/openapi/`、`contracts/schemas/`、狀態機及錯誤代碼。
4. 建立三個獨立分支或 Git Worktree。
5. 所有角色記錄同一個 `spec_version` 與 Git Commit。

## 建議分支

```text
main
├─ feature/platform-v0.1
├─ feature/test-suite-v0.1
└─ validation/functional-v0.1
```

PoC 建議使用 Monorepo，以避免 Compose、Contract、Fixture 與 Image 版本分離。
