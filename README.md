# OpenCC 字型生成器 / OpenCC Font Generator
<p align="center">
  <img width="48%" src="image.png" alt="OpenCC Font Preview">
  <img width="48%" src="image-1.png" alt="OpenCC Font Preview 2">
</p>

---

## 關於本專案 / About This Fork

本專案是基於 [ayaka14732/OpenCCFontGenerator](https://github.com/ayaka14732/OpenCCFontGenerator) 的分支版本，由 [tbdavid2019](https://github.com/tbdavid2019) 維護。

感谢原作者 **ayaka14732** 的出色工作，奠定了本工具的核心基礎。本分支在原版基礎上新增了以下功能：
- **WOFF2 支援**：支援 `.woff2` 作為輸入字型，並可選擇同時輸出 WOFF2 格式。
- **多樣化轉換標準**：支援 `s2hk` (香港)、`s2tw` (台灣) 與 `t2s` (繁轉簡) 等 OpenCC 標準。

- **字型補全 (Glyph Fallback)**：自動從備用字型提取並注入缺失的字形，徹底解決缺字 (豆腐塊) 問題。
- **`--no-punc`**：可選擇性地排除標點符號的轉換。
- **`--force-vertical`**：自動替換標點符號為直排形式（適合電子書直排字型）。
- **`start.py`**：互動式精靈啟動器，提供引導式問答介面。

---

將 OpenCC 簡繁轉換邏輯嵌入 OpenType 字型，使用者下載並安裝字型後，所有文字將自動以目標字形呈現，無需任何軟體設定。

> Embed OpenCC conversion rules into an OpenType font. Once installed, any application that renders with the font will automatically display target glyphs (Traditional or Simplified) — no software configuration required.

---

## 運作原理 / How It Works

本工具在字型的 **GSUB（字形替換）表**中建立 `liga_opencc` 功能，利用 OpenCC 字典將字形映射到對應的目標字形，包含詞彙層面的多對一替換（例如「软件」→「軟體」）。

當開啟「字型補全」功能時，程式會檢查來源字型是否缺少目標字元，並自動從備用字型中抓取所需的字形數據注入到輸出字型中。

---

## 安裝前置需求 / Prerequisites

```bash
pip install -r requirements.txt
python setup.py build  # 下載 OpenCC 資料並生成快取 (包含新標準)
```

同時需要安裝 [otfcc](https://github.com/caryll/otfcc)（`otfccdump` 與 `otfccbuild`）。

---

## 使用方法 / Usage

### 方法一：全自動快速啟動（推薦：免環境設定 & 同步友善）
如果您在 macOS 並希望自動管理環境，請直接執行：

```bash
sh run.sh
```
此腳本會自動建立虛擬環境、建置快取並啟動精靈。

---

### 方法二：手動執行互動式精靈 / Interactive Wizard
如果您已自行設定好環境，請執行：

```bash
python start.py
```

執行後會逐步詢問：
1. 轉換模式（包含 / 排除標點符號轉換）
2. 來源字型路徑（支援 .ttf / .otf / .ttc / .woff2）
3. 輸出字型路徑
4. 新字型名稱
5. 字型版本號碼
6. TTC 索引（僅針對 .ttc 檔案詢問）
7. **OpenCC 轉換標準** (s2t / twp / s2tw / s2hk / t2s)
8. **備用字型路徑** (用於缺字補全)
9. 是否開啟強制直排模式
10. **是否同時輸出 WOFF2 格式**

---

### 方法三：命令列參數 / CLI Arguments

```bash
python -m OpenCCFontGenerator \
  -i <來源字型> \
  -o <輸出字型> \
  [--woff2] \
  [--config <s2t|twp|s2tw|s2hk|t2s>] \
  [--fallback-font <備用字型路徑>] \
  [--font-name <新字型名稱>] \
  [--font-version <版本號碼>] \
  [--no-punc] \
  [--force-vertical]
```

#### 參數說明 / Parameters

| 參數 | 說明 | 必填 |
|------|------|------|
| `-i`, `--input-file` | 來源字型路徑（.ttf / .otf / .ttc / .woff2） | ✅ |
| `-o`, `--output-file` | 輸出字型路徑 | ✅ |
| `--woff2` | 是否額外輸出 WOFF2 格式 | ❌ |
| `--config` | OpenCC 配置（預設: `s2t`） | ❌ |
| `--fallback-font` | 備用字型路徑（用於補齊缺字） | ❌ |
| `--font-name` | 新字型的名稱 | ❌ |
| `--font-version` | 覆寫字型版本號碼 | ❌ |
| `--twp` | 快捷鍵：啟用台灣慣用語轉換 (等同 `--config twp`) | ❌ |
| `--no-punc` | 排除標點符號的轉換 | ❌ |
| `--force-vertical` | 強制直排模式 | ❌ |

---

## 重大功能說明：字型補全 `--fallback-font`

當您將一個原本只有簡體字的字型轉換為繁體時，如果該字型檔案中根本沒有繁體字形，轉換後的文字會變成「豆腐塊」。

現在，您可以指定一個「備用字型」（例如：思源黑體繁體版），工具會自動從中提取缺失的繁體字形並合併到您的輸出字型中。

```bash
python -m OpenCCFontGenerator \
  -i MySimplifiedFont.ttf \
  -o MyNewTraditionalFont.ttf \
  --fallback-font SourceHanSansTC-Regular.otf
```

---

## 選項說明：強制直排模式 `--force-vertical`

當開啟此模式時，工具會自動尋找字型內部的 `vert` 或 `vrt2` 排版功能，並將標點符號的映射直接指向直排版字形。適合不支援 OpenType 特性的電子書閱讀器。

---

## 授權 / License

GPL — 任何衍生作品或採用本程式碼的專案，均須以相同授權條款開放原始碼。
