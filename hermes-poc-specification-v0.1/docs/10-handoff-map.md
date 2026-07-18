# 角色交付與開工對照表

> 文件目的：定義三種工作角色各自應收到哪些文件、第一個動作及回報格式，讓需求負責人可以將同一Repository交給不同工程師或開發代理而不綁定特定產品。
>
> 適用角色：需求負責人、平台實作者、測試實作者、功能測試執行者。
>
> 文件狀態：Draft v0.1。

## 實體Bundle檔案

| 邏輯Bundle | 實體交付檔 | 何時使用 |
|---|---|---|
| Bundle A：平台實作 | `handoff-bundles/platform-implementation-bundle-v0.1.zip` | Contract初步凍結後立即交付 |
| Bundle B：獨立測試套件實作 | `handoff-bundles/test-suite-implementation-bundle-v0.1.zip` | 與平台實作平行開始 |
| Bundle C：功能測試執行 | `handoff-bundles/functional-test-execution-starter-bundle-v0.1.zip` | 平台與測試程式合併成固定Commit後使用 |

Bundle C目前是執行規則與Contract的Starter Bundle，不包含尚未開發的Portal、Controller與測試程式。最終功能測試時，必須把Bundle C的規則與完成後的完整Repository一起交給執行者，不能只交ZIP就要求執行測試。

## 共用基準

三個角色都必須能讀取：

```text
README.md
docs/00-project-charter.md
docs/01-system-requirements.md
contracts/
docs/04-security-and-data-handling.md
docs/09-change-control.md
```

任何角色發現矛盾時，都應停止受影響項目並回報`CONTRACT_AMBIGUITY`，而不是自行修正共同Contract。

## Bundle A：平台實作

### 額外輸入

```text
docs/02-architecture.md
docs/03-tech-stack.md
docs/05-build-and-test-guide.md
docs/07-definition-of-done.md
docs/08-open-decisions.md
work-packets/platform-implementation.md
test-cases/（Read Only）
```

### 第一次工作

1. 只讀盤點全部Contract與Open Decision。
2. 產生Requirement-to-Module實作計畫。
3. 列出Blocker與Contract Ambiguity。
4. Blocker解除後，先完成P-M0與P-M1，不一次實作全部情境。

### 通用啟動指令文字

> 你是平台實作者。先閱讀`work-packets/platform-implementation.md`及其列出的共同文件。不要修改Contract或Test Case。先回報你理解的範圍、模組切分、Blocker與P-M0/P-M1計畫，確認後才開始實作。每個里程碑必須附Requirement ID、測試結果與已知限制。

## Bundle B：獨立測試套件實作

### 額外輸入

```text
docs/02-architecture.md
docs/05-build-and-test-guide.md
docs/06-traceability-matrix.md
docs/07-definition-of-done.md
work-packets/test-suite-implementation.md
test-cases/
test-fixtures/
```

### 第一次工作

1. 驗證OpenAPI、Schema、UI Contract與Test Case是否足以決定Expected。
2. 建立Coverage Gap表。
3. 先完成Fixture、Runner Dockerfile與Controller基本E2E骨架。
4. 平台Endpoint未完成時，依Contract建立測試，不以Mock行為改寫Contract。

### 通用啟動指令文字

> 你是獨立黑箱測試實作者。先閱讀`work-packets/test-suite-implementation.md`及其列出的共同文件。平台目前行為不是Expected的來源；不得修改平台、Contract或Golden Cases。先產生Coverage Gap、Fixture設計及T-M0/T-M1計畫，確認後再實作Container化Portal與Controller E2E。

## Bundle C：功能測試執行

### 額外輸入

```text
docs/05-build-and-test-guide.md
docs/06-traceability-matrix.md
docs/07-definition-of-done.md
work-packets/functional-test-execution.md
已建置或可建置的完整Repository
```

### 第一次工作

1. 不修改任何Source或Expected。
2. 先執行Preflight並產生Run ID與Version Manifest。
3. 使用固定入口執行測試。
4. 收集Artifact並分類失敗。
5. 測試後證明Source Tree仍乾淨。

### 通用啟動指令文字

> 你是功能測試執行者，不是程式修復者。閱讀`work-packets/functional-test-execution.md`後，在專用測試Docker Context執行固定測試流程。不得修改Source、Contract、Test或Expected；不得使用全自動Shell核准。輸出Version Manifest、JUnit、Artifact位置、整體Exit Code與失敗分類。

## 交付順序

```text
需求負責人凍結Contract
       ↓
Bundle A與Bundle B平行工作
       ↓ 每個Milestone提早整合
平台候選Commit＋測試候選Commit
       ↓
整合Commit固定
       ↓
Bundle C在乾淨環境執行
       ↓
需求／領域／安全簽核
```

## 第一天建議

1. 先處理`docs/08-open-decisions.md`中M0/M1的Blocker。
2. 將規格提交為第一個固定Git Commit並記錄`spec_version: 0.1.0`。
3. 將Bundle A交給平台實作者，只要求P-M0與P-M1。
4. 同時將Bundle B交給測試實作者，只要求T-M0與T-M1。
5. 兩邊完成第一個里程碑後立即整合，不等待所有功能完成。
6. 此時不要啟動Bundle C；Bundle C屬於整合候選版的獨立驗證階段。

## 防止角色越界

| 目錄 | 建議Owner | 其他角色權限 |
|---|---|---|
| `contracts/`、`test-cases/` | 需求／領域Owner | Read Only，變更需核准 |
| `portal/`、`controller/` | 平台實作者 | 測試實作者Read Only |
| `tests/`、E2E Compose | 測試實作者 | 平台實作者可Review，不改Expected |
| `test-results/` | 功能測試執行者 | 其他角色讀取分析 |

Monorepo可以使用Branch、Worktree、CODEOWNERS或同等審查規則落實此邊界，但文件本身不要求特定Git服務。
