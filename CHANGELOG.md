# CHANGELOG

All notable changes to OpenCC Font Generator will be documented here.

---

## [2026-11-20]

### Added

#### 新增 GitHub Actions CI/CD 與 GHCR + Watchtower 自動部署管線
- **新增自動化測試與多架構映像發布管線（[.github/workflows/ci-cd.yml](.github/workflows/ci-cd.yml)）**：
  - 於 `main` 分支每次 `push` / `pull_request` 自動執行 Shell/JS/YAML/Python 語法檢查、編譯快取 `otfcc v0.10.4`、OpenCC 1.4.2 詞庫不變量驗證與完整 38 項單元／Web API 測試。
  - `main` 測試全數通過後，自動建置並推送 `linux/amd64` + `linux/arm64` 雙架構映像至 `ghcr.io/tbdavid2019/openccfontgenerator:latest` 與 `sha-<commit>` 標籤。
- **整合 GHCR 映像與 Scoped Watchtower 自動更新**：
  - 更新 [docker-compose.yml](docker-compose.yml) 加入 `image`、`com.centurylinklabs.watchtower.scope=opencc-font` 標籤與 `profiles: ["watchtower"]` 的 `nickfedor/watchtower:latest` 服務，免除遠端低記憶體主機本機編譯負擔並支援 push 後自動滾動更新；同步補充 [README.md](README.md) 部署說明。

#### 888 字體檔加工台品牌命名與完整 SEO / Open Graph / PWA 圖示支援
- **補齊 `https://font.david888.com` 搜尋引擎與社群分享中繼資料（Meta / OG / Twitter / JSON-LD）**：
  - 將站台標題與品牌名稱更新為「**888 字體檔加工台**」，並於 [index.html](src/OpenCCFontGenerator/web/static/index.html) 補齊 `<meta name="description">`、`canonical`、完整 Open Graph（`og:type`、`og:site_name`、`og:locale`、`og:url`、`og:title`、`og:description`、`og:image` `1200×630`）、Twitter Card（`summary_large_image`）與 `WebApplication` Schema.org JSON-LD 結構化資料。
  - 新增品牌專屬 [og-image.png](src/OpenCCFontGenerator/web/static/og-image.png)（`1200×630`）、多解析度 [favicon.ico](src/OpenCCFontGenerator/web/static/favicon.ico)（`16/32/48`）、PNG 圖示組（`16×16`、`32×32`、`180×180 apple-touch-icon.png`、`192×192`、`512×512`）、[site.webmanifest](src/OpenCCFontGenerator/web/static/site.webmanifest) 與 [robots.txt](src/OpenCCFontGenerator/web/static/robots.txt)。
  - 更新 [app.py](src/OpenCCFontGenerator/web/app.py) 提供上述根目錄靜態資產路由與快取標頭（HTML `/` 採 `Cache-Control: no-cache` 以保留 bfcache；圖示與 Manifest 採 `public, max-age=86400`），並於 [test_web_api.py](tests/test_web_api.py) 驗證全數中繼標籤與資源回應。

### Changed

#### 套用 `david888.com` WCAG 2.1 AA/AAA 配色與品牌 Footer
- **全面切換 `david888.com` 品牌色系並強化 WCAG 對比度與輔助使用支援**：
  - 更新 [styles.css](src/OpenCCFontGenerator/web/static/styles.css)、[favicon.svg](src/OpenCCFontGenerator/web/static/favicon.svg) 與 [DESIGN.md](DESIGN.md)：採用深海藍（`#17324D`）、番紅花金（`#FFB010`）、暖奶油紙底（`#FFFEFA` / `#FFF9E8` / `#FFF2D1`）與陶土橘紅（`#9A3F18`），全部文字與表面組合對比度皆達 WCAG AA（>= 4.5:1）至 AAA（7:1+），元件邊框與焦點外框達 WCAG 1.4.11（>= 3:1），並補齊 `::placeholder`、`caret-color`、雙色系 `:focus-visible`（導覽列 `#FFB010` / 內容區 `#17324D`）與 `@media (forced-colors: active)` 系統高對比回退。
