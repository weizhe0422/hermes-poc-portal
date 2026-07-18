# 實體角色Bundle說明

> 文件目的：說明三個ZIP Bundle的交付對象、使用時機及限制；Bundle內容以工作責任分類，不綁定任何特定AI、IDE或CI產品。
>
> 適用角色：需求負責人、平台實作者、測試實作者、功能測試執行者。
>
> 文件狀態：Draft v0.1。

## Bundle A

`platform-implementation-bundle-v0.1.zip`

- 用於Portal、Controller、Dockerfile、Compose及白箱測試開發。
- 包含共同需求、Architecture、Tech Stack、Security、Contract、案例及平台工作包。
- Test Case在此Bundle中為Read Only。

## Bundle B

`test-suite-implementation-bundle-v0.1.zip`

- 用於Portal E2E、Controller E2E、Fixture及測試Runner開發。
- 包含共同需求、Contract、Test Case、Synthetic Fixture及獨立測試工作包。
- 平台目前行為不是Expected Result來源。

## Bundle C

`functional-test-execution-starter-bundle-v0.1.zip`

- 用於Build、部署、功能測試執行、Artifact收集及Failure Classification。
- 現階段只包含執行Contract與測試基準。
- 最終使用時必須搭配平台與測試程式已合併的固定Git Commit。
- 執行者不得修改Source、Contract、Test或Expected Result。
