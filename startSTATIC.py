#!/usr/bin/env python3
"""
startSTATIC.py — Static Font Family Batch Builder Wizard
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from OpenCCFontGenerator.static_family import build_static_cjk_family, collect_source_fonts


def prompt_existing_path(message):
    while True:
        value = input(f"{message}: ").strip()
        if os.path.isfile(value) or os.path.isdir(value):
            return value
        print(f"  ❌ 找不到檔案或資料夾：{value}")


def prompt_existing_dir(message, optional=False):
    while True:
        msg = f"{message} (直接按 Enter 跳過)" if optional else message
        value = input(f"{msg}: ").strip()
        if optional and not value:
            return None
        if os.path.isdir(value):
            return value
        print(f"  ❌ 找不到資料夾：{value}")


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


def main():
    print()
    print("=" * 64)
    print("  Static Font Family Builder / 靜態字型 Family 批次處理精靈")
    print("=" * 64)
    print()
    print("  適用對象：非 variable font。")
    print("  可以輸入單一字型檔，或一整個包含多字重的資料夾。")
    print()

    print("【步驟 1】來源字型檔或資料夾 / Source Font File or Directory")
    input_path = prompt_existing_path("請輸入來源字型檔或資料夾")
    source_files = collect_source_fonts(input_path)
    print(f"  ✓ 找到 {len(source_files)} 個待處理字型\n")

    print("【步驟 2】輸出資料夾 / Output Directory")
    if os.path.isfile(input_path):
        default_output_dir = os.path.join(os.path.dirname(input_path), f"{os.path.splitext(os.path.basename(input_path))[0]}_TC_Family")
    else:
        default_output_dir = os.path.join(input_path, "_TC_Family")
    raw_output_dir = input(f"請輸入輸出資料夾 [預設: {default_output_dir}]: ").strip()
    output_dir = raw_output_dir or default_output_dir
    print(f"  ✓ 輸出資料夾：{output_dir}\n")

    print("【步驟 3】Fallback 字型資料夾 / Fallback Directory")
    print("  說明: 可留空，若來源字型本身已有完整中文字可不提供。")
    fallback_dir = prompt_existing_dir("請輸入 fallback 字型資料夾", optional=True)
    fallback_prefix = None
    merge_mode = "opencc"
    if fallback_dir:
        fallback_prefix = input("請輸入 fallback 檔名前綴 [例如: NotoSansTC，可留空]: ").strip() or None
        print("【步驟 3-1】補字模式 / Merge Mode")
        print("  1. opencc     - 只補 OpenCC 轉換規則需要的目標字")
        print("  2. universal  - 保留來源字庫，並補入 fallback 中所有缺少的 codepoint（預設）")
        merge_mode = {"1": "opencc", "2": "universal"}.get(input("請輸入選項 (1/2) [預設: 2]: ").strip(), "universal")
        print()
    else:
        print("  ✓ 未設定 fallback 字型資料夾。\n")

    print("【步驟 4】OpenCC 轉換標準 / OpenCC Configuration")
    print("  1. s2t  - 簡體轉繁體（預設）")
    print("  2. twp  - 簡體轉繁體（台灣慣用語）")
    print("  3. s2tw - 簡體轉台灣正體")
    print("  4. s2hk - 簡體轉香港繁體")
    print("  5. t2s  - 繁體轉簡體")
    config_map = {"1": "s2t", "2": "twp", "3": "s2tw", "4": "s2hk", "5": "t2s"}
    config = config_map.get(input("請輸入選項 (1/2/3/4/5) [預設: 1]: ").strip(), "s2t")
    print(f"  ✓ 已選擇：{config}\n")

    print("【步驟 5】其他選項 / Additional Options")
    no_punc = prompt_yes_no("是否排除標點符號轉換？", default=False)
    force_vertical = prompt_yes_no("是否開啟強制直排模式？", default=False)
    output_woff2 = prompt_yes_no("是否同時輸出 WOFF2？", default=False)
    print()

    print("【步驟 6】Family 名稱前綴 / Family Name Prefix")
    family_name_prefix = input("請輸入輸出 family 名稱前綴 (直接 Enter 保留原始命名): ").strip() or None
    print()

    print("-" * 56)
    print("  設定摘要 / Summary")
    print("-" * 56)
    print(f"  來源:         {input_path}")
    print(f"  待處理數量:   {len(source_files)}")
    print(f"  輸出資料夾:   {output_dir}")
    print(f"  Fallback 資料夾: {fallback_dir if fallback_dir else '無'}")
    print(f"  Fallback 前綴: {fallback_prefix if fallback_prefix else '無'}")
    print(f"  補字模式:     {merge_mode if fallback_dir else '無'}")
    print(f"  轉換標準:     {config}")
    print(f"  排除標點:     {'是' if no_punc else '否'}")
    print(f"  強制直排:     {'是' if force_vertical else '否'}")
    print(f"  輸出 WOFF2:   {'是' if output_woff2 else '否'}")
    print(f"  Family 名稱:  {family_name_prefix if family_name_prefix else '保留原始命名'}")
    print("-" * 56)
    print()

    if not prompt_yes_no("確認開始批次處理？", default=True):
        sys.exit(0)

    print()
    print("⏳ 正在批次處理靜態字型 family，請稍候...")
    print()

    try:
        results = build_static_cjk_family(
            input_path=input_path,
            output_dir=output_dir,
            fallback_dir=fallback_dir,
            fallback_prefix=fallback_prefix,
            config=config,
            merge_mode=merge_mode,
            no_punc=no_punc,
            force_vertical=force_vertical,
            output_woff2=output_woff2,
            family_name_prefix=family_name_prefix,
        )
    except Exception as e:
        print(f"❌ 處理失敗：{e}")
        sys.exit(1)

    print("✅ 完成！已輸出以下字型：")
    for item in results:
        print(f"  - {item['weight']}: {item['output_file']}")
    print()


if __name__ == '__main__':
    main()
