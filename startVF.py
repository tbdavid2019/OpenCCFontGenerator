#!/usr/bin/env python3
"""
startVF.py — Variable Font CJK Family Builder Wizard
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from OpenCCFontGenerator.vf_family import WEIGHT_PRESETS, build_variable_cjk_family, detect_variable_axes


def prompt_existing_file(message):
    while True:
        value = input(f"{message}: ").strip()
        if os.path.isfile(value):
            return value
        print(f"  ❌ 找不到檔案：{value}")


def prompt_existing_dir(message):
    while True:
        value = input(f"{message}: ").strip()
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
    print("  Variable CJK Family Builder / 可變字型 CJK Family 建立精靈")
    print("=" * 64)
    print()
    print("  這個流程不會生成單一『真正的 variable CJK font』。")
    print("  它會把 variable font 展開成多個權重，再與對應的 CJK fallback 合成。")
    print("  注意：這裡輸入的來源檔案必須是真正的 variable font。")
    print("  副檔名可以是 .ttf 或 .otf，但字型內必須包含 fvar 軸。")
    print()

    print("【步驟 1】Variable 字型路徑 / Variable Font Path")
    input_file = prompt_existing_file("請輸入 variable font 路徑（例如 MonoLisaVariableNormal.ttf）")
    axes = detect_variable_axes(input_file)
    print(f"  ✓ 偵測到軸：{', '.join(f'{k}={v}' for k, v in axes.items())}\n")

    print("【步驟 2】輸出資料夾 / Output Directory")
    default_output_dir = os.path.join(os.path.dirname(input_file), f"{os.path.splitext(os.path.basename(input_file))[0]}_TC_Family")
    raw_output_dir = input(f"請輸入輸出資料夾 [預設: {default_output_dir}]: ").strip()
    output_dir = raw_output_dir or default_output_dir
    print(f"  ✓ 輸出資料夾：{output_dir}\n")

    print("【步驟 3】Fallback 字型資料夾 / Fallback Directory")
    fallback_dir = prompt_existing_dir("請輸入 fallback 字型所在資料夾（例如 NotoSansTC 那一整包）")
    print()

    print("【步驟 4】Fallback 字型前綴 / Fallback Prefix")
    fallback_prefix = input("請輸入 fallback 檔名前綴 [預設: NotoSansTC]: ").strip() or "NotoSansTC"
    print(f"  ✓ 將使用：{fallback_prefix}-Regular.ttf / -Bold.ttf ...\n")

    print("【步驟 5】OpenCC 轉換標準 / OpenCC Configuration")
    print("  1. s2t  - 簡體轉繁體（預設）")
    print("  2. twp  - 簡體轉繁體（台灣慣用語）")
    print("  3. s2tw - 簡體轉台灣正體")
    print("  4. s2hk - 簡體轉香港繁體")
    print("  5. t2s  - 繁體轉簡體")
    config_map = {"1": "s2t", "2": "twp", "3": "s2tw", "4": "s2hk", "5": "t2s"}
    config = config_map.get(input("請輸入選項 (1/2/3/4/5) [預設: 1]: ").strip(), "s2t")
    print(f"  ✓ 已選擇：{config}\n")

    print("【步驟 6】Family 名稱前綴 / Family Name Prefix")
    family_name_prefix = input("請輸入輸出 family 名稱前綴 (直接 Enter 使用原 variable 字型名稱): ").strip() or None
    print()

    print("【步驟 7】是否額外輸出 WOFF2 / Additional WOFF2 Output")
    output_woff2 = prompt_yes_no("是否同時輸出 WOFF2？", default=False)
    print()

    print("-" * 56)
    print("  將建立的權重 / Planned Weights")
    print("-" * 56)
    for display_name, weight_value, fallback_weight_name in WEIGHT_PRESETS:
        print(f"  {display_name:<10} wght={weight_value:<3}  fallback={fallback_prefix}-{fallback_weight_name}.ttf")
    print("-" * 56)
    print("  說明:")
    print("  1. 拉丁字母與數字會來自 variable font 的對應權重實例。")
    print("  2. 中文會來自對應權重的 fallback 字型。")
    print("  3. 這會得到一整套 static family，不是單一可變 CJK font。")
    print()

    if not prompt_yes_no("確認開始建立整套 family？", default=True):
        sys.exit(0)

    print()
    print("⏳ 正在建立多權重 CJK family，請稍候...")
    print()

    try:
        results = build_variable_cjk_family(
            input_file=input_file,
            output_dir=output_dir,
            fallback_dir=fallback_dir,
            fallback_prefix=fallback_prefix,
            config=config,
            output_woff2=output_woff2,
            family_name_prefix=family_name_prefix,
        )
    except Exception as e:
        print(f"❌ 建立失敗：{e}")
        sys.exit(1)

    print("✅ 完成！已輸出以下字型：")
    for item in results:
        print(f"  - {item['weight']}: {item['output_file']}")
    print()


if __name__ == '__main__':
    main()
