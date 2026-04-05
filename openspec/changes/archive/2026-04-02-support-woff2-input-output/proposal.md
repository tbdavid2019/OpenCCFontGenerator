## Why

目前專案的核心工具 `otfcc` 不支援 WOFF2 格式。隨著網頁字型應用的普及，使用者經常需要處理 `.woff2` 格式的輸入，並希望在生成繁體字型時能同時獲得 `.ttf` 與 `.woff2` 格式，以節省手動轉換的時間。

## What Changes

- **輸入支援**：支援 `.woff2` 作為來源字型（自動解壓為臨時 `.ttf`）。
- **輸出選項**：在 `start.py` 互動精靈與 CLI 中增加選項，支援同時輸出 `.ttf` 與 `.woff2`。
- **依賴更新**：引入 `fonttools` 與 `brotli` 作為處理 WOFF2 的必要依賴。

## Capabilities

### New Capabilities
- `woff2-format-support`: 提供 WOFF2 格式的解壓（輸入）與壓縮（輸出）功能。
- `multi-format-output`: 允許使用者選擇同時生成多種格式的字型檔案。

### Modified Capabilities
- `interactive-wizard`: 更新互動流程以包含格式選擇。

## Impact

- `requirements.txt`: 新增 `fonttools` 與 `brotli`。
- `src/OpenCCFontGenerator/font.py`: 修改 `load_font` 與 `save_font` 邏輯。
- `start.py`: 更新互動問答流程。
- `src/OpenCCFontGenerator/__main__.py`: 新增 CLI 參數。
