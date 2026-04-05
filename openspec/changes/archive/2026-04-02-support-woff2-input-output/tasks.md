## 1. 環境準備與依賴更新

- [x] 1.1 在 `requirements.txt` 中新增 `fonttools` 和 `brotli`
- [x] 1.2 確保 `run.sh` 在安裝依賴時包含這些新項目

## 2. 核心功能實現 (font.py)

- [x] 2.1 修改 `load_font`：增加 WOFF2 偵測，若為 WOFF2 則先解壓為臨時 TTF
- [x] 2.2 修改 `save_font`：支援壓縮為 WOFF2 格式
- [x] 2.3 修改 `build_font`：新增 `output_woff2` 參數，並在 TTF 生成後執行壓縮邏輯
- [x] 2.4 確保臨時 TTF 檔案在處理完成後會被刪除

## 3. 使用者介面更新 (start.py & __main__.py)

- [x] 3.1 修改 `start.py`：在來源路徑提示中加入 `.woff2` 說明
- [x] 3.2 修改 `start.py`：新增步驟詢問使用者「是否同時輸出 WOFF2 格式」
- [x] 3.3 修改 `src/OpenCCFontGenerator/__main__.py`：新增 `--woff2` 選項到 CLI 參數

## 4. 驗證與測試

- [x] 4.1 測試使用 `.woff2` 作為輸入進行轉換
- [x] 4.2 測試同時輸出 `.ttf` 與 `.woff2`
- [x] 4.3 驗證生成的 `.woff2` 檔案在瀏覽器中可正常顯示
