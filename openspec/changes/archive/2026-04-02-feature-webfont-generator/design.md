## Context

目前 WOFF2 壓縮邏輯嵌入在 `font.py` 的 `save_font` 中。為了讓 Webfont 轉換成為一個獨立可用的工具，我們需要將其封裝進 `webfont.py`，並提供專門的進入點。

## Goals / Non-Goals

**Goals:**
- 提供獨立的 WOFF2 轉換功能。
- 自動生成 `@font-face` CSS 程式碼。
- 支援使用者指定 Webfont 的 `font-family` 名稱。

**Non-Goals:**
- 不在此模組中進行 OpenCC 轉換或 90 度旋轉（這些應由其他模組完成）。
- 不支援 WOFF1 或 SVG 字型格式。

## Decisions

### 1. 核心轉換邏輯
- **工具**：使用 `fontTools.ttLib.TTFont`。
- **實作**：將來源字型載入後，設定 `flavor='woff2'` 並儲存。

### 2. CSS 產生器
- **內容**：包含一個標準的 `fonts.css` 文件。
- **變數**：自動根據輸出檔名填入 `url()`，根據使用者輸入填入 `font-family`。

### 3. 互動介面
- **工具**：`startWEBFONT.py`。
- **流程**：輸入來源路徑 -> 確認 CSS 名稱 -> 確認輸出路徑 -> 執行轉換並寫入檔案。

## Risks / Trade-offs

- **檔案路徑**：生成的 CSS 檔案路徑需與 WOFF2 檔案保持相對一致，否則 `url()` 會失效。
