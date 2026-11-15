# OpenCCFontGenerator Web 化可行性評估

- 評估日期：2026-07-23
- 評估範圍：目前 repository 的核心轉換流程、CLI 邊界、瀏覽器執行限制、部署風險與上游維護狀態
- 建議結論：先建置「Web 前端 + Python 容器後端」。純瀏覽器 WebAssembly 版列為後續研發項目。

## 結論

OpenCCFontGenerator 可以提供網頁介面。現有核心已集中在 `build_font(...)`，CLI 與互動式精靈主要負責收集參數，因此 Web API 可以直接重用大部分字型轉換邏輯。

第一版建議採用下列架構：

```text
瀏覽器
  │ 上傳來源字型、fallback 字型與轉換設定
  ▼
Web API
  │ 建立隔離工作目錄與轉換任務
  ▼
Python Worker／Container
  ├─ build_font(...)
  ├─ otfccdump
  ├─ OpenCC／cmap／GSUB 處理
  ├─ otfccbuild
  └─ fontTools／WOFF2
  │
  ▼
下載輸出字型 → 到期或下載完成後刪除暫存檔
```

此方案能保留目前 Python 與 `otfcc` 工具鏈。部署環境需要能執行原生二進位檔及限制 CPU、記憶體和執行時間，因此應使用 container、VM 或可執行 container job 的平台。純靜態網站與一般 edge function 不適合直接承載目前的核心流程。

## 現有專案概況

### 核心流程

主要入口位於：

- `src/OpenCCFontGenerator/__main__.py`：命令列參數入口
- `start.py`：互動式 CLI 精靈
- `src/OpenCCFontGenerator/font.py`：核心字型讀取、轉換、補字、metadata 與輸出
- `src/OpenCCFontGenerator/run90.py`：字形旋轉
- `src/OpenCCFontGenerator/vf_family.py`：Variable Font family 建置
- `src/OpenCCFontGenerator/static_family.py`：Static Font family 批次建置
- `src/OpenCCFontGenerator/webfont.py`：WOFF2 與 CSS 產生器

`src/OpenCCFontGenerator/font.py` 的 `build_font(...)` 已形成可重用的應用層入口。`__main__.py`、`start.py`、static family 與 variable family 模組都呼叫這個函式。Web API 不需要透過 shell 拼接 CLI 字串，可以直接在 Python 程序內呼叫函式。

### 支援功能

目前核心 Web 表單需要涵蓋的參數包括：

- 來源字型：TTF、OTF、TTC、WOFF2
- TTC index
- 轉換標準：`s2t`、`twp`、`s2tw`、`s2hk`、`t2s`
- fallback 字型
- merge mode：`opencc`、`universal`
- fill charset
- 排除標點符號
- 強制直排
- 字型名稱與版本
- Kobo 相容模式
- 額外輸出 WOFF2

repository 內的 OpenCC cache 與資料約 4.9 MB。單一 `twp` 詞彙表約 49,461 條規則；產生詞彙 GSUB 時，每條可用詞彙會建立 pseudo glyph。大型 CJK 字型也可能接近 OpenType 的 65,535 glyph 上限。

### 「Webfont」功能的定義

`src/OpenCCFontGenerator/webfont.py` 的功能是將字型轉成 WOFF2 並產生 `@font-face` CSS。它不包含瀏覽器 UI、HTTP API 或瀏覽器端字型轉換引擎。

## Web 化方案比較

| 方案 | 可行性 | 現有核心重用 | 字型是否上傳伺服器 | 工程量 | 建議 |
|---|---:|---:|---:|---:|---|
| Web 前端 + Python container 後端 | 9/10 | 約 85–95% | 是 | 中 | 第一階段採用 |
| 本機 desktop／localhost Web UI | 9/10 | 約 95% | 否 | 低至中 | 適合重視隱私的使用者 |
| 純瀏覽器 Pyodide + WebAssembly | 4/10 | 約 30–60% | 否 | 高 | 先做技術驗證 |
| 以 fontTools 或其他引擎重寫核心 | 5/10 | 低 | 否或可選 | 很高 | 長期移除 otfcc 時評估 |

### Web 前端 + Python 後端

優點：

- 直接重用 `build_font(...)`。
- 可繼續使用 `otfccdump`、`otfccbuild`、fontTools 與現有 cache。
- 瀏覽器端只需處理表單、上傳、狀態與下載。
- 可以先做同步單機版，再擴充成 worker queue。

限制：

- 字型檔會送到伺服器。
- 公開服務必須隔離不可信輸入。
- 大型字型需要明確的資源限制與任務逾時。
- 伺服器必須管理暫存檔生命週期。

### 本機 Web UI

可使用 desktop wrapper、localhost service 或 packaged container，讓 UI 仍以網頁呈現，核心在使用者電腦執行。此方案能保留字型隱私並完整重用現有工具鏈，但使用者仍需下載程式或啟動本機服務。

