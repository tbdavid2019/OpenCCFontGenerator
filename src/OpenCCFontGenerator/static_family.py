import os
from os import path
import re

from .font import build_font


SUPPORTED_EXTENSIONS = ('.ttf', '.otf', '.ttc', '.woff2')

WEIGHT_ALIASES = {
    "Thin": ("thin",),
    "ExtraLight": ("extralight", "extra-light", "ultralight", "ultra-light"),
    "Light": ("light",),
    "Regular": ("regular", "normal", "book", "roman"),
    "Medium": ("medium",),
    "SemiBold": ("semibold", "semi-bold", "demibold", "demi-bold"),
    "Bold": ("bold",),
    "ExtraBold": ("extrabold", "extra-bold", "ultrabold", "ultra-bold", "heavy"),
    "Black": ("black",),
}


def sanitize_filename_part(value):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_") or "Output"


def is_supported_font_file(filename):
    return filename.lower().endswith(SUPPORTED_EXTENSIONS)


def collect_source_fonts(input_path):
    if path.isfile(input_path):
        if not is_supported_font_file(input_path):
            raise ValueError("來源檔案不是支援的字型格式。")
        return [input_path]

    if not path.isdir(input_path):
        raise FileNotFoundError(f"找不到來源檔案或資料夾：{input_path}")

    files = [
        path.join(input_path, filename)
        for filename in sorted(os.listdir(input_path))
        if is_supported_font_file(filename)
    ]
    if not files:
        raise ValueError("來源資料夾中沒有找到支援的字型檔。")
    return files


def detect_weight_from_filename(filename):
    normalized = re.sub(r"[^a-z0-9]+", "", path.basename(filename).lower())
    for canonical_name, aliases in WEIGHT_ALIASES.items():
        for alias in aliases:
            if re.sub(r"[^a-z0-9]+", "", alias) in normalized:
                return canonical_name
    return "Regular"


def collect_fallback_candidates(fallback_dir, fallback_prefix=None):
    files = [
        path.join(fallback_dir, filename)
        for filename in sorted(os.listdir(fallback_dir))
        if is_supported_font_file(filename)
    ]
    if fallback_prefix:
        filtered = [
            file_path for file_path in files
            if path.basename(file_path).lower().startswith(fallback_prefix.lower())
        ]
        if filtered:
            files = filtered
    if not files:
        raise ValueError("fallback 資料夾中沒有找到符合條件的字型檔。")
    return files


def find_fallback_for_source(source_file, fallback_candidates):
    source_weight = detect_weight_from_filename(source_file)
    for candidate in fallback_candidates:
        if detect_weight_from_filename(candidate) == source_weight:
            return candidate
    for candidate in fallback_candidates:
        if detect_weight_from_filename(candidate) == "Regular":
            return candidate
    return fallback_candidates[0]


def build_font_name_for_source(source_file, family_name_prefix=None):
    if not family_name_prefix:
        return None
    weight = detect_weight_from_filename(source_file)
    return f"{family_name_prefix} {weight}"


def build_static_cjk_family(
    input_path,
    output_dir,
    fallback_dir=None,
    fallback_prefix=None,
    config="s2t",
    merge_mode="universal",
    no_punc=False,
    force_vertical=False,
    output_woff2=False,
    family_name_prefix=None,
):
    source_files = collect_source_fonts(input_path)
    fallback_candidates = collect_fallback_candidates(fallback_dir, fallback_prefix) if fallback_dir else None

    os.makedirs(output_dir, exist_ok=True)
    results = []

    for source_file in source_files:
        base_name = path.basename(source_file)
        stem, ext = path.splitext(base_name)
        output_file = path.join(output_dir, f"{sanitize_filename_part(stem)}_TC{ext}")
        fallback_font = find_fallback_for_source(source_file, fallback_candidates) if fallback_candidates else None

        build_font(
            input_file=source_file,
            output_file=output_file,
            config=config,
            fallback_font=fallback_font,
            merge_mode=merge_mode,
            no_punc=no_punc,
            force_vertical=force_vertical,
            output_woff2=output_woff2,
            font_name=build_font_name_for_source(source_file, family_name_prefix),
        )

        results.append({
            "source_file": source_file,
            "fallback_font": fallback_font,
            "output_file": output_file,
            "weight": detect_weight_from_filename(source_file),
        })

    return results
