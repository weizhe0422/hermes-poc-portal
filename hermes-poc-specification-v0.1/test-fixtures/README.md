# 合成測試Fixture

> 文件目的：提供不含真實半導體、設備、廠區、主機或帳密資訊的固定Knowledge與Skill，讓外部Container E2E可重現SUPPORTED、INSUFFICIENT、CONFLICT、HOLD與禁止行為。
>
> 適用角色：測試實作者、功能測試執行者、平台實作者的本機整合測試。
>
> 文件狀態：Synthetic Test Data v0.1；不得將內容視為真實控片或上線作業規範。

## 重要聲明

本目錄所有內容均為測試專用的虛構規則。真實PoC驗收必須由領域專家以核准資料建立另一組Private Fixture，且不得提交至可被外部AI讀取的位置。

## 資料集

| 路徑 | 用途 |
|---|---|
| `knowledge/control-wafer/CW-TEST-001.md` | 明確答案與判斷分支 |
| `knowledge/control-wafer/CW-TEST-002.md` | 與v1產生版本衝突 |
| `knowledge/control-wafer/IMG-CW-001.svg` | 合成狀態畫面 |
| `knowledge/control-wafer/IMG-CW-001.md` | 圖片業務含義伴隨說明 |
| `knowledge/deployment/DEPLOY-SOP-TEST-001.md` | 合成上線規則 |
| `skills/deployment-check/SKILL.md` | 合成Verified Skill |

## 使用規則

- Synthetic E2E只驗證平台與Agent行為，不代表Domain Accuracy。
- Live Domain E2E應使用另外掛載的Private Fixture。
- 測試報告須標記`fixture_type: SYNTHETIC`或`PRIVATE_DOMAIN`。
