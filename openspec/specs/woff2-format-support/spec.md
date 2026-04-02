## ADDED Requirements

### Requirement: 支援 WOFF2 字型讀取
系統 MUST 能夠接受 `.woff2` 檔案作為來源字型輸入。在進行核心處理（otfccdump）之前，系統 SHALL 自動偵測檔案格式並將 WOFF2 解壓縮為臨時的 TTF 格式。

#### Scenario: 讀取 WOFF2 檔案
- **WHEN** 使用者輸入 `my_font.woff2` 作為來源路徑
- **THEN** 系統自動調用 `fontTools` 解壓並生成臨時 TTF 供後續處理

### Requirement: 支援 WOFF2 字型輸出
系統 MUST 能夠將生成的 TTF 字型壓縮為 `.woff2` 格式。

#### Scenario: 生成 WOFF2 檔案
- **WHEN** 處理完成並生成 `output.ttf` 後
- **THEN** 系統自動調用 `fontTools` 壓縮並儲存為 `output.woff2`
