#!/usr/bin/env python3
"""
start90.py — 互動式精靈啟動器 (90度旋轉) / Interactive Wizard for 90-Degree Rotation
"""

import os
import sys

# Allow running from project root without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from OpenCCFontGenerator.run90 import process_rotation

# ---------------------------------------------------------------------------
# Prompt helpers (Copy from start.py logic)
# ---------------------------------------------------------------------------

def prompt_required(message, error="此欄位不可為空，請重新輸入。"):
    while True:
        value = input(f"{message}: ").strip()
        if value:
            return value
        print(f"  ❌ {error}")

def prompt_existing_file(message, optional=False):
    while True:
        msg = f"{message} (直接按 Enter 跳過)" if optional else message
        value = input(f"{msg}: ").strip()
        if optional and not value:
            return None
        if os.path.isfile(value):
            return value
        print(f"  ❌ 找不到檔案：{value}，請確認路徑後再試。")

def prompt_int_optional(message, default=None):
    while True:
        raw = input(f"{message} [預設: {default}]: ").strip()
        if raw == "":
            return default
        try:
            return int(raw)
        except ValueError:
            print("  ❌ 請輸入有效的整數。")

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
    print("  OpenCC 90度旋轉精靈 / 90-Degree Rotation Wizard")
    print("  (用於水平電子書偽直排模式)")
    print("=" * 60)
    print()

    # --- Step 1: Source font ---
    print("【步驟 1】來源字型路徑 / Source Font Path")
    input_file = prompt_existing_file("請輸入字型路徑（建議輸入處理好的 _TC.ttf）")
    print()

    # --- Step 2: Output path ---
    print("【步驟 2】輸出路徑 / Output Path")
    base, ext = os.path.splitext(input_file)
    default_output = f"{base}_Rotated90{ext}"
    raw_output = input(f"請輸入輸出路徑 [預設: {default_output}]: ").strip()
    output_file = raw_output if raw_output else default_output
    print(f"  ✓ 輸出路徑已設定為：{output_file}\n")

    # --- Step 3: Rotation Direction ---
    print("【步驟 3】旋轉方向 / Rotation Direction")
    print("  1. 逆時針 90 度 (Counter-clockwise) - [預設]")
    print("  2. 順時針 90 度 (Clockwise)")
    direction_choice = input("請選擇方向 (1/2) [預設: 1]: ").strip()
    direction = 'cw' if direction_choice == "2" else 'ccw'
    print(f"  ✓ 已選擇：{'順時針' if direction == 'cw' else '逆時針'}\n")

    # --- Step 4: Rotation Center ---
    print("【步驟 4】旋轉中心設定 / Rotation Center")
    print("  說明: 通常中文字型以 (500, 500) 為幾何中心。")
    center_x = prompt_int_optional("請輸入中心 X 座標", default=500)
    center_y = prompt_int_optional("請輸入中心 Y 座標", default=500)
    print()

    # --- Step 5: Rotate Scope ---
    print("【步驟 5】旋轉範圍 / Rotation Scope")
    print("  1. 全部字元（包含中英數、標點符號全部躺平）")
    print("  2. 僅限漢字（英文與數字保持原樣，中文字躺平）")
    rotate_choice = input("請選擇範圍 (1/2) [預設: 1]: ").strip()
    rotate_all = (rotate_choice != "2")
    print(f"  ✓ 已選擇：{'全部字元' if rotate_all else '僅限漢字'}\n")

    # --- Step 6: TTC index (optional) ---
    ttc_index = None
    if str(input_file).lower().endswith('.ttc'):
        print("【步驟 6】TTC 索引（選用）/ TTC Index (optional)")
        ttc_index = prompt_int_optional("請輸入字型索引 (自 0 開始)", default=0)
        print()

    # --- Summary ---
    print("-" * 50)
    print("  設定摘要 / Summary")
    print("-" * 50)
    print(f"  來源檔案:     {input_file}")
    print(f"  輸出檔案:     {output_file}")
    print(f"  旋轉方向:     {'順時針 90°' if direction == 'cw' else '逆時針 90°'}")
    print(f"  旋轉中心:     ({center_x}, {center_y})")
    print(f"  旋轉範圍:     {'全部字元' if rotate_all else '僅中文字'}")
    if ttc_index is not None:
        print(f"  TTC 索引:     {ttc_index}")
    print("-" * 50)
    print()

    confirm = prompt_yes_no("確認並開始進行幾何旋轉？", default=True)
    if not confirm:
        sys.exit(0)

    print()
    print("⏳ 正在進行幾何旋轉運算，請稍候...")
    print()

    try:
        process_rotation(
            input_path=input_file,
            output_path=output_file,
            ttc_index=ttc_index,
            center_x=center_x,
            center_y=center_y,
            rotate_all=rotate_all,
            direction=direction
        )
    except Exception as e:
        print(f"❌ 旋轉失敗：{e}")
        sys.exit(1)

    print(f"✅ 完成！旋轉後的字型已儲存至：{output_file}")
    print()

if __name__ == '__main__':
    main()
