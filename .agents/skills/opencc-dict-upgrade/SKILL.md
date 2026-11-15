---
name: opencc-dict-upgrade
description: >-
  Use this skill when upgrading the OpenCC library and opencc-data dictionaries
  to align OpenCCFontGenerator with a newer upstream BYVoid/OpenCC release,
  rebuilding the cache tables, validating conversion invariants (such as 皇后,
  后来, 业余, 发现/头发, 面/面条, and the 65,535 glyph limit), and updating config
  files.
---

# OpenCC 詞庫與版本升級流程

此 Skill 用於將本專案的 `opencc` Python 套件、`opencc-data` 詞庫、`t2twp.json`、`setup.py` 快取建置邏輯與 `run.sh` 對齊上游 `BYVoid/OpenCC` 新版本。

## 1. 確認上游目標版本與結構差異

升級前先檢查三個來源的最新版本與字典差異：

1. **PyPI `OpenCC` 與 npm `opencc-data` 版本**：確認兩者版本一致（例如 `1.4.2`），並先在虛擬環境測試安裝或比對。
2. **檢查新版內建設定 schema 與詞庫清單**：
   - 在已安裝新版 `opencc` 的 Python 環境讀取 `opencc._opencc_share_dir` 底下的 `s2tw.json`、`s2twp.json`、`s2hk.json`。
   - 核對是否有：
     - 新增、更名或合併的字典檔（如 `1.4.2` 將 `TWPhrases*.txt` 合併為 `TWPhrases.txt`，並新增 `STPhrases_GeneratedFromRegionalPhrases.txt`、`TWVariantsPhrases.txt`、`HKVariantsPhrases.txt`）。
     - 設定檔 schema 變更（如 `group` dict 需指定 `"match_policy": "union"` 或 `"short_circuit"`）。
     - 字典檔案格式變更（如開頭 `#` 註解行與空行）。

## 2. 需同步檢查與更新的檔案

逐一確認以下檔案：

1. **`requirements.txt` & `setup.py` (`install_requires`)**
   - 將 `opencc` 版本下限更新為目標版本（如 `opencc>=1.4.2`）。
2. **`setup.py` 下載與版本戳記**
   - 更新 `OPENCC_DATA_VERSION`。
   - 同步更新 `download_data()` 的 `required_files` 與從 `https://cdn.jsdelivr.net/npm/opencc-data@{OPENCC_DATA_VERSION}/data/` 下載的檔名清單，以及 `build_codepoints()` 遍歷的字典清單。
   - 維持 `opencc_data/.opencc_data_version` 與 `cache/.cache_version` 雙戳記檢查，確保中斷或部分失敗的建置仍會在下次 `setup.py build` 時強制重刷快取。
   - 使用 `iter_opencc_dict()` 略過 `#` 註解行與空行。
   - 傳給 `OpenCC(...)` 的本地設定路徑必須帶完整 `.json` 副檔名（`path.join(pkgroot, 't2twp.json')`），因新版 `opencc` 僅對內建 stem 自動補 `.json`。
3. **`setup.py` 建表不變量（不可破壞）**
   - **禁止對單字異體表（`TWVariants.txt`、`HKVariants.txt`）反推 `t2s(k)`**：只保留 `(k, v)` 原鍵值，否則會造成一簡對多繁反推污染（例如 `麪->麵` 反推成 `面->麵`、`檯->枱` 反推成 `台->枱`、`柺->枴` 反推成 `拐->枴`）。
   - **區域片語表（`TWPhrases.txt`、`TWVariantsPhrases.txt`、`HKVariantsPhrases.txt`）**才同時輸出 `(k, v)` 與（當 `t2s(k) != k` 時的）`(t2s(k), v)`。
   - **`k == v` 防護詞條（guard）剪枝策略**：保留「任一字元落在已變動單字集 `single_char_keys`，或任一長度 `>= 2` 子字串落在已變動片語集 `diff_phrases`」的 `k == v` 條目（例如 `皇后 -> 皇后` 必須保留，防止被 `后 -> 後` 誤轉）；剪除純無差異條目，避免產生過多 pseudo glyphs 而超過 OpenType `65,535` 上限。
4. **`src/OpenCCFontGenerator/t2twp.json`**
   - 對齊目標版本 OpenCC 的 schema（`segmentation.dict` 需保留 `"match_policy": "union"`、`conversion_chain[].dict` 保留 `"match_policy": "short_circuit"`），且引用的 `./opencc_data/*.txt` 需與 `setup.py` 下載清單一致。
   - 用目標版 `OpenCC('src/OpenCCFontGenerator/t2twp.json')` 實測不應輸出 schema warning。
5. **`run.sh`**
   - 同步更新 Python 套件檢查版本與 `.opencc_data_version` 檢查字串。
6. **`CHANGELOG.md`**
   - 依專案規範於日期標題 `## [YYYY-MM-DD]`（不使用 `[Unreleased]`）詳細記錄變更與驗證結果。

## 3. 重建快取與執行驗證

1. 在虛擬環境升級 `opencc`（必要時安裝 `setuptools`）並強制重建快取：

   ```bash
   VENV="$HOME/.virtualenvs/opencc_gen"
   "$VENV/bin/pip" install --upgrade "opencc==<TARGET_VERSION>" setuptools
   rm -f src/OpenCCFontGenerator/cache/.cache_version
   "$VENV/bin/python" setup.py build
   ```

2. 執行本 Skill 附帶的驗證腳本檢查 5 組快取表（`s2t`、`twp`、`s2tw`、`s2hk`、`t2s`）；若為 macOS 且有測試字體（如 `~/Library/Fonts/Iansui-Regular.ttf`），可一併驗證實際 `build_font`、glyph 上限與 CoreText 塑形結果：

   ```bash
   PATH="$HOME/.virtualenvs/opencc_gen/bin:$PATH" \
   PYTHONPATH=src \
   "$HOME/.virtualenvs/opencc_gen/bin/python" \
     .agents/skills/opencc-dict-upgrade/scripts/verify_opencc_upgrade.py \
     --expected-version "<TARGET_VERSION>" \
     --font "$HOME/Library/Fonts/Iansui-Regular.ttf"
   ```

   （若僅驗證快取與設定不測字體編譯，可省略 `--font` 參數。）

3. 執行最後編輯後的靜態檢查與單元測試：

   ```bash
   bash -n run.sh
   "$HOME/.virtualenvs/opencc_gen/bin/python" -m py_compile setup.py src/OpenCCFontGenerator/font.py tests/test_font_io.py
   "$HOME/.virtualenvs/opencc_gen/bin/python" -c "import json; json.load(open('src/OpenCCFontGenerator/t2twp.json', encoding='utf-8'))"
   PYTHONPATH=src "$HOME/.virtualenvs/opencc_gen/bin/python" -m unittest discover -s tests -v
   ```
