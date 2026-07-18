# 文件索引

> 文件目的：列出專案全部規格、Contract、測試資料與角色工作包，讓任何實作者能快速找到其工作所需輸入。
>
> 適用角色：所有專案參與者。
>
> 文件狀態：Draft v0.1。

## 共同文件

| 文件 | 用途 |
|---|---|
| `README.md` | 專案入口、真相優先順序與角色分工 |
| `docs/00-project-charter.md` | 商業問題、PoC目標、範圍及成功定義 |
| `docs/01-system-requirements.md` | 功能性及非功能性需求 |
| `docs/02-architecture.md` | Container、Network、Trust Boundary及資料流 |
| `docs/03-tech-stack.md` | 實作技術、版本基準及Build策略 |
| `docs/04-security-and-data-handling.md` | Docker、知識、模型、Log及測試安全規則 |
| `docs/05-build-and-test-guide.md` | Image Build、Compose及測試執行規格 |
| `docs/06-traceability-matrix.md` | Requirement、Contract、實作及測試對應 |
| `docs/07-definition-of-done.md` | 各階段完成與PoC驗收門檻 |
| `docs/08-open-decisions.md` | 開工前需由人決定或由環境驗證的事項 |
| `docs/09-change-control.md` | Contract、測試及版本變更流程 |
| `docs/10-handoff-map.md` | 三種角色應接收的最小文件集合與啟動順序 |

## 角色工作包

| 文件 | 交付對象 |
|---|---|
| `work-packets/platform-implementation.md` | 平台實作者 |
| `work-packets/test-suite-implementation.md` | 獨立測試實作者 |
| `work-packets/functional-test-execution.md` | 功能測試執行者 |

上述名稱只描述工作責任，不綁定任何特定AI、IDE、Git服務或CI產品。

## 機器可讀Contract

| 路徑 | 用途 |
|---|---|
| `contracts/openapi/portal-api.yaml` | Portal公開API |
| `contracts/openapi/controller-api.yaml` | Controller內部API |
| `contracts/schemas/*.schema.json` | Runtime、Task、Agent結果及錯誤Schema |
| `contracts/state-machines/hermes-runtime.yaml` | Runtime狀態轉移 |
| `contracts/errors/error-catalog.yaml` | 錯誤代碼與對外訊息 |
| `contracts/ui/ui-contract.yaml` | 路由、頁面狀態及穩定測試定位器 |
| `contracts/environment.yaml` | 環境變數、Network、Volume與Port |
| `contracts/versions.yaml` | 規格與元件版本Manifest |

## 測試輸入

| 路徑 | 用途 |
|---|---|
| `test-cases/runtime/cases.yaml` | Controller與Runtime案例 |
| `test-cases/control-wafer/cases.yaml` | 控片知識案例 |
| `test-cases/deployment-check/cases.yaml` | 上線檢查案例 |
| `test-fixtures/knowledge/` | 去敏感、合成的外部E2E Knowledge |

## 閱讀順序

```text
Project Charter
   ↓
System Requirements
   ↓
Architecture＋Security＋Tech Stack
   ↓
Machine-readable Contracts
   ↓
Role Work Packet
   ↓
Traceability＋Definition of Done
```