- **新增 `david888.com 技術提供` 品牌 Footer 與行動版主題色**：
  - 更新 [index.html](src/OpenCCFontGenerator/web/static/index.html) 加入 `<meta name="theme-color" content="#FFB010">` 與語意化 `<footer class="site-footer">`（含 `david888.com 技術提供` 連結、OpenCC 1.4.2 服務說明、`/docs`、`ReDoc` 與 GitHub 連結，並統一左側欄 `/docs` 連結無障礙名稱為 `OpenAPI /docs`），並於 [test_web_api.py](tests/test_web_api.py) 補齊品牌色與 Footer 回歸斷言。

### Fixed

#### 部署前全盤檢查與 Web / CLI 強健性修復
- **納管異體字回退詞庫至 Git 與 Docker 建置環境**：
  - 調整 [.gitignore](.gitignore) 與 [.dockerignore](.dockerignore)，僅忽略上游下載的字典檔而明確保留 `src/OpenCCFontGenerator/opencc_data/Variants.txt`、`Var_tw.txt`、`Var_hk.txt`、`Var_cl.txt`，確保 Docker 映像與遠端部署能正常執行 `apply_variants()` 異體字補字。
- **修復 `static_family` 中文檔名遺失、非 TTF/OTF 副檔名輸出錯誤與撞名覆蓋**：
  - 更新 [static_family.py](src/OpenCCFontGenerator/static_family.py) 的 `sanitize_filename_part()` 保留中文漢字，新增 `_resolve_output_extension()` 將 `.woff2`/`.ttc` 來源正規化為 `.ttf` 輸出，並於 `build_static_cjk_family()` 去重檔名（衝突時自動加上 `_2`、`_3` 後綴）。
- **修復 `run90` 編譯／幾何／度量與 Worker 產物驗證及父行程清理**：
  - 更新 [run90.py](src/OpenCCFontGenerator/run90.py)：`save_font_json()` 改為暫存檔原子建置並強制 `check=True` 與非空檔檢查；僅對旋轉字形同步寫入 `glyf['advanceWidth']`（保留未旋轉西文比例寬度）、依 `unitsPerEm` 計算旋轉中心與全域度量、預設讀取 `.ttc` 第 0 面，並修正複合字形（`references`）旋轉矩陣與平移對齊。
  - 更新 [worker.py](src/OpenCCFontGenerator/web/worker.py)：`_register_outputs()` 驗證所有必要產物皆位於 `outputs/`、非符號連結、非空一般檔案，家族模式開啟 `output_woff2` 時亦嚴格要求每個變體均含有效 WOFF2；各模式依實際字型輪廓決定 `.ttf`/`.otf` 副檔名；[font.py](src/OpenCCFontGenerator/font.py) 的 `save_font()` 不再吞掉 WOFF2 壓縮例外且改為暫存原子寫入。
  - 更新 [jobs.py](src/OpenCCFontGenerator/web/jobs.py)：`JobManager` 為每個 Worker 建立獨立 `TMPDIR` 與精簡環境變數、記錄 POSIX PGID 確保超時與關機終止整組子行程、異常時確實回滾記憶體佇列，並由父行程於任務成功、失敗、逾時、取消或重啟後統一清理 `inputs/`、`tmp/` 與中間資料夾。
- **修復核心字型引擎 `font.py`、`static_family.py` 與 `vf_family.py` 邊界缺陷**：
  - [font.py](src/OpenCCFontGenerator/font.py)：`ensure_gsub_feature_targets()` 納入 `requiredFeature` 避免與 `features` 重複 tag；`apply_force_vertical()` 相容 `otfcc` 帶索引 Feature list；`clone_fallback_glyph()` 移除錯誤提早返回，確保同名碰撞 glyph 正確改名；`apply_variants()` 新增 `ISOLATED_VARIANT_GROUPS` 隔離一簡對多繁易混異體（`後/后`、`面/麵`、`臺/檯/颱`、`餘/余`、`發/髮`）；`.ttc` 未指定索引預設改為 `0`。
  - [static_family.py](src/OpenCCFontGenerator/static_family.py)：字重比對依別名長度由長至短優先匹配（避免 `ExtraBold` 誤配 `Bold`），嚴格檢查 `fallback_prefix` 查無檔案即報錯，並改以輸出檔 stem 去重防止 `.ttf` + `.otf` 開啟 WOFF2 時互蓋。
  - [vf_family.py](src/OpenCCFontGenerator/vf_family.py)：驗證 `wght` 軸範圍（明確指定超界字重即報錯）、僅於存在 `STAT` 表時更新字型名稱、自動將 `CFF2` 實例降級為 `CFF1` 以相容 `otfcc`，並對中文 stem 採 UTF-8 位元組安全裁切。
