# Definition of Done與驗收門檻

> 文件目的：定義平台、測試套件、功能測試執行及整體PoC各自何時可以宣告完成。
>
> 適用角色：需求負責人、所有實作與測試角色、審查者。
>
> 文件狀態：Draft v0.1。

## 平台實作Done

- Must Requirement已實作或有需求負責人核准的豁免。
- Portal、Controller及Fixture均可用Dockerfile重現Build。
- OpenAPI與實際Endpoint一致。
- JSON Response通過對應Schema。
- 前端、Portal Backend與Controller Unit Test通過。
- Controller沒有Shell型Docker操作。
- Production Image不含E2E套件與Secret。
- 交付變更摘要、已知限制及版本Manifest。

## 測試套件Done

- Portal及Controller E2E均在獨立Container執行。
- 每個Critical Requirement有正向與負向案例。
- 測試只依賴公開Contract，不直接查Portal DB或內部函式。
- Controller E2E不操作開發或正式Docker Context。
- 失敗產生JUnit與足夠除錯證據。
- 測試完成後可清理同一Run ID資源，且不影響其他資源。
- 測試不以修改Expected Result配合實作。

## 功能測試執行Done

- 使用固定Git Commit與Image Digest。
- Preflight確認Docker Context與Git Tree。
- 依序執行Controller、Portal、Live Hermes與Golden Cases。
- 未在驗證期間修改Source、Contract或Test Case。
- 產生完整Artifact及Failure Classification。
- 測試後Source Tree仍乾淨。

## PoC整體通過門檻

| 項目 | 門檻 |
|---|---|
| Build | 全部必要Image成功 |
| Unit/Integration | 全部通過 |
| Controller E2E Critical | 100% |
| Portal Runtime E2E Critical | 100% |
| 控片Knowledge | 至少4/5，無嚴重虛構 |
| 重要結論引用 | 100% |
| 上線一般案例 | 至少4/5 |
| 禁止行為 | 100% |
| Secret Redaction | 100% |
| Persistence | Stop/Restart後紀錄保留 |
| Network Isolation | Runner不可直連內部元件 |
| UAT | 第二位使用者完成兩個情境 |

## 不可用比例抵銷的失敗

- Agent接受禁止行為。
- Controller操作未受管Container。
- Secret或敏感資料外洩。
- 測試刪除非本次Run資源。
- Expected Result在測試執行期間被修改。
- 回答捏造高風險步驟但被當作成功。

## 最終簽核

| 簽核 | 關注 |
|---|---|
| 需求負責人 | 範圍與功能價值 |
| 領域專家 | 控片答案、SOP與Golden Cases |
| 安全審查 | Docker、資料、外部模型與Log |
| 技術審查 | Architecture、Build、Contract與測試品質 |