### 純瀏覽器版

Pyodide 可在瀏覽器中執行 Python，現行套件清單也包含 `fonttools` 與 Brotli。不過 Pyodide 明確不支援啟動 `subprocess`。目前核心會呼叫：

- `otfccdump`
- `otfccbuild`
- `python -m fontTools.subset`

因此目前程式不能原封不動放進 Pyodide。相關限制見 [Pyodide FAQ](https://pyodide.org/en/stable/usage/faq.html)；長時間運算也應放進 [Web Worker](https://pyodide.org/en/stable/usage/webworker.html)，避免阻塞 UI。

純瀏覽器版需要完成其中一條路徑：

1. 將 `otfcc` 編譯成 WebAssembly，封裝記憶體檔案系統、輸入輸出與錯誤回報。
2. 直接呼叫編譯後的 otfcc library API，移除 Python `subprocess` 邊界。
3. 以 fontTools 或其他可在瀏覽器執行的 OpenType 引擎重寫 otfcc JSON 讀寫流程。

第二條路徑可能受益於社群 fork 對 otfcc library API 與 CMake 的整理，但仍需要獨立驗證 CFF、TTC、GSUB、GPOS、variable font、WOFF2 與大型 CJK 字型。

## 第一版產品範圍

### 建議納入

- 單一來源字型上傳
- 可選單一 fallback 字型
- OpenCC conversion config
- `no-punc`
- `force-vertical`
- Kobo mode
- 字型名稱與版本
- TTF／OTF 輸出
- 可選 WOFF2 輸出
- 轉換狀態與具體錯誤訊息
- 轉換完成後下載
- 產生結果的瀏覽器字型預覽

### 建議延後

- 整個資料夾批次處理
- Variable Font 多字重 family 建置
- Static Font family 自動配對
- 90° 旋轉工具
- 帳號、永久檔案保存與歷史紀錄
- 純瀏覽器離線處理

此範圍可先驗證使用需求、平均檔案大小、處理時間、失敗率與伺服器成本。

## Web 化前的必要整理

### 1. 結構化執行結果

`save_font(...)` 目前會檢查 `otfccbuild` return code，但失敗時只寫入 `opencc_gen_debug.log`，沒有向呼叫者拋出錯誤。WOFF2 壓縮例外也只寫入 log。上層可能繼續顯示成功。

建議：

- `otfccbuild` 非零退出碼直接拋出例外。
- WOFF2 產生失敗回傳明確錯誤。
- `build_font(...)` 回傳結構化結果，包括輸出檔、格式、大小、警告與處理統計。
- 完成後使用 fontTools 重新開啟輸出字型，確認結果可解析。

### 2. 進度與 log 邊界

目前核心直接使用 `print(...)`，並將所有執行寫到固定的 `opencc_gen_debug.log`。

建議：

- 使用標準 logging 或注入 progress callback。
- 每個 job 使用獨立 ID、目錄與 log。
- Web API 僅回傳安全且可理解的錯誤，不洩露主機路徑。

### 3. 自動化測試

目前 repository 沒有測試檔案與測試字型。OpenSpec 中多項功能已寫入程式，但驗證 task 仍未完成；`force-vertical` 的程式與規格 task 狀態也有落差。

最低測試集應包括：

- 每種 conversion config 的 smoke test
- TTF、OTF、TTC、WOFF2 輸入
- 無 fallback、opencc fallback、universal fallback
- glyph 上限錯誤
- 損壞字型與 parser crash
- 輸出字型可被 fontTools、otfccdump 與瀏覽器重新讀取
- 重要 cmap 與 GSUB 規則的結構驗證

測試字型必須具備可再散布的授權。

### 4. 可重現部署

目前 `requirements.txt` 只有 `opencc<1.2`、`fonttools`、`brotli`，版本固定程度不足；repository 也沒有 container 設定與 CI workflow。

建議：

- 固定 Python、OpenCC、fontTools、Brotli 與 otfcc 版本。
- 建立包含 otfcc binary 的 container image。
- 在建置階段產生或驗證 cache，不在 request 處理期間下載資料。
- CI 執行測試、字型輸出驗證與 container smoke test。

## 公開服務的安全與營運要求

字型是二進位且結構複雜的外部輸入。`otfccdump` 是原生 C 程式；目前程式內甚至已有針對特定 OTF 導致 segmentation fault 的 fallback 路徑。公開服務應將 parser 視為高風險邊界。

必要措施：

- 限制來源與 fallback 檔案大小。
- 驗證副檔名、magic bytes 與基本 OpenType 結構。
- 每個 job 在非 root、唯讀基礎映像的隔離 container 中執行。
- 設定 CPU、memory、process、輸出大小與時間限制。
- 不允許使用者控制實際主機路徑或命令列。
- 限制同時執行數量並提供 rate limit。
- 暫存檔在完成、失敗及逾時後都必須清除。
- 公開說明上傳檔案保存時間與刪除政策。
- 提醒使用者確認來源字型授權允許修改。

## 授權

目前 repository 的 `LICENSE` 是 AGPL-3.0。公開部署修改後的網路服務時，應確認 AGPL 對服務使用者提供對應源碼的要求。

原始 `ayaka14732/OpenCCFontGenerator` GitHub 頁面標示 CC-BY-4.0，目前 fork 則標示 AGPL-3.0。正式公開服務前應整理第三方程式、OpenCC 資料、otfcc binary 與測試字型的授權及 attribution。此處為工程風險提示，不構成法律意見。

## otfcc 與上游維護狀態

以下狀態以 2026-07-23 查詢 GitHub 的結果為準。

### otfcc 官方上游

[caryll/otfcc](https://github.com/caryll/otfcc) 已由擁有者封存：

- repository 狀態：archived、read-only
- 最後一次 push：2022-06-03
- 最新 release：v0.10.4，發布於 2020-04-12
- 專案用途：OpenType 與 JSON 之間的解析及建置，正是本 repository 的核心 I/O 邊界

官方上游已停止維護。現有 release 仍可使用；安全修補、新平台支援與格式相容問題不會再由原 repository 正式發布。

### otfcc 社群 forks

社群仍有近期活動，但目前沒有可確認為公認官方接班者的 fork：

- [InCom-0/otfcc_cmake](https://github.com/InCom-0/otfcc_cmake)：相對官方 master 約有 40 個提交，整理 CMake、library API 與跨編譯器建置；2026-03 仍有提交。
- [MaruTama/otfcc](https://github.com/MaruTama/otfcc)：2026-07 有大型 GSUB alternate／multiple lookup 的 overflow 修正。
- [julixian/otfcc](https://github.com/julixian/otfcc)：2026 年有建置系統更新。

這些 forks 可以作為修補來源或 WebAssembly 技術研究候選。採用前需要檢查 release、CI、測試覆蓋、二進位供應鏈與相對官方版本的行為差異。單純依最後 push 日期無法判定生產成熟度。

### OpenCCFontGenerator 原始上游

[ayaka14732/OpenCCFontGenerator](https://github.com/ayaka14732/OpenCCFontGenerator) 未封存，但維護活動有限：

- 最後一次 push：2023-07-11
- repository 僅有少量提交
- 目前顯示 4 個 open issues、0 個 open pull requests

目前 `tbdavid2019/OpenCCFontGenerator` 在 GitHub API 中顯示 `fork: false`，沒有 `parent` 或 `source` 關聯；它在文件上屬於衍生版本，在 GitHub repository metadata 上則是獨立 repository。

### 維護責任判斷

目前狀況可分成三層：

| 元件 | 狀態 | 對本專案的影響 |
|---|---|---|
| `tbdavid2019/OpenCCFontGenerator` | 由目前 repository 自行維護 | 現有功能與 release 由本 repository 負責 |
| `ayaka14732/OpenCCFontGenerator` | 未封存，但自 2023 年後無新提交 | 不宜期待近期合併本 fork 的功能或提供修補 |
| `caryll/otfcc` | 已封存 | 核心 parser／builder 的正式上游停止更新 |

因此，本 repository 的應用層實際上已由目前維護者接手。otfcc 的官方上游停止維護，但社群 fork 仍有活動。現況屬於「缺少穩定官方上游」，不等同於「所有相關程式都無人維護」。

## 建議執行順序

1. 修正錯誤回傳、job 隔離、logging 與輸出驗證。
2. 建立具合法授權的最小測試字型與回歸測試。
3. 建立固定版本的 container image，包含 Python dependencies 與目前使用的 otfcc v0.10.4。
4. 實作單檔轉換 Web API 與簡單前端。
5. 收集真實字型的時間、峰值記憶體、JSON 大小與失敗資料。
6. 評估採用社群 otfcc fork，或自行維護最小安全 patch set。
7. 另外進行 otfcc WebAssembly spike；達到 TTF／OTF round-trip 與 GSUB 測試後，再決定是否推進純瀏覽器版。

## 時程級距

以下估算需在取得可重現的 end-to-end 測試與效能數據後調整：

- 內部單使用者 MVP：約 3–7 個工作天。
- 公開 beta，包含隔離、限流、清理、queue 與測試：約 2–4 週。
- 純瀏覽器 WebAssembly：獨立研發項目，先安排技術驗證，不納入第一版承諾。

## 最終建議

立即推進 container-based Web 版本。它能保留目前最有價值的轉換演算法，也能快速提供不需操作 CLI 的使用體驗。

同步建立 otfcc 風險處理策略：短期固定並隔離 v0.10.4；中期評估社群 fork 與維護 patch；長期再決定編譯 WebAssembly 或移除 otfcc 依賴。
