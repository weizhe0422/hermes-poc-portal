# 需求追溯矩陣

> 文件目的：將Must Requirement連結到API/UI Contract、負責元件與自動化測試，確保沒有未測需求或無需求依據的測試。
>
> 適用角色：需求負責人、平台實作者、測試實作者、審查者。
>
> 文件狀態：Draft v0.1；實作開始後須持續更新實際檔案與Test ID。

本表中的`RUNTIME-*`、`CW-*`與`DEPLOY-*`已有YAML案例；`PORTAL-*`、`EVAL-*`、`BUILD-*`、`SECURITY-*`等為測試實作者須依Contract落實的預定Test ID，尚未存在時不得誤標為已通過。

| Requirement | Contract | 實作責任 | Test Case |
|---|---|---|---|
| RT-01、02 | Portal `/api/runtime/status`、Runtime State Machine | Portal＋Controller | RUNTIME-001、002 |
| RT-03 | Controller Start API、UI `runtime-start` | Controller＋Portal | RUNTIME-003、PORTAL-RT-003 |
| RT-04 | Controller Stop API、UI `runtime-stop` | Controller＋Portal | RUNTIME-004 |
| RT-05 | Controller Restart API、UI `runtime-restart` | Controller＋Portal | RUNTIME-005 |
| RT-06 | Runtime State Machine idempotency | Controller | RUNTIME-006、007 |
| RT-07 | Error `OPERATION_CONFLICT` | Controller | RUNTIME-008 |
| RT-08 | Error `RUNTIME_START_TIMEOUT` | Controller | RUNTIME-009 |
| RT-09 | AgentInstance health fields | Controller | RUNTIME-010、011 |
| RT-10、11 | Controller API＋Security Contract | Controller | RUNTIME-012～015 |
| RT-12 | Runtime Event Schema | Portal | RUNTIME-016 |
| AG-02 | Portal Task API error contract | Portal | PORTAL-AG-002 |
| AG-03～06 | Task Run Schema | Portal | PORTAL-AG-003～006 |
| AG-07 | Source Reference Schema | Portal Adapter | CW-001、DEPLOY-001 |
| AG-08 | Error `AGENT_RESPONSE_INVALID` | Portal Adapter | PORTAL-AG-008 |
| AG-09、10 | Feedback與Task API | Portal | PORTAL-AG-009、010 |
| KW-01～03 | Knowledge Request/Response Schema | Portal＋Hermes Adapter | CW-001、002 |
| KW-04 | `INSUFFICIENT` | Hermes Adapter | CW-003 |
| KW-05 | `CONFLICT` | Hermes Adapter | CW-004 |
| KW-06 | `SUPPORTED` | Hermes Adapter | CW-001 |
| DP-01～05 | Deployment Request/Response Schema | Portal＋Hermes Adapter | DEPLOY-001～003 |
| DP-06 | Prohibited Actions Contract | Hermes Adapter | DEPLOY-004、005 |
| DP-07 | Deployment Response required fields | Portal | DEPLOY-001～005 |
| EV-01～08 | Evaluation Case Schema、Evaluation API | Portal | EVAL-001～006 |
| BLD-01～06 | Tech Stack、Environment Contract | Platform/Test Images | BUILD-001～006 |
| BLD-07 | Architecture Network Contract | Compose | SECURITY-001～003 |
| BLD-08 | Build/Test Guide | Test Runner | ARTIFACT-001 |
| E2E-01、02 | UI Contract、Network Contract | Portal E2E | SECURITY-001～003 |
| E2E-03、04 | Controller E2E Compose Contract | Controller E2E | CONTROLLER-ENV-001 |
| E2E-05～08 | Build/Test Guide | Test Runners | EXECUTION-001～004 |
| NF-01～03 | Security Guide | 全部元件 | SECURITY-004～008 |
| NF-04、05 | Architecture＋Task Schema | Portal／Hermes | PERSIST-001、002 |
| NF-06～08 | Environment Contract | Portal／Hermes | PERF-001～003 |
| NF-09～11 | Environment＋Schemas | 全部元件 | CONFIG-001、INSTANCE-001 |
| NF-12 | UI Contract | Portal | UAT-001 |

## 維護規則

- 新增Must Requirement時，必須同時新增Contract及至少一個Test ID。
- Test Case若沒有Requirement ID，必須標記為Exploratory或先取得需求核准。
- Contract改版後，Matrix、平台實作與測試必須在同一個Change中更新。
- `Not Automated`項目必須列出人工驗證步驟、負責人與證據格式。
