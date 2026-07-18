# 專案章程

> 文件目的：定義 Hermes PoC Portal 要解決的問題、待驗證假設、第一階段範圍及成功條件，防止開發過程擴張成完整企業平台。
>
> 適用角色：需求負責人、領域專家、所有實作與測試角色。
>
> 文件狀態：Draft v0.1；需求負責人核准後成為範圍基準。

## 問題陳述

組織內的領域經驗、SOP與操作方法分散在個人文件、HTML、投影片、圖片及原始碼中。現況缺乏一個能在封閉環境執行、可重用Knowledge與Verified Skill、且具有版本與稽核能力的低門檻入口。

## PoC核心假設

1. Hermes可以在封閉網路中讀取掛載的Knowledge與Verified Skill。
2. Portal可以降低一般使用者啟動及使用Hermes的門檻。
3. 同一套Portal可以支援知識查詢與流程檢查兩類不同任務。
4. 結果若附來源、版本、Golden Cases與人工審核，能比純對話結果更容易被信任。
5. Portal、Controller與Agent結果能透過Container化E2E重複驗證。

## 第一階段情境

| 情境 | 目的 | PoC中要證明的事情 |
|---|---|---|
| 控片知識助手 | 依HTML、圖片及Markdown回答控片相關問題 | 能引用來源、辨識資料不足與文件衝突 |
| 系統上線流程檢查 | 依Verified Skill檢查上線必要條件 | 能產生結構化檢查、Hold缺件並拒絕禁止行為 |

## In Scope

- 本機、封閉網路、Docker Compose部署。
- Portal、Controller、Hermes與測試Runner Container化。
- Portal啟動、停止、重新啟動一個預先建立的Hermes Instance。
- Portal與Controller分離，只有Controller接觸Docker Engine。
- 一個Hermes Instance；所有API與資料保留`instance_id`。
- Knowledge與Verified Skill唯讀掛載。
- Portal任務、引用、回饋、測試與版本紀錄。
- Portal E2E、Controller E2E、Live Hermes E2E及Golden Cases。
- 去敏感的合成Fixture供外部測試環境使用。

## Out of Scope

- Portal內建立、修改或自動發布Skill。
- 公開或企業Marketplace。
- Production部署、DB修改、設備控制或自動重啟Production。
- 任意Docker Image、Command、Volume或Container管理。
- 每人一個Hermes、多節點、自動擴縮或Kubernetes。
- 完整企業SSO、RBAC與高可用資料庫。
- 自動索引所有文件或自動訓練模型。
- 將敏感文件或Log傳送到未核准的外部AI服務。

## 角色

| 角色 | 決策或工作責任 |
|---|---|
| 需求負責人 | 範圍、優先級、Contract與變更核准 |
| 領域專家 | 控片真實性、SOP適用版本、Golden Cases與禁止行為 |
| 平台實作者 | Production程式、Dockerfile、Compose、白箱測試 |
| 測試實作者 | 獨立黑箱E2E、Fixture、測試報告 |
| 功能測試執行者 | 在乾淨環境Build、執行、保存證據與分類失敗 |

## PoC成功條件

1. Portal可從Hermes Stopped狀態完成Start並確認Healthy。
2. Runtime生命週期Critical E2E全部通過。
3. 控片Knowledge案例至少4/5通過，重要結論100%附來源，無嚴重虛構。
4. 上線流程一般案例至少4/5通過。
5. 禁止行為案例100%通過。
6. Portal與Hermes重啟後，Portal歷史與版本紀錄不遺失。
7. 外部E2E Runner無法直接存取Controller、Hermes、Docker Socket與Knowledge Volume。
8. 第二位未參與開發的人不需口頭指導即可完成兩個情境。

## 失敗也是有效結果

PoC若未達門檻，不得以修改Expected Result掩蓋。必須將失敗歸類為Platform Defect、Test Defect、Contract Ambiguity、Environment Failure、Model Variance或Domain Review Required，作為是否繼續投資的證據。
