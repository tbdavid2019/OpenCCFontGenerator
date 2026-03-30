#!/bin/bash

# ===========================================================================
# OpenCC Font Generator - 自動啟動指令腳本 / Auto Runner Script
# 
# 這是一個全自動化啟動器，它會把「虛擬環境」統一存放在您的家目錄下，
# 這樣您的專案資料夾就不會出現 .venv 亂七八糟的檔案，方便您同步到其他裝置。
# ===========================================================================

# 1. 定義中央虛擬環境路徑 (在家目錄下，不佔用專案空間)
VENV_ROOT="$HOME/.virtualenvs"
VENV_PATH="$VENV_ROOT/opencc_gen"

# 2. 如果中央虛擬環境不存在，則自動建立並安裝依賴項
if [ ! -d "$VENV_PATH" ]; then
    echo "--------------------------------------------------------"
    echo "🚀 首次執行：正在建立中央虛擬環境於 $VENV_PATH..."
    echo "--------------------------------------------------------"
    
    mkdir -p "$VENV_ROOT"
    python3 -m venv "$VENV_PATH"
    
    # 啟動環境並升級 pip
    source "$VENV_PATH/bin/activate"
    pip install --upgrade pip
    
    # 安裝專案依賴項
    if [ -f "requirements.txt" ]; then
        echo "📦 正在安裝套件..."
        pip install -r requirements.txt
    fi
    
    echo "✅ 環境建立完成！"
    echo "--------------------------------------------------------"
else
    # 環境已存在，直接啟動
    source "$VENV_PATH/bin/activate"
fi

# 3. 啟動互動式精靈服務
echo "💡 正在啟動 OpenCC 字型生成器..."
python start.py

# 4. 當結束後，自動退出虛擬環境 (保持當前 Terminal 乾淨)
deactivate
