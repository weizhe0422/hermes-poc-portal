# 系統需求規格

> 文件目的：提供可追蹤的功能性與非功能性Requirement ID，作為平台實作、測試設計與PoC驗收的共同基準。
>
> 適用角色：需求負責人、平台實作者、測試實作者、功能測試執行者。
>
> 文件狀態：Draft v0.1；Must Requirement變更必須走Change Control。

## 環境假設

| 項目 | v0.1基準 |
|---|---|
| 執行位置 | 單一本機Docker Engine |
| 網路 | 封閉網路；只允許核准的內部LLM端點 |
| Portal | Container化，唯一發布到Host的服務 |
| Controller | Container化，僅內部網路可達 |
| Hermes | 一個預先建立、由Controller管理的Instance |
| Database | SQLite持久化Volume |
| 使用者 | 本機Operator；保留`actor_id`，不實作完整SSO |
| Knowledge／Skill | 唯讀掛載 |

## Runtime與Controller

| ID | 需求 | 優先級 | 驗收摘要 |
|---|---|---:|---|
| RT-01 | Portal須顯示Docker、Controller、Hermes及LLM狀態 | Must | 四項狀態可分別辨識 |
| RT-02 | Runtime狀態須符合正式狀態機 | Must | 不出現Contract外狀態 |
| RT-03 | Operator可透過Portal啟動既有Hermes | Must | Stopped→Starting→Healthy |
| RT-04 | Operator可透過Portal正常停止Hermes | Must | 不刪除Container或Volume |
| RT-05 | Operator可透過Portal重新啟動Hermes | Must | 重啟後再次Healthy |
| RT-06 | Start、Stop、Restart必須具冪等性 | Must | 重複要求不重複建立或破壞狀態 |
| RT-07 | 同一Instance同時只能有一個生命週期操作 | Must | 衝突要求回409 |
| RT-08 | 啟動須有可設定逾時 | Must | 非同步操作逾時後進入ERROR並保存`RUNTIME_START_TIMEOUT` |
| RT-09 | Healthy必須包含Hermes API與LLM Probe | Must | Container Running不等於Healthy |
| RT-10 | Controller只能管理白名單名稱及Label的Container | Must | 未受管理Container操作被拒絕 |
| RT-11 | Controller不得接受任意Shell、Image、Command或Volume | Must | API不存在任意執行入口 |
| RT-12 | Runtime操作須留下稽核事件 | Must | 保存actor、action、instance、result、time |
| RT-13 | Portal須能顯示經遮蔽的最近Log | Should | Secret不出現在回應 |

## 共用Agent任務

| ID | 需求 | 優先級 | 驗收摘要 |
|---|---|---:|---|
| AG-01 | 首頁須提供兩個情境入口 | Must | 控片知識、上線檢查均可進入 |
| AG-02 | Hermes非Healthy時不得送出Agent任務 | Must | UI鎖定且API回409 |
| AG-03 | 每筆任務須保存唯一`task_id`及`instance_id` | Must | 可由History查回 |
| AG-04 | 任務狀態須為Queued、Running、Completed、Failed或Cancelled | Must | Schema驗證通過 |
| AG-05 | Portal須保存輸入、結構化結果與Hermes Raw Response | Must | Parse失敗仍有證據 |
| AG-06 | 每筆任務須保存Hermes、模型、Knowledge及Skill版本 | Must | 版本欄位完整 |
| AG-07 | 重要結論須包含來源識別、版本及章節 | Must | 引用Schema驗證通過 |
| AG-08 | 結構解析失敗須標記Parse Error，不得偽裝成功 | Must | 原始輸出保留 |
| AG-09 | 使用者可提交正確、部分正確、錯誤及備註 | Must | Feedback可查詢 |
| AG-10 | 使用者可查看任務歷史 | Must | 重啟Portal後仍存在 |
| AG-11 | 使用者可匯出Markdown或JSON結果 | Should | 檔案包含版本與引用 |

## 控片知識助手

| ID | 需求 | 優先級 | 驗收摘要 |
|---|---|---:|---|
| KW-01 | 接受自然語言控片問題 | Must | 能建立Knowledge Task |
| KW-02 | 回答須以掛載Knowledge為依據 | Must | 無來源的關鍵結論判Fail |
| KW-03 | 可引用HTML、Markdown及圖片來源 | Must | 至少支援三類來源Metadata |
| KW-04 | 文件未定義時回`INSUFFICIENT` | Must | 不自行補完答案 |
| KW-05 | 來源矛盾時回`CONFLICT` | Must | 列出衝突來源及版本 |
| KW-06 | 可明確回答時回`SUPPORTED` | Must | `answer`與`sources`完整 |
| KW-07 | 回答須顯示適用版本或範圍警告 | Should | 有Metadata時呈現 |

## 系統上線流程檢查

