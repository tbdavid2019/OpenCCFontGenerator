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


def prompt_existing_file(message, optional=False):
    """Prompt until the user enters a path to an existing file."""
    while True:
        msg = f"{message} (直接按 Enter 跳過)" if optional else message
        value = input(f"{msg}: ").strip()
        if optional and not value:
            return None
        if os.path.isfile(value):
            return value
        print(f"  ❌ 找不到檔案：{value}，請確認路徑後再試。")


def prompt_float_optional(message):
    """Prompt for a float. Returns None on empty input."""
    while True:
        raw = input(f"{message} (直接按 Enter 保留原設定): ").strip()
        if raw == "":
            return None
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
    input_file = prompt_existing_file("請輸入來源字型路徑（.ttf / .otf / .ttc / .woff2）")
    print()

    # --- Step 3: Output path ---
    print("【步驟 3】輸出字型路徑 / Output Font Path")
    base, ext = os.path.splitext(input_file)
    default_output = f"{base}_TC{ext}"
    raw_output = input(f"請輸入輸出路徑 [預設: {default_output}]: ").strip()
    output_file = raw_output if raw_output else default_output
    print(f"  ✓ 輸出路徑已設定為：{output_file}\n")

    # --- Step 4: Font Name (Replaces Name Header JSON) ---
    print("【步驟 4】設定新字型名稱 / New Font Name")
    print("  說明: 留空則系統會自動讀取原字型名稱並標註 'TC'（或依據轉換模式標註）。")
    print("        （若需進階設定，也可直接輸入 .json 檔案路徑）")
    raw_name_input = input("請輸入新名稱 (直接按 Enter 留空): ").strip()
    print()

    font_name = None
    name_header_file = None

    if raw_name_input.endswith(".json"):
        if os.path.isfile(raw_name_input):
            name_header_file = raw_name_input
            print(f"  ✓ 將使用 JSON 設定檔: {name_header_file}\n")
        else:
            print(f"  ❌ 找不到檔案：{raw_name_input}，請確認後再試。")
            sys.exit(1)
    elif raw_name_input:
        font_name = raw_name_input

    # --- Step 5: Font version ---
    print("【步驟 5】字型版本號碼 / Font Version")
    font_version = prompt_float_optional("請輸入新版本號碼")
    if font_version is None:
        print("  ✓ 將保留原始字型的版本號設定。\n")
    else:
        print(f"  ✓ 版本號碼將更新為：{font_version}\n")

    # --- Step 6: TTC index (optional) ---
    ttc_index = None
    if str(input_file).lower().endswith('.ttc'):
        print("【步驟 6】TTC 索引（選用）/ TTC Index (optional)")
        ttc_index = prompt_int_optional("此為 .ttc 檔案，請輸入轉換目標的字型索引 (自 0 開始)")
        print()

    # --- Step 7: OpenCC Configuration ---
    print("【步驟 7】OpenCC 轉換標準 / OpenCC Configuration")
    print("  1. s2t  - 簡體轉繁體（預設）")
    print("  2. twp  - 簡體轉繁體（包含台灣慣用語轉換，例如：软件 -> 軟體）")
    print("  3. s2tw - 簡體轉台灣正體")
    print("  4. s2hk - 簡體轉香港繁體")
    print("  5. t2s  - 繁體轉簡體")
    print()
    config_map = {"1": "s2t", "2": "twp", "3": "s2tw", "4": "s2hk", "5": "t2s"}
    config_choice = input("請輸入選項 (1/2/3/4/5) [預設: 1]: ").strip()
    config = config_map.get(config_choice, "s2t")
    print(f"  ✓ 已選擇：{config}\n")

    # --- Step 8: Fallback Font ---
    print("【步驟 8】缺字補全（備用字型）/ Fallback Font")
    print("  說明: 如果目標字元在來源字型中不存在，可以從另一個字型（備用字型）中提取並補入。")
    fallback_font = prompt_existing_file("請輸入備用字型路徑", optional=True)
    merge_mode = "opencc"
    fill_charset = "none"
    if fallback_font:
        print(f"  ✓ 已設定備用字型：{fallback_font}\n")
        print("【步驟 8-0】主動補字集 / Fill Charset")
        print("  1. none         - 不先主動補字（預設）")
        print("  2. hant-common  - 先從 fallback 補常用漢字/繁中字集")
        print("  說明: 若來源字型繁中字區不完整，建議選 2。")
        fill_charset_choice = input("請輸入選項 (1/2) [預設: 1]: ").strip()
        fill_charset = {"1": "none", "2": "hant-common"}.get(fill_charset_choice, "none")
        print(f"  ✓ 已選擇主動補字集：{fill_charset}\n")
        print("【步驟 8-1】補字模式 / Merge Mode")
        print("  1. opencc     - 只補 OpenCC 轉換規則需要的目標字（預設）")
        print("  2. universal  - 保留來源字庫，並補入 fallback 中所有缺少的 codepoint")
        print("  說明: universal 較接近通用型 merge font，但大型字型更容易超過 glyph 上限。")
        merge_mode_choice = input("請輸入選項 (1/2) [預設: 1]: ").strip()
        merge_mode = {"1": "opencc", "2": "universal"}.get(merge_mode_choice, "opencc")
        print(f"  ✓ 已選擇補字模式：{merge_mode}\n")
    else:
        print("  ✓ 未設定備用字型。\n")

    # --- Step 9: Force Vertical ---
    print("【步驟 9】強制直排模式 / Force Vertical Mode")
    print("  說明: 將標點符號替換為直排形式，適合電子書字型。")
    force_vertical = prompt_yes_no("是否開啟強制直排模式？", default=False)
    print()

    # --- Step 10: Output WOFF2 ---
    print("【步驟 10】額外輸出格式 / Additional Formats")
    print("  說明: 除了預設的 TTF 之外，是否同時生成壓縮率較高的 WOFF2 格式？")
    output_woff2 = prompt_yes_no("是否同時輸出 WOFF2 格式？", default=False)
    print()

    # --- Summary ---
    print("-" * 50)
    print("  設定摘要 / Summary")
    print("-" * 50)
    print(f"  來源字型:     {input_file}")
    print(f"  輸出路徑:     {output_file}")
    if name_header_file:
        print(f"  名稱標頭:     {name_header_file} (JSON模式)")
    else:
        print(f"  新字型名稱:   {font_name if font_name else '自動產生'}")
    print(f"  版本號碼:     {font_version if font_version is not None else '保留原字型設定'}")
    if str(input_file).lower().endswith('.ttc'):
        print(f"  TTC 索引:    {ttc_index if ttc_index is not None else '無'}")
    print(f"  轉換標準:     {config}")
    print(f"  備用字型:     {fallback_font if fallback_font else '無'}")
    if fallback_font:
        print(f"  主動補字集:   {fill_charset}")
        print(f"  補字模式:     {merge_mode}")
    print(f"  排除標點:     {'是' if no_punc else '否'}")
    print(f"  強制直排:     {'是' if force_vertical else '否'}")
    print(f"  輸出 WOFF2:   {'是' if output_woff2 else '否'}")
    print("-" * 50)
    if merge_mode == "universal":
        print("  注意: universal 模式會盡量保留原始字庫並合併 fallback 缺字。")
        print("        若字型太大，再加上 OpenCC 規則後可能超過 OpenType glyph 上限。")
    else:
        print("  注意: 輸出的 _TC 字型是為 OpenCC 詞彙級轉換優化的 subset font。")
        print("        為了在 OpenType glyph 上限內容納 GSUB 規則，程式可能不會完整保留原始字庫。")
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
            config=config,
            fallback_font=fallback_font,
            merge_mode=merge_mode,
            fill_charset=fill_charset,
            no_punc=no_punc,
            force_vertical=force_vertical,
            font_name=font_name,
            output_woff2=output_woff2,
        )
    except Exception as e:
        print(f"❌ 生成失敗：{e}")
        sys.exit(1)

    print(f"✅ 完成！字型已儲存至：{output_file}")
    print()


if __name__ == '__main__':
    main()