- **強化 Web API 上傳准入、ZIP 預檢、反代 IP 正規化與下載租約**：
  - [app.py](src/OpenCCFontGenerator/web/app.py) 與 [__main__.py](src/OpenCCFontGenerator/web/__main__.py)：`UploadGuardMiddleware` 於讀取 multipart 前即檢查全域同時上傳上限（`OPENCC_WEB_MAX_CONCURRENT_UPLOADS`）、佇列滿載（`503`）與磁碟剩餘空間門檻（`OPENCC_WEB_MIN_FREE_MB` -> `507`），並於 `submit_job()` 原子交接釋放上傳名額避免雙重計算；停用 Uvicorn `proxy_headers` 改由應用層單一權威解析並正規化 IPv4/IPv6（無效轉發標頭回退 peer IP）；`SlidingWindowRateLimiter` 限制鍵數上限並節流過期掃描。
  - [jobs.py](src/OpenCCFontGenerator/web/jobs.py)：開 `ZipFile` 前先掃描 EOCD / ZIP64 中央目錄限制條目數（含資料夾）與目錄大小，拒絕加密或非 Deflate/Store 壓縮格式並統一回傳 `400`；檔名改以 UTF-8 位元組上限（`180 bytes`）裁切；`job_id` 升級為 32 位 hex；新增下載租約避免 TTL/DELETE 與串流下載互搶，所有任務與下載回應皆附帶 `Cache-Control: private, no-store`；`/healthz` 擴充檢查全部 5 組詞表與異體字庫。
- **修復 CSS 模板跳脫、cURL 預覽與 Web 前端輪詢／重繪／無障礙細節**：
  - [webfont.py](src/OpenCCFontGenerator/webfont.py) 跳脫包含 `\f` 在內的控制字元並對 `url(...)` 進行百分號編碼；[jobs.py](src/OpenCCFontGenerator/web/jobs.py) 對 `download_url` 檔名進行 `urllib.parse.quote` 百分號編碼。
  - [app.js](src/OpenCCFontGenerator/web/static/app.js) 與 [index.html](src/OpenCCFontGenerator/web/static/index.html)：以 `AbortController` + 序號鎖定單一在途輪詢避免舊回應倒序覆寫；進行中卡片改為原地更新耗時、進度與日誌（不再因時間跳動重建 DOM 遺失焦點）；`DELETE` 僅於伺服器確認成功或 `404` 時才移除本機紀錄；cURL 預覽改用 `--form-string` 與引用檔案路徑；補齊行動端抽屜背景 `inert` 鎖定與焦點切換，並標註見本條屬詞表預覽。

### Changed

- **改用多階段原始碼編譯 `otfcc` 與唯讀安全強化**：
  - [Dockerfile](Dockerfile) 移除已失效的 `otfcc-linux.x64-0.10.4.zip` 404 下載，改為驗證 SHA-256 後從 `caryll/otfcc v0.10.4` 原始碼編譯 `otfccdump` / `otfccbuild`（原生支援 `linux/amd64` 與 `linux/arm64`），建置後清理 `/app/build`，並將 `/app` 與執行檔設為 `root` 唯讀權限，僅開放 `/data/jobs` 與 `/data/tmp` 給 `appuser`。
  - [docker-compose.yml](docker-compose.yml) 預設僅綁定 `127.0.0.1:8000:8000`、預設單一並發 Worker（`OPENCC_WEB_MAX_CONCURRENT_JOBS=1`）配合 `4g` 記憶體避免 OOM，啟用 `read_only: true`、`cap_drop: [ALL]`、`tmpfs: /tmp` 與環境變數參數化，並同步更新 [README.md](README.md) 與 [PRODUCT.md](PRODUCT.md)。
