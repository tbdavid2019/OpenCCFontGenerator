## Context

當前字型處理流程依賴 `otfccdump` 與 `otfccbuild`。由於這些工具不原生支援 WOFF2，我們需要引入 `fontTools` 作為預處理與後處理工具。

## Goals / Non-Goals

**Goals:**
- 讓使用者能直接輸入 `.woff2` 檔案。
- 在輸出時，可以選擇同時生成 `.ttf` 與 `.woff2`。
- 自動化 WOFF2 的解壓（decompress）與壓縮（compress）過程。

**Non-Goals:**
- 不支援 WOFF1（市場需求較低且 fontTools 處理方式略有不同，先專注於 WOFF2）。
- 不處理字型子集化（Subsetting），維持現有的全字元處理邏輯。

## Decisions

### 1. 引入 `fontTools` 作為核心轉換引擎
- **理由**：`fontTools` 是 Python 字型處理的事實標準，對 WOFF2 的支援非常成熟。
- **替代方案**：調用外部 `woff2_decompress` 二進位檔。缺點是需要使用者額外安裝 C++ 編譯的工具，不夠自動化。

### 2. 在 `load_font` 前進行透明解壓
- **做法**：如果輸入路徑以 `.woff2` 結尾，先將其轉換為臨時 `.ttf` 檔案，再交給 `otfccdump`。

### 3. 多格式輸出邏輯
- **做法**：在 `build_font` 完成 `.ttf` 生成後，如果使用者啟動了 `woff2` 選項，則立即調用 `fontTools` 進行壓縮。

## Risks / Trade-offs

- **依賴體積**：`fonttools` 與 `brotli` 會增加一些依賴大小，但考慮到功能增益，這是可以接受的。
- **處理時間**：WOFF2 的壓縮與解壓縮需要額外的計算時間，特別是對於中文字型，但這在可接受範圍內。
