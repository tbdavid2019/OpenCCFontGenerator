#!/usr/bin/env python3
"""
startWEBFONT.py — 互動式精靈啟動器 (Webfont 轉換) / Interactive Wizard for Webfont Conversion
"""

import os
import sys

# Allow running from project root without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from OpenCCFontGenerator.webfont import process_webfont

# ---------------------------------------------------------------------------
# Prompt helpers (Copy from start.py logic)
# ---------------------------------------------------------------------------

def prompt_existing_file(message, optional=False):
    while True:
        msg = f"{message} (直接按 Enter 跳過)" if optional else message
        value = input(f"{msg}: ").strip()
        if optional and not value:
            return None
        if os.path.isfile(value):
            return value
        print(f"  ❌ 找不到檔案：{value}，請確認路徑後再試。")

def prompt_yes_no(message, default=False):
    hint = "(y/N)" if not default else "(Y/n)"
    while True:
        raw = input(f"{message} {hint}: ").strip().lower()
        if raw == "":
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  ❌ 請輸入 y 或 n。")

# ---------------------------------------------------------------------------
# Main wizard
# ---------------------------------------------------------------------------

def main():
    print()
    print("=" * 60)
    print("  OpenCC Webfont 轉換精靈 / Webfont Conversion Wizard")
    print("  (產出高品質 WOFF2 並自動生成 CSS 範例)")
    print("=" * 60)
    print()

    # --- Step 1: Source font ---
    print("【步驟 1】來源字型路徑 / Source Font Path")
    input_file = prompt_existing_file("請輸入 TTF/OTF 字型路徑")
    print()

    # --- Step 2: Output path ---
    print("【步驟 2】輸出路徑 / Output Path")
    base, _ = os.path.splitext(input_file)
    default_output = f"{base}.woff2"
    raw_output = input(f"請輸入 WOFF2 輸出路徑 [預設: {default_output}]: ").strip()
    output_file = raw_output if raw_output else default_output
    print(f"  ✓ 輸出路徑已設定為：{output_file}\n")

    # --- Step 3: Font Family Name ---
    print("【步驟 3】設定 CSS Font Family / CSS Font Family Name")
    default_family = os.path.splitext(os.path.basename(output_file))[0]
    raw_family = input(f"請輸入字型家族名稱 [預設: {default_family}]: ").strip()
    font_family = raw_family if raw_family else default_family
    print(f"  ✓ Font Family 已設定為：{font_family}\n")

    # --- Summary ---
    print("-" * 50)
    print("  設定摘要 / Summary")
    print("-" * 50)
    print(f"  來源檔案:     {input_file}")
    print(f"  輸出檔案:     {output_file}")
    print(f"  CSS Family:   {font_family}")
    print(f"  額外產出:     fonts.css")
    print("-" * 50)
    print()

    confirm = prompt_yes_no("確認並開始轉換為 Webfont？", default=True)
    if not confirm:
        sys.exit(0)

    print()
    print("⏳ 正在壓縮為 WOFF2 並產出 CSS，請稍候...")
    print()

    try:
        process_webfont(
            input_path=input_file,
            output_path=output_file,
            font_family=font_family
        )
    except Exception as e:
        print(f"❌ 轉換失敗：{e}")
        sys.exit(1)

    print(f"\n✅ 完成！請查看輸出目錄下的檔案：")
    print(f"   1. {os.path.basename(output_file)} (字型主體)")
    print(f"   2. fonts.css (CSS 範例)")
    print()

if __name__ == '__main__':
    main()
