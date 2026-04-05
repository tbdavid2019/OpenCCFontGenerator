## ADDED Requirements

### Requirement: 獨立轉換 WOFF2
系統 MUST 提供一個獨立於主轉換流程的功能，將 TTF 或 OTF 字型轉換為 WOFF2 格式。

#### Scenario: 成功轉換 Webfont
- **WHEN** 使用者輸入一個 `.ttf` 字型檔案並啟動 Webfont 轉換
- **THEN** 系統 SHALL 調用 `fontTools` 並生成一個對應的 `.woff2` 檔案

### Requirement: 自動生成 CSS 範例
在 Webfont 轉換完成後，系統 MUST 自動生成一個包含 `@font-face` 的 CSS 檔案。

#### Scenario: 產出 CSS 片段
- **WHEN** 轉換完成
- **THEN** 系統 SHALL 在輸出目錄建立 `fonts.css`，其內容包含正確的 `font-family` 與指向 `.woff2` 的 `url()`
