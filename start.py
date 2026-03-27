#!/usr/bin/env python3
"""
start.py — 互動式精靈啟動器 / Interactive Wizard for OpenCC Font Generator

執行方式 / Usage:
    python start.py
"""

import os
import sys

# Allow running from project root without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from OpenCCFontGenerator.font import build_font


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

def prompt_required(message, error="此欄位不可為空，請重新輸入。"):
    """Prompt until a non-empty value is given."""
    while True:
        value = input(f"{message}: ").strip()
        if value:
            return value
        print(f"  ❌ {error}")


def prompt_existing_file(message):
    """Prompt until the user enters a path to an existing file."""
    while True:
        value = prompt_required(message)
        if os.path.isfile(value):
            return value
        print(f"  ❌ 找不到檔案：{value}，請確認路徑後再試。")


def prompt_float(message, default=None):
    """Prompt for a float. Returns default on empty input if provided."""
    while True:
        hint = f" (預設: {default})" if default is not None else ""
        raw = input(f"{message}{hint}: ").strip()
        if raw == "" and default is not None:
            return float(default)
        try:
            return float(raw)
        except ValueError:
            print("  ❌ 請輸入有效的數字（例如: 1.0）。")


def prompt_int_optional(message):
    """Prompt for an optional integer. Returns None if empty."""
    while True:
        raw = input(f"{message} (直接按 Enter 跳過): ").strip()
        if raw == "":
            return None
        try:
            return int(raw)
        except ValueError:
            print("  ❌ 請輸入有效的整數。")


def prompt_yes_no(message, default=False):
    """Prompt for a yes/no answer. Returns bool."""
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
    print("=" * 50)
    print("  OpenCC 字型生成器 / OpenCC Font Generator")
    print("=" * 50)
    print()

    # --- Step 1: Conversion mode ---
    print("【步驟 1】選擇轉換模式 / Conversion Mode")
    print("  1. 包含標點符號轉換（預設）")
    print("  2. 排除標點符號轉換")
    print()
    no_punc = False
    while True:
        choice = input("請輸入選項 (1/2) [預設: 1]: ").strip()
        if choice in ("", "1"):
            no_punc = False
            print("  ✓ 已選擇：包含標點符號轉換\n")
            break
        elif choice == "2":
            no_punc = True
            print("  ✓ 已選擇：排除標點符號轉換\n")
            break
        else:
            print("  ❌ 請輸入 1 或 2。")

    # --- Step 2: Source font ---
    print("【步驟 2】來源字型路徑 / Source Font Path")
    input_file = prompt_existing_file("請輸入來源字型路徑（.ttf / .otf / .ttc）")
    print()

    # --- Step 3: Output path ---
    print("【步驟 3】輸出字型路徑 / Output Font Path")
    output_file = prompt_required("請輸入輸出字型路徑（例如: output.ttf）")
    print()

    # --- Step 4: Name header ---
    print("【步驟 4】名稱標頭設定檔 / Name Header JSON File")
    name_header_file = prompt_existing_file("請輸入名稱標頭 JSON 檔案路徑")
    print()

    # --- Step 5: Font version ---
    print("【步驟 5】字型版本號碼 / Font Version")
    font_version = prompt_float("請輸入版本號碼", default=1.0)
    print()

    # --- Step 6: TTC index (optional) ---
    print("【步驟 6】TTC 索引（選用）/ TTC Index (optional)")
    ttc_index = prompt_int_optional("若來源為 .ttc 檔案，請輸入字型索引")
    print()

    # --- Step 7: Taiwanese phrases ---
    print("【步驟 7】台灣慣用語轉換 / Taiwanese Phrases")
    twp = prompt_yes_no("是否包含台灣慣用語轉換？", default=False)
    print()

    # --- Step 8: Force Vertical ---
    print("【步驟 8】強制直排模式 / Force Vertical Mode")
    print("  說明: 將標點符號替換為直排形式，適合電子書字型。")
    force_vertical = prompt_yes_no("是否開啟強制直排模式？", default=False)
    print()

    # --- Summary ---
    print("-" * 50)
    print("  設定摘要 / Summary")
    print("-" * 50)
    print(f"  來源字型:     {input_file}")
    print(f"  輸出路徑:     {output_file}")
    print(f"  名稱標頭:     {name_header_file}")
    print(f"  版本號碼:     {font_version}")
    print(f"  TTC 索引:    {ttc_index if ttc_index is not None else '無'}")
    print(f"  台灣慣用語:   {'是' if twp else '否'}")
    print(f"  排除標點:     {'是' if no_punc else '否'}")
    print(f"  強制直排:     {'是' if force_vertical else '否'}")
    print("-" * 50)
    print()

    confirm = prompt_yes_no("確認以上設定並開始生成？", default=True)
    if not confirm:
        print("已取消。")
        sys.exit(0)

    print()
    print("⏳ 正在生成字型，請稍候...")
    print()

    try:
        build_font(
            input_file=input_file,
            output_file=output_file,
            name_header_file=name_header_file,
            font_version=font_version,
            ttc_index=ttc_index,
            twp=twp,
            no_punc=no_punc,
            force_vertical=force_vertical,
        )
    except Exception as e:
        print(f"❌ 生成失敗：{e}")
        sys.exit(1)

    print(f"✅ 完成！字型已儲存至：{output_file}")
    print()


if __name__ == '__main__':
    main()