- **補充單元與 Web API 測試**：更新 [tests/test_font_io.py](tests/test_font_io.py) 與 [tests/test_web_api.py](tests/test_web_api.py)，涵蓋上述全部核心引擎、ZIP/上傳准入、下載租約、反代正規化與 `variable-family` 端到端實測（全部 38 項測試通過）。

---

## [2026-11-15]

### Added

#### 新增 FastAPI Web 工作台、非同步 REST API 與 Docker 部署架構
- **新增 Web / API 服務模組 `src/OpenCCFontGenerator/web/`**：
  - 建立 [config.py](src/OpenCCFontGenerator/web/config.py)、[rate_limit.py](src/OpenCCFontGenerator/web/rate_limit.py)、[schemas.py](src/OpenCCFontGenerator/web/schemas.py)、[preview.py](src/OpenCCFontGenerator/web/preview.py)、[worker.py](src/OpenCCFontGenerator/web/worker.py)、[jobs.py](src/OpenCCFontGenerator/web/jobs.py)、[app.py](src/OpenCCFontGenerator/web/app.py) 與 [__main__.py](src/OpenCCFontGenerator/web/__main__.py)。
  - 完整支援五大字型流程：`convert`（單一字型簡繁轉換 + Fallback 補字 + WOFF2 + Kobo）、`rotate90`、`webfont`、`static-family` 與 `variable-family`，支援多檔及 `.zip` 壓縮包上傳與批次輸出打包。
  - 每個編譯任務於獨立隔離目錄與獨立 Subprocess Worker 中執行（確保 `opencc_gen_debug.log` 不互撞且結束後立即釋放 CJK 字型編譯記憶體），並提供單檔／總容量上限、ZIP Zip-Slip／壓縮彈防護、滑動視窗 IP 速率限制、佇列並發控管與背景 TTL 自動清除機制。
  - 提供 `/healthz`、`/api/v1/capabilities`、`/api/v1/preview`、`/api/v1/jobs/*` 及內建 Swagger UI（`/docs`）/ ReDoc（`/redoc`）。
- **新增響應式 Web 工作台前端（`src/OpenCCFontGenerator/web/static/`）**：
  - 實作「CJK 字體見本帳工作台」介面（[index.html](src/OpenCCFontGenerator/web/static/index.html)、[styles.css](src/OpenCCFontGenerator/web/static/styles.css)、[app.js](src/OpenCCFontGenerator/web/static/app.js)、[favicon.svg](src/OpenCCFontGenerator/web/static/favicon.svg)），包含即時 OpenCC 轉換見本條、拖曳上傳與即時上傳進度、cURL API 指令即時生成，以及具 `localStorage` 追蹤能力的非同步任務日誌佇列。
- **新增 Docker 單容器建置與生產部署檔**：
  - 新增 [requirements-web.txt](requirements-web.txt)、[Dockerfile](Dockerfile)（基於 `linux/amd64` `python:3.12-slim`，建置期預載 `otfcc` v0.10.4 與編譯 `OpenCC 1.4.2` 快取、非 root 使用者執行與 `HEALTHCHECK`）、[.dockerignore](.dockerignore) 與 [docker-compose.yml](docker-compose.yml)。
  - 更新 [setup.py](setup.py) `package_data` 納入 `web/static/*`，更新 [README.md](README.md) 補充 Web / API / Docker 部署文件，並紀錄 [PRODUCT.md](PRODUCT.md) 與 [DESIGN.md](DESIGN.md)。
