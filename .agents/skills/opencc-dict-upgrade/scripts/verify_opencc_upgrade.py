#!/usr/bin/env python3
"""Verify OpenCC version alignment, generated cache tables, and optional font shaping."""

import argparse
import os
import subprocess
import sys
import tempfile


SUFFIX_MAP = {
    "s2t": "",
    "twp": "_twp",
    "s2tw": "_s2tw",
    "s2hk": "_s2hk",
    "t2s": "_t2s",
}


def load_table(path):
    entries = {}
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            if line.startswith("#"):
                raise AssertionError(f"Unstripped comment leaked into {path}:{lineno}: {line!r}")
            stripped = line.strip()
            if not stripped:
                continue
            parts = stripped.split("\t")
            if len(parts) != 2:
                raise AssertionError(f"Malformed line in {path}:{lineno}: {line!r}")
            entries[parts[0]] = parts[1]
    return entries


def verify_cache(pkgroot, expected_version):
    data_ver_path = os.path.join(pkgroot, "opencc_data", ".opencc_data_version")
    cache_ver_path = os.path.join(pkgroot, "cache", ".cache_version")
    for stamp_path in (data_ver_path, cache_ver_path):
        with open(stamp_path, encoding="utf-8") as f:
            actual = f.read().strip()
        if actual != expected_version:
            raise AssertionError(
                f"Version mismatch in {stamp_path}: expected {expected_version!r}, got {actual!r}"
            )
    print(f"[ok] Version stamps match {expected_version}")

    for cfg, suf in SUFFIX_MAP.items():
        chars = load_table(os.path.join(pkgroot, "cache", f"convert_table_chars{suf}.txt"))
        words = load_table(os.path.join(pkgroot, "cache", f"convert_table_words{suf}.txt"))
        print(f"[ok] {cfg}: chars={len(chars)}, words={len(words)}")

        if cfg != "t2s":
            expected_words = {
                "皇后": "皇后",
                "后来": "後來",
                "发现": "發現",
                "业余": "業餘",
            }
            for k, v in expected_words.items():
                if words.get(k) != v:
                    raise AssertionError(f"{cfg}: words[{k!r}]={words.get(k)!r}, expected {v!r}")

        if cfg in ("twp", "s2tw"):
            if chars.get("面") not in (None, "面"):
                raise AssertionError(f"{cfg}: chars['面']={chars.get('面')!r} (should stay 面)")
            if words.get("面条") != "麵條":
                raise AssertionError(f"{cfg}: words['面条']={words.get('面条')!r}, expected '麵條'")

        if cfg == "twp":
            if words.get("软件") != "軟體":
                raise AssertionError(f"twp: words['软件']={words.get('软件')!r}, expected '軟體'")

        if cfg == "s2hk":
            for bad_char in ("拐", "台"):
                if bad_char in chars:
                    raise AssertionError(
                        f"s2hk: unexpected single-char overwrite chars[{bad_char!r}]={chars[bad_char]!r}"
                    )


def verify_font_coretext(font_path, config="twp"):
    from fontTools.ttLib import TTFont
    from OpenCCFontGenerator.font import build_font

    if not os.path.exists(font_path):
        raise FileNotFoundError(f"Font not found: {font_path}")

    with tempfile.NamedTemporaryFile(suffix=".ttf", delete=False) as tmp:
        out_path = tmp.name

    try:
        build_font(font_path, out_path, config=config, font_name="VerifyOpenCCUpgrade")
        tt = TTFont(out_path)
        num_glyphs = len(tt.getGlyphOrder())
        if num_glyphs > 65535:
            raise AssertionError(f"Glyph count exceeded OpenType limit (65535): {num_glyphs}")
        print(f"[ok] Built {config} font glyph count: {num_glyphs} (<= 65535)")

        cmap = tt.getBestCmap()
        swift_code = r"""
import CoreText
import Foundation

let fontPath = CommandLine.arguments[1]
let url = URL(fileURLWithPath: fontPath)
let descs = CTFontManagerCreateFontDescriptorsFromURL(url as CFURL) as! [CTFontDescriptor]
let font = CTFontCreateWithFontDescriptor(descs[0], 24.0, nil)

let samples = ["业余", "后来", "皇后", "发现", "头发", "软件", "面", "面条"]
for s in samples {
    let attr = NSAttributedString(string: s, attributes: [kCTFontAttributeName as NSAttributedString.Key: font])
    let line = CTLineCreateWithAttributedString(attr)
    let runs = CTLineGetGlyphRuns(line) as! [CTRun]
    var glyphs: [CGGlyph] = []
    for run in runs {
        let count = CTRunGetGlyphCount(run)
        var buf = [CGGlyph](repeating: 0, count: count)
        CTRunGetGlyphs(run, CFRangeMake(0, count), &buf)
        glyphs.append(contentsOf: buf)
    }
    print("\(s):\(glyphs.map(String.init).joined(separator: ","))")
}
"""
        res = subprocess.run(
            ["swift", "-", out_path],
            input=swift_code,
            text=True,
            check=True,
            capture_output=True,
        )
        shaped = {}
        for line in res.stdout.strip().splitlines():
            key, val = line.split(":", 1)
            shaped[key] = [int(x) for x in val.split(",")]

        def gid(ch):
            return tt.getGlyphID(cmap[ord(ch)])

        checks = {
            "业余": (1, gid("餘")),
            "后来": (0, gid("後")),
            "发现": (0, gid("發")),
            "头发": (1, gid("髮")),
        }
        for word, (idx, expected_gid) in checks.items():
            if shaped[word][idx] != expected_gid:
                raise AssertionError(
                    f"CoreText shaping failed for {word!r}: got {shaped[word]}, expected gid {expected_gid} at {idx}"
                )

        if shaped["皇后"] != [gid("皇"), gid("后")]:
            raise AssertionError(f"CoreText shaping failed for '皇后': {shaped['皇后']}")
        if config == "twp":
            if shaped["软件"] != [gid("軟"), gid("體")]:
                raise AssertionError(f"CoreText shaping failed for '软件': {shaped['软件']}")
            if shaped["面"] != [gid("面")]:
                raise AssertionError(f"CoreText shaping failed for '面': {shaped['面']}")
            if shaped["面条"] != [gid("麵"), gid("條")]:
                raise AssertionError(f"CoreText shaping failed for '面条': {shaped['面条']}")

        print(f"[ok] CoreText shaping checks passed for {list(shaped.keys())}")
    finally:
        if os.path.exists(out_path):
            os.remove(out_path)


def main():
    parser = argparse.ArgumentParser(description="Verify OpenCC dictionary upgrade cache and font output.")
    parser.add_argument("--expected-version", required=True, help="Expected opencc-data version, e.g. 1.4.2")
    parser.add_argument("--pkgroot", default="src/OpenCCFontGenerator", help="Path to package root")
    parser.add_argument("--font", help="Optional source font path to run build_font + CoreText check")
    parser.add_argument("--config", default="twp", help="Conversion config for --font check (default: twp)")
    args = parser.parse_args()

    verify_cache(args.pkgroot, args.expected_version)
    if args.font:
        if sys.platform != "darwin":
            print("[skip] CoreText font shaping check requires macOS")
        else:
            verify_font_coretext(args.font, config=args.config)


if __name__ == "__main__":
    main()
