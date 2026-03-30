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

# 3. 檢查並自動安裝 otfcc (若系統未安裝)
if ! command -v otfccdump &> /dev/null; then
    echo "⚠️ 尚未安裝 otfcc (otfccdump/otfccbuild)，正在嘗試為您自動安裝..."
    OS=$(uname -s)
    ARCH=$(uname -m)
    OTFCC_URL=""

    if [ "$OS" = "Darwin" ]; then
        if [ "$ARCH" = "arm64" ]; then
            OTFCC_URL="https://github.com/caryll/otfcc/releases/download/v0.10.4/otfcc-macos.arm64-0.10.4.zip"
        else
            OTFCC_URL="https://github.com/caryll/otfcc/releases/download/v0.10.4/otfcc-macos.x64-0.10.4.zip"
        fi
    elif [ "$OS" = "Linux" ]; then
        OTFCC_URL="https://github.com/caryll/otfcc/releases/download/v0.10.4/otfcc-linux.x64-0.10.4.zip"
    fi

    if [ -n "$OTFCC_URL" ]; then
        curl -L -s -o /tmp/otfcc_download.zip "$OTFCC_URL"
        mkdir -p /tmp/otfcc_bin
        unzip -q -o /tmp/otfcc_download.zip -d /tmp/otfcc_bin
        cp /tmp/otfcc_bin/otfccbuild /tmp/otfcc_bin/otfccdump "$VENV_PATH/bin/"
        chmod +x "$VENV_PATH/bin/otfcc"*
        rm -rf /tmp/otfcc_download.zip /tmp/otfcc_bin
        echo "✅ otfcc 已成功安裝至專屬環境！"
    else
        echo "❌ 無法自動判定系統版本，請手動安裝 otfcc (https://github.com/caryll/otfcc)！"
    fi
    echo "--------------------------------------------------------"
fi

# 4. 啟動互動式精靈服務
echo "💡 正在啟動 OpenCC 字型生成器..."
python start.py

# 5. 當結束後，自動退出虛擬環境 (保持當前 Terminal 乾淨)
deactivate