- **新增 Web / API 整合測試 `tests/test_web_api.py`**：涵蓋健康檢查（含 `503` 降級回應）、即時預覽對照表、速率限制、反代 IP 鏈驗證、Pre-multipart 上傳大小攔截、ZIP 共享解壓預算與目錄穿越防護、佇列插槽預留，以及 `webfont`、`convert`、`rotate90`、`static-family` 非同步 Worker 端到端生命週期（未安裝可選 Web 依賴時優雅略過）。
- **依據多方 Code Review（Codex CLI / OMP CLI / OpenCode CLI）兩輪審查進行安全性與強健性加固**：
  - [config.py](src/OpenCCFontGenerator/web/config.py)、[app.py](src/OpenCCFontGenerator/web/app.py)、[__main__.py](src/OpenCCFontGenerator/web/__main__.py)：預設關閉 `OPENCC_WEB_TRUST_PROXY_HEADERS`，新增 `OPENCC_WEB_TRUSTED_PROXIES` 可信反代 CIDR 驗證（未設定或無效設定時 Fail-Closed 不採信轉發標頭）；並以純 ASGI `UploadGuardMiddleware` 於 Starlette 解析 Multipart 前執行 IP 速率限制、`Content-Length` 與 Chunked 串流上限攔截（確保回傳 `413` 而非 `400`）；強化 `_env_int()` 容錯、補齊 Python 3.8+ `typing` 相容性、防禦 `fallback_prefix` / `sanitize_filename_part()` 路徑穿越並於 [vf_family.py](src/OpenCCFontGenerator/vf_family.py) 內驗證目標路徑，`/healthz` 異常時改回傳 HTTP `503`。
  - [jobs.py](src/OpenCCFontGenerator/web/jobs.py)、[worker.py](src/OpenCCFontGenerator/web/worker.py)、[rate_limit.py](src/OpenCCFontGenerator/web/rate_limit.py)、[preview.py](src/OpenCCFontGenerator/web/preview.py)：加入請求級共享 `ZipExtractionBudget` 與非同步執行緒解壓、基於 `_pending_dirs` 的無洩漏排隊插槽預留（涵蓋 `BaseException` / `CancelledError` 與孤兒清理）、POSIX `start_new_session` / `os.killpg` 整組子行程（含 `otfcc`）超時／取消清理、`32 KiB` 分段尾端 Log 讀取、重啟中斷任務延長保留完整 TTL、Python 3.8 相容執行緒池關閉與快取強化。
  - 前端與部署（[index.html](src/OpenCCFontGenerator/web/static/index.html)、[styles.css](src/OpenCCFontGenerator/web/static/styles.css)、[app.js](src/OpenCCFontGenerator/web/static/app.js)、[Dockerfile](Dockerfile)、[docker-compose.yml](docker-compose.yml)）：補齊行動端抽屜 `inert` 管理、`Escape` 關閉與切頁焦點移轉、`aria-current` 與即時狀態 `role="status"`、`AbortController` 過時預覽請求取消、cURL 單引號安全跳脫、輪詢斷線指數退避重試，以及 Docker `mem_limit` / `cpus` / `pids_limit` / `no-new-privileges` 資源與權限上限。

#### 新增 OpenCC 詞庫與版本升級 Skill（`opencc-dict-upgrade`）
- **新增專案 Skill `.agents/skills/opencc-dict-upgrade/SKILL.md`**：系統化整理對齊上游 `BYVoid/OpenCC` 與 `opencc-data` 的升級步驟、必守建表不變量（單字異體表防反推污染、`k == v` guard 剪枝、`.cache_version` 雙戳記、`t2twp.json` schema 驗證）與發佈前驗證清單。
- **新增驗證腳本 `.agents/skills/opencc-dict-upgrade/scripts/verify_opencc_upgrade.py`**：可一鍵檢查版本戳記、5 組快取詞表完整性與（於 macOS 指定 `--font` 時）`build_font` glyph 上限及 CoreText 塑形結果。
- **新增與更新指引文件 `AGENTS.md` / `README.md`**：建立根目錄 [AGENTS.md](AGENTS.md) 說明環境、關鍵不變量與 `opencc-dict-upgrade` skill 入口，並在 `README.md` 補充 `--config` 各模式差異與 `twp` 超翻／排版錯位風險對照表，以及詞庫升級與驗證腳本使用說明，確保後續開發或新 session 能立即找到並遵守規範。
- **整理專案文件與 OpenSpec Skills 目錄**：納入 Web 化可行性評估文件 `docs/web-port-feasibility-assessment.md`，並將舊版各 IDE／CLI 專屬 OpenSpec skills 統整遷移至 `.agents/skills/`（含新增 `openspec-sync-specs`、`openspec-update-change`）。
- **Files added/updated**: `.agents/skills/opencc-dict-upgrade/SKILL.md`, `.agents/skills/opencc-dict-upgrade/scripts/verify_opencc_upgrade.py`, `.agents/skills/openspec-*`, `AGENTS.md`, `README.md`, `docs/web-port-feasibility-assessment.md`

