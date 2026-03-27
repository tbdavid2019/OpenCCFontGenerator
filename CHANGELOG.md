# CHANGELOG

All notable changes to OpenCC Font Generator will be documented here.

---

## [Unreleased]

### Added

#### `--no-punc` — 排除標點符號轉換
- 新增 `--no-punc` CLI 參數（`BooleanOptionalAction`，預設 `False`）。
- 啟用後，`build_font()` 會在建立 GSUB 替換表前，自動過濾掉所有非漢字（以 `build_codepoints_non_han()` 定義的 Unicode 範圍）的轉換項目。
- 漢字轉換行為完全不受影響，完全向後相容。
- **Files changed**: `src/OpenCCFontGenerator/font.py`, `src/OpenCCFontGenerator/__main__.py`

#### `start.py` — 互動式精靈啟動器
- 新增專案根目錄的 `start.py`，提供引導式問答介面。
- 精靈依序詢問：轉換模式（含/排除標點）、來源字型路徑、輸出路徑、名稱標頭 JSON、版本號碼、TTC 索引（選用）、台灣慣用語轉換（選用）。
- 所有必填欄位具備輸入驗證與重新提示功能；路徑欄位會檢查檔案是否存在。
- 顯示設定摘要後再詢問確認，才開始生成。
- 僅使用 Python 標準函式庫（`input()`），無額外相依套件。
- **Files changed**: `start.py` (new)

#### `--force-vertical` — 強制直排模式
- 新增 `--force-vertical` CLI 參數。
- 運作原理：自動從 `GSUB` 表搜尋 `vert` 與 `vrt2` 特性，並將其對應的直排字形強制寫入 `cmap` 映射中。
- 改善 `remove_glyph()`：自動清理 `vmtx`、`VORG`、`hmtx` 與 `vhea` 表中對應的字形數據，確保直排字型結構完整。
- **Files changed**: `src/OpenCCFontGenerator/font.py`, `src/OpenCCFontGenerator/__main__.py`, `start.py`
