# Build與測試執行指南

> 文件目的：定義所有Production/Test Image、Compose檔案、標準執行順序及Artifact，使任何具備核准Docker環境的執行者可重現Build與驗證。
>
> 適用角色：平台實作者、測試實作者、功能測試執行者、環境管理者。
>
> 文件狀態：Draft v0.1；指令名稱是應實作的穩定入口，不綁定CI產品。

## 必要Image

| Image | Dockerfile | 性質 |
|---|---|---|
| `hermes-poc-portal` | `portal/Dockerfile` | Production |
| `hermes-poc-controller` | `controller/Dockerfile` | Production |
| `hermes-agent` | 既有核准Image | Production |
| `hermes-poc-portal-e2e` | `tests/portal-e2e/Dockerfile` | Test Only |
| `hermes-poc-controller-e2e` | `tests/controller-e2e/Dockerfile` | Test Only |
| `hermes-poc-hermes-fixture` | `tests/hermes-fixture/Dockerfile` | Test Only |

## 必要Compose

| 檔案 | 內容 |
|---|---|
| `compose.yaml` | Portal、Controller、Hermes、Network、Volume |
| `compose.e2e.portal.yaml` | Portal E2E Runner、e2e-network、Artifact Volume |
| `compose.e2e.controller.yaml` | Controller Under Test、Runner、隔離Docker Engine、Fixture |

## 標準Script Contract

下列名稱須由平台／測試實作者共同提供，實際可使用Shell、PowerShell、Make或跨平台程式實作：

| 入口 | 責任 |
|---|---|
| `scripts/build-all` | Build全部Production及Test Image |
| `scripts/run-unit-tests` | 執行前後端與Controller Unit Test |
| `scripts/run-controller-e2e` | 執行隔離Controller E2E |
| `scripts/run-portal-e2e` | 執行Portal瀏覽器/API E2E |
| `scripts/run-live-agent-e2e` | 使用真實Hermes與核准LLM執行功能測試 |
| `scripts/run-golden-cases` | 執行並彙整領域案例 |
| `scripts/run-functional-tests` | 依序呼叫全部必要測試並回傳整體Exit Code |
| `scripts/collect-test-results` | 彙整JUnit、JSON、Trace、Screenshot、Log與版本 |

## 完整執行順序

```text
Preflight
  ├─ verify clean Git tree
  ├─ verify Docker context
  ├─ verify required images/dependencies available
  └─ write version manifest
        ↓
Build
        ↓
Unit and Integration Tests
        ↓
Controller E2E
        ↓ only if pass
Portal E2E
        ↓ only if pass
Live Hermes E2E
        ↓
Golden Cases
        ↓
Collect Evidence and Verify Clean Tree (由外部Orchestrator執行)
```

**測試隔離要求 (EXECUTION-004)**：
- 測試必須由外部 Orchestrator 執行並在結束後比對 Git 狀態，確認沒有非預期的程式碼變更。
- 測試 Runner 執行期間，**絕對不得取得 `.git` 目錄或 Writable Source Mount**。
- 只允許將產出的 Artifact 寫入已被 `.gitignore` 排除的 `test-results` 目錄。

## Exit Code

| Exit Code | 意義 |
|---:|---|
| 0 | 全部必要與Critical Test通過 |
| 10 | Build失敗 |
| 20 | Unit/Integration失敗 |
| 30 | Controller E2E失敗 |
| 40 | Portal E2E失敗 |
| 50 | Live Hermes E2E失敗 |
| 60 | Golden Case失敗 |
| 70 | Environment/Preflight失敗 |
| 80 | Artifact或Cleanliness驗證失敗 |

具體Script可使用更細Exit Code，但不得將失敗轉成0。

## Artifact

```text
test-results/<run-id>/
├─ manifest.yaml
├─ summary.json
├─ junit/
├─ portal-e2e/
│  ├─ playwright-report/
│  ├─ screenshots/
│  ├─ traces/
│  └─ videos/
├─ controller-e2e/
│  ├─ http-traces/
│  ├─ docker-snapshots/
│  └─ logs/
└─ live-agent/
   ├─ raw-responses/
   ├─ normalized-results/
   └─ golden-case-summary.json
```

Artifact須先做Secret Redaction；Raw Response若含敏感資料，只能保存在核准位置且不得交給外部分析工具。

## LLM非決定性處理

- 不比較整段自然語言完全相同。
- 優先Assert Schema、Status、Source ID、必要步驟、禁止步驟與Missing Information。
- Critical安全規則使用決定性Assertion，不以另一個LLM作唯一裁判。
- 語意差異需要人工Review時標記`DOMAIN_REVIEW_REQUIRED`，不得自動Pass。

## 一鍵目標

最終必須能由一個穩定入口執行：

```text
scripts/run-functional-tests
```

執行者不應需要理解Portal或Controller內部實作即可取得明確Pass/Fail與證據。
