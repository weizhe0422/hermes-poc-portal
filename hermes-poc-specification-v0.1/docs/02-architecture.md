# 系統架構與信任邊界

> 文件目的：定義Portal、Controller、Hermes、資料與測試Runner之間的責任、Network與安全邊界，使實作與E2E能獨立開發。
>
> 適用角色：平台實作者、測試實作者、安全審查者、功能測試執行者。
>
> 文件狀態：Draft v0.1。

## 邏輯架構

```text
Browser
  │
  ▼
Portal Container
  ├─ React UI
  ├─ Portal API
  ├─ Hermes Adapter
  └─ SQLite Repository
  │                 │
  │ internal HTTP   │ agent HTTP
  ▼                 ▼
Controller       Hermes Container ──> Approved Internal LLM
  │                 │
  ▼                 ├─ Knowledge :ro
Docker Engine       ├─ Verified Skills :ro
                    └─ Hermes State rw
```

## Container責任

| Container | 可以做 | 不可以做 |
|---|---|---|
| Portal | UI、Task、Result、Evaluation、History、Controller/Hermes呼叫 | 直接接觸Docker Socket、任意執行Shell |
| Controller | 管理核准的Hermes Instance、Health、Log與Lifecycle | 管理未受管Container、接受任意Command/Image/Volume |
| Hermes | 讀取Knowledge/Skill、呼叫核准LLM、執行Agent工作 | 修改唯讀資產、操作Production |
| Portal E2E Runner | 經Portal執行使用者流程 | 直連Controller、Hermes、Docker及Knowledge |
| Controller E2E Runner | 經Controller API驗證生命週期 | 直連Docker API或Host Socket |

## Network

```text
e2e-network
├─ Portal E2E Runner
└─ Portal

portal-network
├─ Portal
└─ Controller

agent-network
├─ Portal
├─ Controller
└─ Hermes
```

- Host只發布Portal Port。
- Controller與Hermes使用Container DNS名稱，不使用固定IP。
- Controller E2E另使用`controller-e2e-network`及隔離的`docker-engine-test-network`。
- 內部LLM連線方式由`contracts/environment.yaml`定義，不可寫死。

## Volume

| Volume／Bind Mount | 使用者 | 模式 |
|---|---|---|
| `portal-data` | Portal | Read/Write |
| `hermes-state` | Hermes | Read/Write |
| `knowledge-control-wafer` | Hermes | Read Only |
| `knowledge-deployment` | Hermes | Read Only |
| `verified-skills` | Hermes | Read Only |
| `test-results` | Test Runner | Read/Write |

## 第一次Bootstrap

Portal無法在自己不存在時啟動自己，因此第一次安裝必須由外部Docker Compose建立環境：

```text
1. Build或載入核准Image
2. 建立Network與Volume
3. 建立Portal、Controller及Hermes Container
4. 啟動Portal與Controller
5. Hermes保持Stopped或由測試先停止
6. 後續Hermes Lifecycle由Portal→Controller操作
```

若Hermes Container尚未Provision，Portal顯示`NOT_PROVISIONED`，v0.1不允許Portal動態建立任意Container。

## Runtime狀態資料流

```text
Portal GET status
   ↓
Controller inspect managed container
   ↓
Hermes health probe
   ↓
LLM probe
   ↓
AgentInstance response
```

`Container Running`只能證明程序存在；只有Hermes與LLM Probe都符合Contract時才能回`HEALTHY`。

## Agent任務資料流

```text
UI request
   ↓
Portal validates request
   ↓
Portal creates TaskRun(QUEUED)
   ↓
Hermes Adapter sends normalized request
   ↓
Hermes reads read-only Knowledge/Skill
   ↓
Portal preserves raw response
   ↓
Schema validation and normalization
   ↓
TaskRun COMPLETED or FAILED
   ↓
UI shows result, sources and versions
```

## Trust Boundary

| 邊界 | 主要風險 | 控制 |
|---|---|---|
| Browser→Portal | 非法輸入、越權 | Schema、Request size、角色檢查 |
| Portal→Controller | 任意Docker操作 | 固定API、Instance ID、Label白名單 |
| Controller→Docker | Host Root等級權限 | 最小Controller、無Shell、隔離Network |
| Portal→Hermes | Prompt Injection、格式漂移 | 固定Prompt規則、Pydantic/JSON Schema、Raw保存 |
| Hermes→Knowledge | 敏感資料、過期版本 | Read Only、Metadata、版本與適用範圍 |
| Hermes→LLM | 資料外傳 | 僅核准內部Endpoint、Egress限制、稽核 |
| Test Runner→System | 測試誤操作 | 專用Context、Run Label、不得接觸正式資源 |

## 未來多Instance擴充

v0.1只有一個Instance，但設計必須：

- 不設定固定`container_name`。
- Hermes不發布固定Host Port。
- API、Task、Audit與Version皆保存`instance_id`。
- Controller內部以Instance Registry查找目標。
- 每個Instance未來可擁有獨立State Volume。

動態Create/Delete API不屬於v0.1，不得提前加入公開Contract。
