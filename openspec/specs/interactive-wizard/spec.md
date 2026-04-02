## ADDED Requirements

### Requirement: Wizard prompts for all required inputs
When `start.py` is executed, the wizard SHALL prompt the user sequentially for all required inputs: source font path (支援 .ttf, .otf, .ttc, .woff2), output font path, name-header file path, and font version number.

#### Scenario: User provides all required inputs
- **WHEN** the user runs `python start.py` and enters valid values for all required prompts (包括 .woff2 作為來源)
- **THEN** `build_font()` is called with the provided values and font generation completes successfully

### Requirement: 支援多種格式輸出選項
在 `start.py` 互動精靈中，SHALL 增加一個步驟詢問使用者是否需要同時輸出 WOFF2 格式。

#### Scenario: 使用者選擇同時輸出 WOFF2
- **WHEN** 執行到格式選擇步驟，使用者選擇「同時輸出 TTF 與 WOFF2」
- **THEN** 字型生成完成後，輸出目錄會同時出現 `.ttf` 與 `.woff2` 檔案

### Requirement: Wizard offers punctuation conversion choice
The wizard SHALL present a numbered menu for the punctuation conversion option before any other prompts.

#### Scenario: User selects option 1 (include punctuation conversion)
- **WHEN** the user enters `1` at the conversion mode prompt
- **THEN** `build_font()` is called with `no_punc=False`

#### Scenario: User selects option 2 (exclude punctuation conversion)
- **WHEN** the user enters `2` at the conversion mode prompt
- **THEN** `build_font()` is called with `no_punc=True`

### Requirement: Wizard re-prompts on invalid or missing required input
For required fields, the wizard SHALL re-prompt when the user provides empty input or an invalid value. It SHALL NOT crash or exit.

#### Scenario: User provides an empty path for required field
- **WHEN** the user presses Enter without typing a path for a required field
- **THEN** the wizard SHALL display an error message and repeat the same prompt

#### Scenario: User enters a non-existent source font path
- **WHEN** the user enters a file path that does not exist on disk for the source font
- **THEN** the wizard SHALL display an error message indicating the file was not found and re-prompt

### Requirement: Wizard accepts defaults for optional inputs
Optional inputs (TTC index, `--twp` flag) SHALL have sensible defaults. The user SHALL be able to press Enter to accept the default.

#### Scenario: User accepts default for optional field
- **WHEN** the user presses Enter on an optional prompt without typing a value
- **THEN** the wizard uses the documented default value for that field
