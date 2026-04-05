## 1. 基礎設施與核心邏輯

- [x] 1.1 建立 `runWEBFONT.sh` 啟動腳本
- [x] 1.2 建立 `src/OpenCCFontGenerator/webfont.py` 處理 WOFF2 壓縮
- [x] 1.3 建立 `startWEBFONT.py` 互動精靈介面

## 2. 功能實作

- [x] 2.1 在 `webfont.py` 中實作 `TTF` 轉 `WOFF2` 的核心函式
- [x] 2.2 在 `webfont.py` 中實作 CSS `@font-face` 範例產出邏輯
- [x] 2.3 確保 `startWEBFONT.py` 能正確引導使用者並執行轉換

## 3. 文件與紀錄更新

- [x] 3.1 更新 `README.md` 加入 Webfont 生成器的使用教學與最佳實踐
- [x] 3.2 更新 `CHANGELOG.md` 紀錄此新功能

## 4. 驗證

- [x] 4.1 測試從 TTF 生成 WOFF2 並檢查 CSS 內容
- [x] 4.2 驗證獨立腳本在不同目錄下的執行情況
