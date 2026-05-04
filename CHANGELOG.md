# CHANGELOG

All notable changes to OpenCC Font Generator will be documented here.

---

## [Unreleased]

### Added

#### Variable CJK Family Builder — variable 拉丁字型多權重合成流程
- 新增 `runVF.sh` 與 `startVF.py` 互動精靈，支援將 variable 拉丁字型展開成多個 static 權重 instance，並與對應的 CJK fallback 字型逐一合成。
- 新增 `src/OpenCCFontGenerator/vf_family.py`，內含 variable font `wght` 軸展開、fallback 權重配對與批次輸出整套 family 的核心流程。
- 適用場景：像 `MonoLisaVariable*.ttf` 這類只有英數的 variable 字型，可搭配 `NotoSansTC-*.ttf` 建立一整套可安裝的 CJK family。
- **Files changed**: `runVF.sh`, `startVF.py`, `src/OpenCCFontGenerator/vf_family.py`, `README.md`

#### Static Font Family Builder — 非 variable 靜態字型批次流程
- 新增 `runSTATIC.sh` 與 `startSTATIC.py` 互動精靈，支援將單一靜態字型或整個靜態字重 family 批次處理。
- 新增 `src/OpenCCFontGenerator/static_family.py`，可依檔名自動辨識 `Regular / Medium / Bold` 等字重，並自動配對對應的 fallback 字型。
- 適用場景：來源字型不是 variable font，但仍想把一整組 `Regular/Bold/Light...` 靜態字型一次轉成 `_TC` family。
- **Files changed**: `runSTATIC.sh`, `startSTATIC.py`, `src/OpenCCFontGenerator/static_family.py`, `README.md`

#### `--merge-mode universal` — 通用型 merge font 模式
- 新增 `--merge-mode {opencc,universal}` CLI 參數，讓 fallback 字型不再只補 OpenCC 轉換目標字，而是可選擇保留來源字庫並合併 fallback 中所有缺少的 codepoint。
- 更新互動式精靈 `start.py`，加入 fallback 補字模式選單。
- **Files changed**: `src/OpenCCFontGenerator/font.py`, `src/OpenCCFontGenerator/__main__.py`, `start.py`, `README.md`

#### `--fill-charset` — 先補字集再轉換
- 新增 `--fill-charset` 參數，支援在 OpenCC 流程前先主動從 fallback 字型補指定字集。
- 目前內建 `hant-common / opencc-hant / han`，會使用專案內建的 Han codepoint cache 先補常用繁中字區。
- `runVF.sh` 現在預設會先補 `hant-common`；`runSTATIC.sh` 與 `start.py` 也新增對應選項。
- **Files changed**: `src/OpenCCFontGenerator/font.py`, `src/OpenCCFontGenerator/__main__.py`, `start.py`, `startSTATIC.py`, `src/OpenCCFontGenerator/static_family.py`, `src/OpenCCFontGenerator/vf_family.py`, `README.md`

#### Font Metadata Improvements — 繁中名稱與文件科普補強
- 輸出字型現在會自動補上 `zh-TW` (`languageID=1028`) 的本地化名稱記錄，提高 macOS 與中文環境中被辨識為繁中字型的機率。
- README 新增字型術語教學、直式 Mermaid 渲染流程圖，以及 Variable CJK Family 流程說明。
- **Files changed**: `src/OpenCCFontGenerator/font.py`, `README.md`

### Changed

#### Documentation for subset-font behavior
- 補充 README 與互動式精靈說明，明確標示 `_TC` 輸出為針對 OpenCC 詞彙級轉換優化的 subset font，而非完整保留原始字庫的副本。
- 補充 OpenType `65535` glyph 上限與 pseudo glyph 取捨背景，避免使用者誤判輸出檔體積與字庫覆蓋範圍。
- **Files changed**: `README.md`, `start.py`

### Fixed

#### Fallback merge reliability for composite glyphs and cleanup
- 修正 fallback 補字時只複製最外層 glyph、沒有遞迴帶入 composite/reference 依賴的問題。
- 修正補進來的 fallback codepoint 在 subset 清理時可能又被移除的問題。
- `clean_unused_glyphs()` 現在也會將 glyph references 納入可達性分析，避免元件字形被誤刪。
- **Files changed**: `src/OpenCCFontGenerator/font.py`

#### Kindle GSUB compatibility for OpenCC substitution
- 修正 OpenCC 替換規則原本掛在自訂 feature tag（如 `liga_s2t`）上的相容性問題。
- 現在同一組 GSUB lookup 會同時掛到標準 OpenType feature：`liga`、`rlig`、`ccmp`，提高 Kindle 與其他受限閱讀器啟用替換規則的機率。
- **Files changed**: `src/OpenCCFontGenerator/font.py`, `README.md`

#### Taiwan Phrases (twp) "面" character conversion
- 修正 `twp` (台灣用語) 模式中，單字「面」(face/surface) 被錯誤轉換為「麵」(noodles) 的問題。
- 現在單字「面」會正確保留為「面」，而「麵條」、「拉麵」等詞彙仍會透過詞彙表正確轉換為「麵」。
- **Files changed**: `src/OpenCCFontGenerator/cache/convert_table_chars_twp.txt`

#### Glyph cleanup compatibility for fallback merge
- 修正部分來源字型缺少 `GSUB` 或 `GPOS` 表時，啟用 `--fallback-font` 後在清理未使用字形階段觸發 `KeyError('GSUB')` 而失敗的問題。
- `remove_glyph()` 與 `clean_unused_glyphs()` 現在會在 OpenType 版面表不存在時安全略過相關 lookup 清理。
- **Files changed**: `src/OpenCCFontGenerator/font.py`

### Added

#### Webfont Generator — 獨立網頁字型工具
- 新增 `runWEBFONT.sh` 與 `startWEBFONT.py` 互動精靈，支援將 TTF/OTF 獨立轉換為 WOFF2。
- **自動化 CSS**: 轉換完成後自動產出 `fonts.css` 範例，內含 `@font-face` 設定。
- **Files changed**: `runWEBFONT.sh`, `startWEBFONT.py`, `src/OpenCCFontGenerator/webfont.py`

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
