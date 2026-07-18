# Contract與變更控制

> 文件目的：規範需求、Contract、實作、測試與Golden Cases如何同步變更，避免不同角色依賴不同版本。
>
> 適用角色：所有專案參與者。
>
> 文件狀態：Draft v0.1。

## 權威來源

- Requirements說明「為什麼與必須做到什麼」。
- OpenAPI/JSON Schema/State Machine說明「機器可觀察的精確行為」。
- Golden Cases說明「特定情境的可接受與禁止結果」。
- 程式與測試必須服從上述來源，而非彼此模仿。

## 變更流程

```text
提出Change
   ↓
標記影響Requirement/Contract/Test/Security
   ↓
需求或領域Owner核准
   ↓
先修改Contract與Expected Result
   ↓
平台與測試分支各自更新
   ↓
重新執行全部受影響測試
   ↓
更新版本Manifest與Traceability
```

## 需要核准的變更

- Must/Critical Requirement增刪或降級。
- API Endpoint、Schema、Status Code及Error Code。
- Runtime狀態轉移與Timeout語意。
- Golden Case Expected或禁止行為。
- Knowledge/Skill適用版本。
- Docker權限、Network或Volume邊界。
- 外部模型或資料傳輸方式。

## 版本規則

| 變更 | 版本示例 |
|---|---|
| 相容文字澄清 | 0.1.0 → 0.1.1 |
| 新增相容欄位／案例 | 0.1.x → 0.2.0 |
| 移除欄位或改變語意 | 0.x → 1.0.0或新Major |

## 禁止做法

- 因實作不符而直接修改測試Expected。
- 因測試不穩而跳過Critical Case。
- 在功能測試執行期間更新Dependency或Image。
- 同一版本Manifest指向不同Git Commit或Image Digest。
- 只改自然語言文件但不改機器Contract，或反之。

## 合併條件

每個Change至少附：

- 受影響Requirement ID。
- Contract Diff。
- 新增或更新的Test ID。
- 安全影響。
- Migration或相容性說明。
- 執行結果與Artifact位置。