### Changed

#### 對齊上游 BYVoid/OpenCC 最新版（`OpenCC 1.4.2` / `opencc-data@1.4.2`）
- **升級 OpenCC 套件與詞庫版本**：
  - 將 `requirements.txt` 與 `setup.py` 的依賴從 `opencc<1.2` 更新為 `opencc>=1.4.2`，並在 `.virtualenvs/opencc_gen` 環境安裝 `opencc==1.4.2`。
  - 將 `setup.py` 的 `OPENCC_DATA_VERSION` 更新為 `1.4.2`，改從 `opencc-data@1.4.2` 下載字典，並透過 `opencc_data/.opencc_data_version` 與 `cache/.cache_version` 追蹤版本狀態，確保版本升級或部分建置失敗時能自動重刷快取。
  - 更新 `run.sh` 的版本驗證邏輯，檢查 `opencc >= (1, 4, 2)` 與快取版本檔 `.opencc_data_version == 1.4.2`。
- **相容 OpenCC 1.4.2 字典格式與設定檔結構**：
  - 在 `setup.py` 新增 `iter_opencc_dict()` 以安全跳過 `opencc-data@1.4.2` 的 `#` 註解與空行，並納入新增的 `STPhrases_GeneratedFromRegionalPhrases.txt`、`TWVariantsPhrases.txt`、`HKVariantsPhrases.txt` 與合併後的 `TWPhrases.txt`。
  - 重構 `src/OpenCCFontGenerator/t2twp.json`，改用 `1.4.2` 的 `TWPhrases.txt`、`TWVariantsPhrases.txt`、`TWVariants.txt`，並於 `segmentation.dict` 補齊 `"match_policy": "union"` 與 `conversion_chain` 的 `"match_policy": "short_circuit"`，消除 schema 警告；同時在 `setup.py` 傳入 `t2twp.json` 完整副檔名。
  - 在 `setup.py` 建表時：針對一簡對多繁／防護詞條保留觸及單字或子詞的 `k == v` guard（如 `皇后 -> 皇后`）並剪除多餘無差異 `k == v` 條目，讓轉換後字型 glyph 數維持在 65,535 上限內（實測 `Iansui-Regular` + `twp` 為 `56,998` glyphs）；同時避免對單字異體表（`TWVariants.txt`、`HKVariants.txt`）反推 `t2s(k)`，防止 `麪->麵`、`檯->枱`、`柺->枴` 誤覆寫為 `面->麵`、`台->枱`、`拐->枴`。
- **驗證**：已完成 `python setup.py build` 重建 5 組設定快取（`s2t`、`twp`、`s2tw`、`s2hk`、`t2s`），驗證 `皇后`、`后来`、`发现`、`业余`、`软件`、`面`、`面条` 與 `s2hk` 詞表，並對 `Iansui-Regular.ttf`（`twp`）實測編譯與 CoreText 塑形驗證通過。
- **Files changed**: `requirements.txt`, `setup.py`, `src/OpenCCFontGenerator/t2twp.json`, `run.sh`, `CHANGELOG.md`

### Fixed

