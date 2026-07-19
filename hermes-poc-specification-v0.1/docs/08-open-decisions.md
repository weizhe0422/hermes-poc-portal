# 開放決策與環境待確認事項

> 文件目的：明確列出規格無法代替真實環境決定的Blocker，避免實作者自行假設Hermes API、模型、Registry或領域Ground Truth。
>
> 適用角色：需求負責人、環境管理者、領域專家、技術負責人。
>
> 文件狀態：整體Spec仍為Draft v0.1.0，但M0/M1 Contract子集合已Frozen為v0.2.0。Frozen M0/M1 Contract若要修改，必須提出Change Request、更新版本並重跑受影響測試。Future Draft Contract可以調整，但不得暗中改變Frozen M0/M1語意。

| ID | 問題 | 建議預設 | Owner | 截止點 | 狀態 |
|---|---|---|---|---|---|
| OD-01 | 實際Hermes Image Tag/Digest為何？ | 使用目前已驗證Image並鎖Digest | Environment | M0 | Blocker |
| OD-02 | Hermes任務API與Health API精確路徑？ | 以Adapter配置，不寫死 | Platform | M1 | Blocker |
| OD-03 | Hermes是否提供直接LLM Probe？ | Synthetic Probe只能驗證介面，不能取代Live Hermes Probe，實作不得自行猜測Live Endpoint。 | Platform | M1 | Blocker |
| OD-04 | 內部LLM Base URL、模型名及Context？ | 由Secret/Env注入 | Environment | M1 | Blocker |
| OD-05 | Host OS與Docker Engine/Compose版本？ | 記入Version Manifest | Environment | M0 | Blocker |
| OD-06 | 內部Registry位址及可用Base Image？ | Node 24/Python 3.13/Playwright Mirror | Environment | M0 | Blocker |
| OD-07 | Portal對Host發布Port？ | 8080 | Product | M0 | Open |
| OD-08 | Controller測試用隔離Docker方式？ | Rootless或專用測試Daemon | Security | M2 | Blocker |
| OD-09 | SQLite備份與Retention多久？ | PoC保留30日 | Product | M3 | Open |
| OD-10 | 真實控片Fixture與Expected Result由誰核准？ | 指定Domain Expert | Product | M4 | Blocker |
| OD-11 | 上線SOP及禁止行為版本？ | 使用已核准最新版本 | Domain | M4 | Blocker |
| OD-12 | 功能測試執行工具是否會呼叫外部模型？ | 未核准則只用合成Fixture或不用AI執行 | Security | Validation | Blocker |
| OD-13 | 第二位UAT使用者是誰？ | 未參與實作的工程師 | Product | M6 | Open |
| OD-14 | PoC是否需要Streaming Response？ | v0.1先不做 | Product | M1 | Decided |
| OD-15 | 是否需要登入？ | localhost單Operator；保留actor_id | Product | M0 | Decided |

## 決策記錄格式

```yaml
decision_id: OD-XX
decision: "核准內容"
rationale: "原因"
decided_by: "角色或姓名"
decided_at: "UTC timestamp"
affected_contracts:
  - "檔案路徑"
```

決策完成後應更新本表、相關Contract及`contracts/versions.yaml`。
