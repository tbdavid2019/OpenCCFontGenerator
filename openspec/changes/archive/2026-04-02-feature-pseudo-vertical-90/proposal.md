## Why

目前專案提供的直排模式僅限於標點符號的字形替換，對於僅支援水平排版系統的舊型設備，使用者無法獲得良好的閱讀體驗。透過將字元整體順時針旋轉 90 度，使用者可以旋轉閱讀設備來實現「偽直排」效果。

## What Changes

- **獨立腳本路徑**：新增 `run90.sh`, `run90.py` 與 `start90.py` 以執行旋轉任務。
- **互動式精靈**：提供 `start90.py` 引導式介面，讓使用者輕鬆設定來源路徑、輸出路徑與旋轉中心。
- **幾何旋轉邏輯**：對 `glyf` 表中所有字元的點座標應用 90 度順時針旋轉矩陣。
- **度量衡調整**：重新計算字型寬度與垂直偏移，確保旋轉後排版整齊。
- **檔案命名**：產出的字型將自動加上 `_Rotated90` 後綴。

## Capabilities

### New Capabilities
- `pseudo-vertical-90-rotation`: 實現字元幾何資料的 90 度旋轉與度量調整功能。
- `independent-rotation-script`: 提供獨立的進入點進行旋轉後處理。

### Modified Capabilities
<!-- 無 -->

## Impact

- 檔案結構：新增 `run90.sh`, `src/OpenCCFontGenerator/run90.py`。
- 專案相依性：維持現有依賴（otfcc）。