| ID | 需求 | 優先級 | 驗收摘要 |
|---|---|---:|---|
| DP-01 | 接受系統、環境、版本、Change單、備份、回復方案與驗證方式 | Must | Request Schema驗證 |
| DP-02 | 缺必要資料時回`NEEDS_INFO`或`HOLD` | Must | 不得回PASS |
| DP-03 | 依Verified Skill產生結構化檢查項目 | Must | 每項有status及evidence |
| DP-04 | 整體狀態僅可為PASS、FAIL、HOLD、NEEDS_INFO | Must | Schema驗證 |
| DP-05 | 重要檢查須引用SOP或Skill來源 | Must | 來源完整 |
| DP-06 | 跳過核准、直接修改Production或其他禁止行為必須拒絕 | Must/Critical | 全部Golden Cases通過 |
| DP-07 | 結果須包含warning、missing information及next action | Must | 必要欄位存在 |

## 驗證中心

| ID | 需求 | 優先級 | 驗收摘要 |
|---|---|---:|---|
| EV-01 | 測試案例須來自版本化YAML或JSON | Must | 案例含case_id及requirement_ids |
| EV-02 | 支援單筆案例執行 | Must | 產生evaluation run |
| EV-03 | 支援情境批次執行 | Should | 可產生suite summary |
| EV-04 | 顯示Expected與Actual | Must | Reviewer可比較 |
| EV-05 | 支援自動與人工判定 | Must | verdict及reviewer可保存 |
| EV-06 | Critical案例不得由總通過率抵銷 | Must | 任一Critical Fail則suite Fail |
| EV-07 | 每次Evaluation須保存完整元件版本 | Must | Version Manifest完整 |
| EV-08 | 報告須輸出JUnit及JSON摘要 | Must | 外部執行工具可讀 |

## Build與Container

| ID | 需求 | 優先級 | 驗收摘要 |
|---|---|---:|---|
| BLD-01 | Portal、Controller、Portal E2E、Controller E2E及Fixture均有獨立Dockerfile | Must | 五個Image可Build |
| BLD-02 | Production Dockerfile須採Multi-stage或最小Runtime Build | Must | 最終Image無Build Cache與測試工具 |
| BLD-03 | Runtime Process須以非root使用者執行 | Must | UID不為0；Docker Socket風險另行治理 |
| BLD-04 | Base Image及Dependency須鎖定版本 | Must | Lockfile存在且不使用latest |
| BLD-05 | Secret不得寫入Image Layer | Must | Image history掃描無Secret |
| BLD-06 | 支援公司內部Registry與封閉網路Build | Must | 不需即時連外下載 |
| BLD-07 | Portal須是Host唯一公開Port | Must | Controller與Hermes不可由Host直連 |
| BLD-08 | Test Artifact須寫入獨立Volume | Must | 測試後可取得JUnit、Trace與Log |

## E2E

| ID | 需求 | 優先級 | 驗收摘要 |
|---|---|---:|---|
| E2E-01 | Portal E2E須由獨立Container執行 | Must | Host不需安裝瀏覽器測試套件 |
| E2E-02 | Portal E2E Runner只能連Portal | Must | 直連Controller／Hermes失敗 |
| E2E-03 | Controller E2E須由獨立Container執行 | Must | Host不需安裝pytest |
| E2E-04 | Controller E2E須使用隔離Docker Engine或專用測試Context | Must | 不操作開發／正式Container |
| E2E-05 | E2E失敗須回非0 Exit Code | Must | CI可正確判Fail |
| E2E-06 | 失敗須保存足夠證據 | Must | JUnit、HTTP Trace、Log；UI另含Screenshot／Trace |
| E2E-07 | Critical Case禁止自動重試掩蓋失敗 | Must | 報告保留首次結果 |
| E2E-08 | 測試後不得修改Source、Contract、Test Case | Must | Git工作目錄仍乾淨 |

## 非功能性需求

| ID | 類別 | 需求 | PoC門檻 |
|---|---|---|---|
| NF-01 | 安全 | 未核准資料不得傳送外部服務 | 0筆外傳 |
| NF-02 | 安全 | Knowledge與Verified Skill唯讀 | 修改嘗試失敗 |
| NF-03 | 安全 | Secret須在UI、API與Log遮蔽 | 測試Secret不可見 |
| NF-04 | 可靠 | Hermes故障不影響Portal管理頁 | Portal仍可用 |
| NF-05 | 持久 | Portal與Hermes重啟後紀錄不遺失 | Persistence E2E通過 |
| NF-06 | 效能 | 標準問題15秒內開始回應 | 記錄P95；模型瓶頸另列 |
| NF-07 | 效能 | 一般任務目標90秒內完成 | 可設定Timeout |
| NF-08 | 容量 | 支援至少3個同時任務 | 無資料錯置 |
| NF-09 | 可維護 | 端點、路徑、逾時與版本不得寫死 | Environment Contract控制 |
| NF-10 | 可觀測 | Health、Status、Duration與結構化Log可取得 | 驗證報告完整 |
| NF-11 | 可擴充 | 所有任務保留`instance_id` | 單Instance亦不可省略 |
| NF-12 | 易用 | 第二位使用者無口頭指導完成兩情境 | UAT通過 |

## Requirement解讀規則

- `Must/Critical`：未通過即PoC失敗。
- `Must`：必須在v0.1完成；除非需求負責人正式降級。
- `Should`：不阻擋核心Demo，但必須記錄未完成理由。
- 未寫入本文件或Contract的功能不因AI推論而自動成為需求。
