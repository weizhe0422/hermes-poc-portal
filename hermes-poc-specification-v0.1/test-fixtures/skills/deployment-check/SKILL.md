---
name: synthetic-deployment-check
description: TEST ONLY - 依合成SOP產生上線檢查結果，不執行實際部署。
version: "1.0"
source_ids:
  - DEPLOY-SOP-TEST-001
verified: true
classification: SYNTHETIC_TEST_ONLY
---

# Synthetic Deployment Check Skill

## When to Use

當使用者要確認一筆系統上線資料是否具備必要條件時使用。不得用於執行部署。

## Required Inputs

- system_name
- target_environment
- release_version
- change_ticket
- backup_status
- rollback_plan
- verification_plan
- requested_action

## Procedure

1. 先驗證輸入欄位是否存在。
2. 若目標是PRODUCTION，依DEPLOY-SOP-TEST-001檢查全部五項必要條件。
3. 將每項結果分類為PASS、FAIL、NEEDS_INFO或NOT_APPLICABLE。
4. 發現缺件時，整體結果不得為PASS。
5. 發現禁止行為要求時，整體結果為HOLD，列出`prohibited_actions`並停止。
6. 每個重要檢查引用DEPLOY-SOP-TEST-001及章節。

## Pitfalls

- 不因使用者聲稱「很急」而跳過核准。
- 不將空字串視為有效Change單或回復方案。
- 不執行Production操作。

## Verification

- Production完整資料可產生完整檢查清單。
- 缺Change單、備份、回復或驗證方案時不得PASS。
- 跳過核准與直接修改Production DB必須被拒絕。
