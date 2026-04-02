#!/bin/bash

# ===========================================================================
# OpenCC Font Generator - 90度旋轉 (偽直排) 啟動腳本
# ===========================================================================

VENV_PATH="$HOME/.virtualenvs/opencc_gen"

if [ ! -d "$VENV_PATH" ]; then
    echo "❌ 找不到虛擬環境 $VENV_PATH，請先執行 run.sh 建立環境。"
    exit 1
fi

source "$VENV_PATH/bin/activate"

# 確保必要的套件已安裝
if ! python3 -c "import fontTools" &> /dev/null; then
    echo "📦 正在安裝必要套件..."
    pip install fonttools brotli
fi

echo "💡 正在啟動 OpenCC 90度旋轉精靈..."
python start90.py

deactivate
