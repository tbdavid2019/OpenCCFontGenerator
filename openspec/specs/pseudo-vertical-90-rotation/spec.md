## ADDED Requirements

### Requirement: 座標旋轉運算
系統 MUST 對字型的每個 `glyf` 點資料應用順時針 90 度旋轉。

#### Scenario: 旋轉單個座標點
- **WHEN** 座標點為 (200, 800) 且旋轉中心為 (500, 500)
- **THEN** 新座標點 SHALL 為 (800, 800)

### Requirement: 固定等寬度度量
旋轉後的字型 MUST 將所有處理過的字元 `advanceWidth` 設定為固定數值。

#### Scenario: 設定固定寬度
- **WHEN** 字元旋轉完成後
- **THEN** `advanceWidth` SHALL 設定為 1000

### Requirement: 獨立的執行腳本
系統 MUST 提供 `run90.sh` 以執行整個旋轉流程。

#### Scenario: 執行腳本流程
- **WHEN** 使用者執行 `sh run90.sh input.ttf`
- **THEN** 系統依次執行 OpenCC 轉換與 90 度旋轉處理，最後輸出 `input_TC_Rotated90.ttf`
