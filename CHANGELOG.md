# CHANGELOG

All notable changes to OpenCC Font Generator will be documented here.

---

## [Unreleased]

### Added

#### Pseudo-Vertical Rotation (90° Rotation) — 偽直排旋轉支援
- 新增 `run90.sh` 與 `start90.py` 互動精靈，支援將字元順時針旋轉 90 度以解決舊型設備不支援直排的問題。
- **幾何中心旋轉**: 透過 `run90.py` 對 `glyf` 座標進行精確變換。
- **智慧識別**: 提供「僅旋轉漢字」選項，避免英數混排時英文字母跟著躺平。
- **度量衡調整**: 自動修正 `advanceWidth` 與全域度量，確保排版一致。
- **Files changed**: `run90.sh`, `start90.py`, `src/OpenCCFontGenerator/run90.py`

#### WOFF2 Input & Output Support — 網頁字型支援
- 新增對 `.woff2` 作為來源字型的支援。系統會自動解壓 WOFF2 並轉為臨時 TTF 供 `otfcc` 處理。
- 新增 `--woff2` 選項與互動精靈對話（Step 10），支援在輸出 TTF 時同時生成壓縮後的 `.woff2` 格式。
- 新增 `fonttools` 與 `brotli` 作為處理 WOFF2 的必要依賴。
- **Files changed**: `requirements.txt`, `src/OpenCCFontGenerator/font.py`, `src/OpenCCFontGenerator/__main__.py`, `start.py`

#### `s2hk`, `s2tw`, `t2s` — 多樣化 OpenCC 轉換標準
- 新增對 `s2hk` (簡體轉香港繁體)、`s2tw` (簡體轉台灣正體) 與 `t2s` (繁體轉簡體) 的支援。
- 更新 `setup.py`：自動從 OpenCC 數據源下載並生成對應標準的快取映射表（`convert_table_chars_*.txt`）。
- 更新 `font.py`：轉換邏輯重構，支援透過 `--config` 參數動態載入不同的 OpenCC 配置。
- **Files changed**: `setup.py`, `src/OpenCCFontGenerator/font.py`, `src/OpenCCFontGenerator/__main__.py`, `start.py`

#### `--fallback-font` — 字型補全功能 (Glyph Fallback)
- 新增 `--fallback-font` CLI 參數。
- 運作原理：在字型生成過程中，系統會自動比對主要字型是否缺少轉換後的目標字元。若有缺字且使用者提供了「備用字型」，系統會自動利用 `otfcc` 將所需的字形數據（含 `glyf`、`hmtx` 等度量資訊）注入到目標字型中。
- 解決問題：徹底解決簡體字型轉換成繁體字型後，因原字型不含繁體字形而出現「豆腐塊」的缺字現象。
- **Files changed**: `src/OpenCCFontGenerator/font.py`, `src/OpenCCFontGenerator/__main__.py`, `start.py`

#### `start.py` 與 CLI 介面優化
- 更新互動式精靈 `start.py`：引導使用者選擇轉換標準 (s2t, twp, s2hk, s2tw, t2s) 與設定備用字型路徑。
- 優化 CLI 參數：加入 `--config` 與 `--fallback-font` 參數，並保留對舊有 `--twp` 參數的相容性。
- **Files changed**: `start.py`, `src/OpenCCFontGenerator/__main__.py`

---

## [Older Changes]

### Added

#### `--no-punc` — 排除標點符號轉換
- 新增 `--no-punc` CLI 參數（`BooleanOptionalAction`，預設 `False`）。
- 啟用後，`build_font()` 會在建立 GSUB 替換表前，自動過濾掉所有非漢字（以 `build_codepoints_non_han()` 定義的 Unicode 範圍）的轉換項目。
- 漢字轉換行為完全不受影響，完全向後相容。
- **Files changed**: `src/OpenCCFontGenerator/font.py`, `src/OpenCCFontGenerator/__main__.py`

#### `start.py` — 互動式精靈啟動器 (Initial Version)
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
