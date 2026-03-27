# OpenCC 字型生成器 / OpenCC Font Generator

---

## 關於本專案 / About This Fork

本專案是基於 [ayaka14732/OpenCCFontGenerator](https://github.com/ayaka14732/OpenCCFontGenerator) 的分支版本，由 [tbdavid2019](https://github.com/tbdavid2019) 維護。

感謝原作者 **ayaka14732** 的出色工作，奠定了本工具的核心基礎。本分支在原版基礎上新增了以下功能：
- `--no-punc`：可選擇性地排除標點符號的轉換
- `start.py`：互動式精靈啟動器，提供引導式問答介面，降低使用門檻

---

將 OpenCC 簡繁轉換邏輯嵌入 OpenType 字型，使用者下載並安裝字型後，所有簡體中文文字將自動以繁體字形呈現，無需任何軟體設定。

> Embed OpenCC Simplified→Traditional Chinese conversion rules into an OpenType font. Once installed, any application that renders with the font will automatically display Traditional Chinese glyphs — no software configuration required.

---

## 運作原理 / How It Works

本工具在字型的 **GSUB（字形替換）表**中建立 `liga_s2t` 功能，利用 OpenCC 字典將簡體字形映射到對應的繁體字形，包含詞彙層面的多對一替換（例如「软件」→「軟體」）。

> This tool builds a `liga_s2t` GSUB feature in the font, mapping Simplified Chinese glyphs to Traditional Chinese using OpenCC dictionaries — including phrase-level ligature substitutions (e.g. 软件 → 軟體).

---

## 安裝前置需求 / Prerequisites

```bash
pip install -r requirements.txt
python setup.py build  # 下載 OpenCC 資料並生成快取
```

同時需要安裝 [otfcc](https://github.com/caryll/otfcc)（`otfccdump` 與 `otfccbuild`）。

> Also requires [otfcc](https://github.com/caryll/otfcc) (`otfccdump` and `otfccbuild`) on your PATH.

---

## 使用方法 / Usage

### 方法一：互動式精靈（推薦新手）/ Interactive Wizard (Recommended)

```bash
python start.py
```

執行後會逐步詢問：
1. 轉換模式（包含 / 排除標點符號轉換）
2. 來源字型路徑
3. 輸出字型路徑
4. 名稱標頭設定檔（JSON）
5. 版本號碼
6. TTC 索引（選用）
7. 是否包含台灣慣用語轉換

---

### 方法二：命令列參數 / CLI Arguments

```bash
python -m OpenCCFontGenerator \
  -i <來源字型> \
  -o <輸出字型> \
  -n <名稱標頭 JSON> \
  --font-version <版本號碼> \
  [--ttc-index <索引>] \
  [--twp] \
  [--no-punc]
```

#### 參數說明 / Parameters

| 參數 | 說明 | 必填 |
|------|------|------|
| `-i`, `--input-file` | 來源字型路徑（.ttf / .otf / .ttc） | ✅ |
| `-o`, `--output-file` | 輸出字型路徑 | ✅ |
| `-n`, `--name-header-file` | 名稱標頭 JSON 設定檔路徑 | ✅ |
| `--font-version` | 字型版本號碼（例如: `1.0`） | ✅ |
| `--ttc-index` | TTC 檔案的字型索引（選用） | ❌ |
| `--twp` | 啟用台灣慣用語轉換（例如「軟件」→「軟體」） | ❌ |
| `--no-punc` | 排除標點符號的轉換，僅轉換漢字 | ❌ |
| `--no-twp` | 停用台灣慣用語（與 `--twp` 相反） | ❌ |

#### 範例 / Example

```bash
# 基本轉換
python -m OpenCCFontGenerator \
  -i SourceHanSansSC-Regular.otf \
  -o SourceHanSansSC-TC-Regular.otf \
  -n name_header.json \
  --font-version 1.0

# 包含台灣慣用語，排除標點符號轉換
python -m OpenCCFontGenerator \
  -i SourceHanSansSC-Regular.otf \
  -o SourceHanSansSC-TC-Regular.otf \
  -n name_header.json \
  --font-version 1.0 \
  --twp \
  --no-punc
```

---

## 選項說明：排除標點符號 `--no-punc`

預設情況下，生成的字型會同時轉換漢字與標點符號（如 `" "` → `「 」`）。  
若不希望標點符號被改變，加上 `--no-punc` 即可：

```bash
python -m OpenCCFontGenerator ... --no-punc
```

或在互動式精靈中選擇「**2. 排除標點符號轉換**」。

---

## 授權 / License

GPL — 任何衍生作品或採用本程式碼的專案，均須以相同授權條款開放原始碼。
