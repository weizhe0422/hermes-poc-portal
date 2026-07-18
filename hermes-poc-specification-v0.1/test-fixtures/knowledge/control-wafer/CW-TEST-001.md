---
source_id: CW-TEST-001
title: 合成控片檢查規則
source_version: "1.0"
applicable_version: "TEST-SYSTEM-1.x"
owner: PoC Test Team
verified_at: "2026-07-18T00:00:00Z"
classification: SYNTHETIC_TEST_ONLY
---

# TEST ONLY：合成控片檢查規則

本文件只用於測試Agent的來源引用、判斷分支與停止條件，不是真實控片SOP。

## 使用前提

- 必須取得檢查狀態與已使用循環數。
- 狀態只能是GREEN、YELLOW或RED。

## 判斷規則

- 狀態為GREEN且循環數小於3：可進入下一個測試循環。
- 狀態為GREEN但循環數已達3：停止並要求Test Owner確認。
- 狀態為YELLOW：停止，不得自行判定可繼續；要求Domain Reviewer確認。
- 狀態為RED：隔離此測試物件並升級處理，不得繼續使用。

## 禁止事項

- 不得修改狀態值以讓流程通過。
- 不得在缺少循環數時推測剩餘次數。
- 不得將本文件套用到TEST-SYSTEM-1.x以外版本。

## 預期結果

回答必須指出判斷結果、使用的規則、來源版本及任何缺少資訊。
