## Why

為了讓字型工具組更具模組化，我們需要將 Webfont (WOFF2) 的轉換功能從核心轉換流程中獨立出來。這樣使用者可以針對已有的繁體字型進行格式優化，並自動獲得可用於網頁開發的 CSS 範例。

## What Changes

- **獨立格式轉換器**：新增 `runWEBFONT.sh`, `startWEBFONT.py` 與 `src/OpenCCFontGenerator/webfont.py`。
- **自動化 CSS 產出**：轉換過程中自動生成 `fonts.css` 範例，內含 `@font-face` 設定。
- **文件更新**：更新 `README.md` 加入 Webfont 最佳實踐，並在 `CHANGELOG.md` 紀錄此功能。

## Capabilities

### New Capabilities
- `webfont-conversion-module`: 獨立的 TTF/OTF 轉 WOFF2 轉換引擎。
- `css-template-generator`: 自動產生符合 Web 實踐的 `@font-face` CSS 片段。

### Modified Capabilities
<!-- 無 -->

## Impact

- 檔案結構：新增 `runWEBFONT.sh`, `startWEBFONT.py`, `src/OpenCCFontGenerator/webfont.py`。
- 專案相依性：維持對 `fonttools` 與 `brotli` 的依賴。