#### OpenCC GSUB 詞彙替換失效（如「后来」顯示「后來」、「业余」顯示「業余」）與異體字跨字誤映（如「發現」／「髮現」）
- **修復 GSUB 重複 Feature Tag 導致 OpenCC 替換規則完全失效**：
  - `otfccdump` 會將來源字型原有的 feature 匯出成帶索引後綴的名稱（如 `liga_00036`、`rlig_00051`、`ccmp_00007`）。原本的 `insert_empty_feature()` 直接新增 `liga` / `rlig` / `ccmp` 鍵值，造成同一個語系內出現重複 feature tag，導致 CoreText 與 HarfBuzz 忽略 OpenCC 的 `word2pseu`、`char2char`、`pseu2word` lookups，使「后来」在僅套用 `cmap` 下顯示為「后來」、「业余」顯示為「業余」。
  - 現在會辨識並合併既有的同 tag feature（如 `liga_*`、`rlig_*`、`ccmp_*`），確保每個 `LangSys` 僅保留單一 `liga` / `rlig` / `ccmp` feature，並維持 `word2pseu -> char2char -> pseu2word` 的 lookup 執行順序。
- **修正 `apply_variants()` 執行順序與異體字跨字污染**：
  - 將 `apply_variants()` 移至 `--fallback-font` 補字完成之後再執行，避免在有備用字型時搶先把缺失的繁體字（如「後」、「發」、「髮」）提前映到簡體或異體字形，導致 fallback 補字失效。
  - 在 `apply_variants()` 中隔離同簡對多繁的易混字形（例如不讓 `發`／`発` 與 `髮`／`髪` 彼此交叉回退），避免缺字時把「發現」誤顯為「髮現」或把「頭髮」誤顯為「頭發」。
  - 修正 `apply_variants()` 解析 `Var_hk.txt` 中含空白字元的項目時拋出 `TypeError` 的問題，並在 `t2s` 模式下略過繁體異體字預填，避免干擾繁轉簡規則。
- **去除 `word2pseu` 重複來源字形序列**：避免 `cmap` 補齊簡體碼位後產生重複的 `from` glyph sequence，節省 pseudo glyph 名額並確保編譯結果穩定。
- **OpenType `65,535` Glyph 上限自動保護（Large CJK 字型相容）**：
  - 在 `src/OpenCCFontGenerator/font.py` 的 `build_font()` 中，於 `merge_mode != 'universal'` 且 `glyph_count + len(final_entries_word) > 65535` 時自動裁剪不在 OpenCC 所需字集、常用漢字符與非漢字範圍內的冗餘字形（如 `LXGWWenKai`、`TaiwanPearl`、`NaikaiFont` 等 44k–50k glyphs 的大型字庫），同時保持中小字庫 100% 原字形不變；並同步更新 `README.md` 重要限制說明。
  - 新增單元測試驗證超過上限時自動 subset 且保留所有 OpenCC GSUB 詞彙字形。
- **驗證**：已對 `Iansui-Regular.ttf` 與 `[origin]/jf金萱那提2.0半糖.otf` 實測重建並以 CoreText 驗證（`业余`/`業余`→`業餘`、`后来`→`後來`、`皇后`→`皇后`、`发现`→`發現`、`头发`→`頭髮`、`多余`→`多餘`），並通過單元測試。
- **Files changed**: `src/OpenCCFontGenerator/font.py`, `tests/test_font_io.py`, `CHANGELOG.md`

---

## [2026-08-08]

### Fixed

#### CFF OTF browser rejection (`Invalid font data in ArrayBuffer`)
- 修復 CFF-based OTF 經 `otfccbuild 0.10.4` 重建後，可能把相鄰 stem hint operators 合併，產生超過 CFF1 48-operand stack 上限的 Type 2 CharString。
- 所有 CFF 字型現在都會在送入 `otfccdump` 前先以 fontTools desubroutinize 並移除 hints，避免 Chromium／Firefox OTS 拒絕整份字型。
- `otfccbuild` 現在使用暫存檔原子建置，失敗時會拋出錯誤，不會留下或誤用舊輸出。
- 產物會重新編譯 CFF、移除 otfcc 寫入的非標準 FontDict 欄位，並完整載入所有 OpenType tables 驗證後才取代目標檔案。
- 新增 CFF 正規化、輸出驗證、權限保留與失敗不覆寫的單元測試。
- **Files changed**: `src/OpenCCFontGenerator/font.py`, `tests/test_font_io.py`, `requirements.txt`, `setup.py`, `run.sh`

