## ADDED Requirements

### Requirement: 支援多種格式輸出選項
在 `start.py` 互動精靈中，SHALL 增加一個步驟詢問使用者是否需要同時輸出 WOFF2 格式。

#### Scenario: 使用者選擇同時輸出 WOFF2
- **WHEN** 執行到格式選擇步驟，使用者選擇「同時輸出 TTF 與 WOFF2」
- **THEN** 字型生成完成後，輸出目錄會同時出現 `.ttf` 與 `.woff2` 檔案

## MODIFIED Requirements

### Requirement: Wizard prompts for all required inputs
When `start.py` is executed, the wizard SHALL prompt the user sequentially for all required inputs: source font path (支援 .ttf, .otf, .ttc, .woff2), output font path, name-header file path, and font version number.

#### Scenario: User provides all required inputs
- **WHEN** the user runs `python start.py` and enters valid values for all required prompts (包括 .woff2 作為來源)
- **THEN** `build_font()` is called with the provided values and font generation completes successfully
