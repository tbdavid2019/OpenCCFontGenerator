import os
from os import path
import re
import tempfile

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

from .font import build_font


WEIGHT_PRESETS = [
    ("Thin", 100, "Thin"),
    ("ExtraLight", 200, "ExtraLight"),
    ("Light", 300, "Light"),
    ("Regular", 400, "Regular"),
    ("Medium", 500, "Medium"),
    ("SemiBold", 600, "SemiBold"),
    ("Bold", 700, "Bold"),
    ("ExtraBold", 800, "ExtraBold"),
    ("Black", 900, "Black"),
]


def detect_variable_axes(input_file):
    font = TTFont(input_file)
    if "fvar" not in font:
        available_tables = ", ".join(font.keys())
        raise ValueError(
            "來源字型不是 variable font，找不到 fvar table。"
            "這和副檔名無關；.ttf 與 .otf 都可以是 variable font，前提是字型內真的包含變體軸。"
            f"目前偵測到的 tables: {available_tables}"
        )
    return {axis.axisTag: axis.defaultValue for axis in font["fvar"].axes}


def instantiate_variable_font(input_file, output_file, axis_values):
    font = TTFont(input_file)
    if "fvar" not in font:
        raise ValueError("來源字型不是 variable font，找不到 fvar table。")
    instance = instantiateVariableFont(font, axis_values, inplace=False, updateFontNames=True)
    instance.save(output_file)


def find_fallback_for_weight(fallback_dir, fallback_prefix, weight_name):
    candidates = [
        path.join(fallback_dir, f"{fallback_prefix}-{weight_name}.ttf"),
        path.join(fallback_dir, f"{fallback_prefix}-{weight_name}.otf"),
    ]
    for candidate in candidates:
        if path.isfile(candidate):
            return candidate
    raise FileNotFoundError(f"找不到對應權重的 fallback 字型：{fallback_prefix}-{weight_name}.ttf/.otf")


def sanitize_filename_part(value):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_") or "Output"


def build_variable_cjk_family(
    input_file,
    output_dir,
    fallback_dir,
    fallback_prefix="NotoSansTC",
    config="s2t",
    output_woff2=False,
    family_name_prefix=None,
    weights=None,
):
    axes = detect_variable_axes(input_file)
    if "wght" not in axes:
        raise ValueError("來源 variable font 不包含 wght 軸，無法建立多權重 family。")

    os.makedirs(output_dir, exist_ok=True)
    selected_presets = WEIGHT_PRESETS if weights is None else [preset for preset in WEIGHT_PRESETS if preset[0] in weights]
    if not selected_presets:
        raise ValueError("沒有可用的權重預設。")

    base_filename = sanitize_filename_part(path.splitext(path.basename(input_file))[0])
    results = []

    for display_name, weight_value, fallback_weight_name in selected_presets:
        fallback_font = find_fallback_for_weight(fallback_dir, fallback_prefix, fallback_weight_name)

        axis_values = dict(axes)
        axis_values["wght"] = weight_value

        with tempfile.NamedTemporaryFile(suffix=f"-{display_name}.ttf", delete=False) as temp_file:
            temp_instance_path = temp_file.name
        try:
            instantiate_variable_font(input_file, temp_instance_path, axis_values)

            output_filename = f"{base_filename}_{display_name}_TC.ttf"
            output_file = path.join(output_dir, output_filename)

            build_font(
                input_file=temp_instance_path,
                output_file=output_file,
                config=config,
                fallback_font=fallback_font,
                merge_mode="universal",
                fill_charset="hant-common",
                output_woff2=output_woff2,
                font_name=f"{family_name_prefix} {display_name}" if family_name_prefix else None,
            )
            results.append({
                "weight": display_name,
                "weight_value": weight_value,
                "fallback_font": fallback_font,
                "output_file": output_file,
            })
        finally:
            if path.exists(temp_instance_path):
                os.remove(temp_instance_path)

    return results