#### Font Book `name` 表架構警告與亂碼名稱
- 修復輸出字型在 macOS 字體簿中出現金嘆號、`[name 表架構]` 警告，以及名稱顯示亂碼的問題。
- 調整 metadata 寫入策略：
  - `platform 1` 的 legacy name records 改為使用 ASCII-safe 名稱，避免中文名稱落入不相容的 Macintosh name encoding。
  - `platform 1 / encoding 25` 的 `nameID 1/3/4/6` 現在會以正確的 legacy bytes 格式重寫，不再留下空值或舊 PostScript 名稱。
  - 補齊 `Windows zh-TW (languageID 1028)` 的 `nameID 3/5/6`，讓繁中語系的 name record 結構完整一致。
- 已以 Font Book 直接開啟重建後的字型驗證，警告已消失。
- **Files changed**: `src/OpenCCFontGenerator/font.py`

#### OpenCC Fallback Path Crash: `char2char_table` 未初始化
- 修復在 `fallback_font + fill_charset + opencc merge` 路徑下，若單字轉換需要建立 GSUB `char2char` 替換表時，程式會因 `char2char_table` 未先初始化而直接拋出 `NameError`。
- 現在會在單字轉換流程開始前建立 `char2char_table`，讓已存在來源碼位、但仍需改寫為目標 glyph 的情況可以正常累積替換規則。
- 已用互動式精靈 `start.py` 依實際參數重跑驗證，原本的 `name 'char2char_table' is not defined` 已消失，並成功輸出 `.ttf` 與 `.woff2`。
- **Files changed**: `src/OpenCCFontGenerator/font.py`

#### Kindle & E-Reader Critical Fix: "Missing Source Character" Conversion Bug
- **重大修正**：修復了原本「來源字不在字型中則不轉換」的錯誤邏輯。
- **問題背景**：原本程式會檢查簡體字（來源）是否在字型中，若字型是純繁體字型（如 `jf金萱`），其 `cmap` 根本沒有簡體編碼，導致程式跳過轉換規則。在 Kindle 上顯示時，簡體字會因缺字而回退到系統字型，造成轉換失敗的假象。
- **解決方案**：
    - 改為**直接修改 `cmap`**：只要目標繁體字存在於字型中，就強行將簡體編碼指向該繁體字形。這不依賴 GSUB，相容性最高。
    - **放寬轉換條件**：轉換規則的建立不再受限於來源字是否存在於字型中。
- **影響**：大幅提升在 Kindle、Kobo 等電子書設備上的繁簡轉換覆蓋率。
- **Files changed**: `src/OpenCCFontGenerator/font.py`

#### 變體與異體字自動補全 (Variant Supplementing)
- 引進類似 `TCFontCreator` 的異體字回退機制。
- 新增 `Variants.txt`, `Var_tw.txt`, `Var_hk.txt`, `Var_cl.txt` 等字典。
- 運作原理：如果字型缺少某個編碼（如「妳」），但有其對應變體（如「你」），程式會自動將「妳」的編碼指向「你」的字形，避免缺字。
- **Files changed**: `src/OpenCCFontGenerator/font.py`, `src/OpenCCFontGenerator/opencc_data/*.txt`

### Added

#### `--kobo` — Kobo eReader 相容模式
- 新增 `--kobo` CLI 參數與精靈選項。
- 專門針對 Kobo eReader 的嚴格字型解析機制設計，修正因 Family Name 包含空格或非 ASCII 字元導致無法正確辨識與群組的問題。
- 開啟後，會強制濾除中文命名紀錄 (如 `zh-TW`)，並確保 `nameID 1/2/4/6/16/17` 符合純英文無空白的嚴格格式。
- **Files changed**: `src/OpenCCFontGenerator/font.py`, `src/OpenCCFontGenerator/__main__.py`, `src/OpenCCFontGenerator/static_family.py`, `src/OpenCCFontGenerator/vf_family.py`, `startSTATIC.py`, `startVF.py`, `start.py`

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
