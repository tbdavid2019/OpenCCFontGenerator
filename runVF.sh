#!/bin/bash

# ===========================================================================
# OpenCC Font Generator - Variable Font CJK Family Builder
# ===========================================================================

VENV_PATH="$HOME/.virtualenvs/opencc_gen"

if [ ! -d "$VENV_PATH" ]; then
    echo "❌ 找不到虛擬環境 $VENV_PATH，請先執行 run.sh 建立環境。"
    exit 1
fi

source "$VENV_PATH/bin/activate"

if ! python3 -c "import fontTools; from fontTools.varLib.instancer import instantiateVariableFont" &> /dev/null; then
    echo "📦 正在安裝必要套件..."
    pip install fonttools brotli
fi

if ! command -v otfccdump &> /dev/null; then
    echo "❌ 找不到 otfccdump，請先執行 run.sh 或手動安裝 otfcc。"
    deactivate
    exit 1
fi

echo "💡 正在啟動 Variable CJK Family 建立精靈..."
python startVF.py

deactivate
