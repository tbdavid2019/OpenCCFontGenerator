import os
from os import path
import re
import tempfile

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

from .font import build_font, detect_output_extension


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


def detect_variable_axis_bounds(input_file):
    font = TTFont(input_file)
    try:
        if "fvar" not in font:
            available_tables = ", ".join(font.keys())
            raise ValueError(
                "來源字型不是 variable font，找不到 fvar table。"
                "這和副檔名無關；.ttf 與 .otf 都可以是 variable font，前提是字型內真的包含變體軸。"
                f"目前偵測到的 tables: {available_tables}"
            )
        return {
            axis.axisTag: (axis.minValue, axis.defaultValue, axis.maxValue)
            for axis in font["fvar"].axes
        }
    finally:
        font.close()


def detect_variable_axes(input_file):
    bounds = detect_variable_axis_bounds(input_file)
    return {tag: vals[1] for tag, vals in bounds.items()}


def instantiate_variable_font(input_file, output_file, axis_values):
    font = TTFont(input_file)
    try:
        if "fvar" not in font:
            raise ValueError("來源字型不是 variable font，找不到 fvar table。")
        has_stat = "STAT" in font
        instance = instantiateVariableFont(font, axis_values, inplace=False, updateFontNames=has_stat)
        try:
            if "CFF2" in instance:
                from fontTools.cffLib.CFF2ToCFF import convertCFF2ToCFF
                convertCFF2ToCFF(instance)
            instance.save(output_file)
        finally:
            instance.close()
    finally:
        font.close()


def find_fallback_for_weight(fallback_dir, fallback_prefix, weight_name):
    safe_prefix = sanitize_filename_part(fallback_prefix or "")
    base_dir = os.path.abspath(fallback_dir)
    candidates = [
        path.join(base_dir, f"{safe_prefix}-{weight_name}.ttf"),
        path.join(base_dir, f"{safe_prefix}-{weight_name}.otf"),
    ]
    for candidate in candidates:
        resolved = os.path.abspath(candidate)
        if os.path.commonpath([resolved, base_dir]) != base_dir:
            continue
        if path.isfile(resolved):
            return resolved
    raise FileNotFoundError(f"找不到對應權重的 fallback 字型：{safe_prefix}-{weight_name}.ttf/.otf")


def sanitize_filename_part(value):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value or "")
    cleaned = re.sub(r"\.{2,}", "_", cleaned).strip("._")
    return cleaned or "Output"


def _sanitize_output_stem(value, max_bytes=120):
    cleaned = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "_", value or "")
    cleaned = re.sub(r"\.{2,}", "_", cleaned).strip("._")
    if not cleaned:
        return "Output"
    encoded = cleaned.encode("utf-8")
    if len(encoded) > max_bytes:
        cleaned = encoded[:max_bytes].decode("utf-8", errors="ignore").rstrip("._")
    return cleaned or "Output"


def build_variable_cjk_family(
    input_file,
    output_dir,
    fallback_dir,
    fallback_prefix="NotoSansTC",
    config="s2t",
    output_woff2=False,
    family_name_prefix=None,
    weights=None,
    kobo_mode=False,
):
    axis_bounds = detect_variable_axis_bounds(input_file)
    if "wght" not in axis_bounds:
        raise ValueError("來源 variable font 不包含 wght 軸，無法建立多權重 family。")

    min_wght, _, max_wght = axis_bounds["wght"]
    axes = {tag: vals[1] for tag, vals in axis_bounds.items()}

    if weights is None:
        selected_presets = [
            preset for preset in WEIGHT_PRESETS
            if min_wght <= preset[1] <= max_wght
        ]
        if not selected_presets:
            raise ValueError(f"來源可變字型的 wght 軸範圍（{min_wght:g}–{max_wght:g}）未涵蓋任何預設字重。")
    else:
        selected_presets = [preset for preset in WEIGHT_PRESETS if preset[0] in weights]
        if not selected_presets:
            raise ValueError("沒有可用的權重預設。")
        out_of_range = [
            f"{preset[0]} ({preset[1]})"
            for preset in selected_presets
            if not (min_wght <= preset[1] <= max_wght)
        ]
        if out_of_range:
            raise ValueError(
                f"來源可變字型的 wght 軸範圍為 {min_wght:g}–{max_wght:g}，不支援字重：{', '.join(out_of_range)}"
            )

    os.makedirs(output_dir, exist_ok=True)
    out_ext = detect_output_extension(input_file)
    base_filename = _sanitize_output_stem(path.splitext(path.basename(input_file))[0])
    results = []

    for display_name, weight_value, fallback_weight_name in selected_presets:
        fallback_font = find_fallback_for_weight(fallback_dir, fallback_prefix, fallback_weight_name)

        axis_values = dict(axes)
        axis_values["wght"] = weight_value

        with tempfile.NamedTemporaryFile(suffix=f"-{display_name}{out_ext}", delete=False) as temp_file:
            temp_instance_path = temp_file.name
        try:
            instantiate_variable_font(input_file, temp_instance_path, axis_values)

            output_filename = f"{base_filename}_{display_name}_TC{out_ext}"
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
                kobo_mode=kobo_mode,
            )
            results.append({
                "weight": display_name,
                "weight_value": weight_value,
                "fallback_font": fallback_font,
                "output_file": output_file,
                "woff2_file": path.join(output_dir, f"{base_filename}_{display_name}_TC.woff2") if output_woff2 else None,
            })
        finally:
            if path.exists(temp_instance_path):
                os.remove(temp_instance_path)

    return results
