#!/bin/bash

# ===========================================================================
# OpenCC Font Generator - Static Font Family Batch Builder
# ===========================================================================

VENV_PATH="$HOME/.virtualenvs/opencc_gen"

if [ ! -d "$VENV_PATH" ]; then
    echo "❌ 找不到虛擬環境 $VENV_PATH，請先執行 run.sh 建立環境。"
    exit 1
fi

source "$VENV_PATH/bin/activate"

if ! python3 -c "import fontTools, brotli" &> /dev/null; then
    echo "📦 偵測到缺少必要套件，正在自動安裝..."
    pip install fonttools brotli
fi

if ! command -v otfccdump &> /dev/null; then
    echo "❌ 找不到 otfccdump，請先執行 run.sh 或手動安裝 otfcc。"
    deactivate
    exit 1
fi

echo "💡 正在啟動靜態字型 Family 批次處理精靈..."
python startSTATIC.py

deactivate
