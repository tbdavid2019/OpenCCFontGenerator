## Context

The `OpenCCFontGenerator` tool translates Simplified Chinese text into Traditional Chinese via font-level GSUB substitution ligatures powered by OpenCC rules. While functional, it is currently limited to generic `s2t` and `twp` conversions. To enhance versatility, we want to adopt capabilities seen in `TCFontCreator`, including regional variants (`s2hk`, `s2tw`), reverse conversion (`t2s`), and missing glyph fallback logic, which merges necessary glyphs from a secondary font when the primary font doesn't contain a target character.

## Goals / Non-Goals

**Goals:**
- Add command-line and interactive wizard (`start.py`) support for `s2hk`, `s2tw`, and `t2s` conversion configurations.
- Introduce a new process in the font generation pipeline to optionally import missing glyphs from a provided fallback font, preventing "tofu" boxes when substituting characters.

**Non-Goals:**
- Completely rewriting the `otfcc` parsing engine.
- Adding full support for all possible OpenCC permutations (like `hk2s` or `tw2sp`) unless explicitly requested; focusing on the main additions.
- Creating a graphical desktop application; we will stick to CLI and the interactive `start.py` wizard.

## Decisions

1. **Configuration Selection**: `OpenCCFontGenerator` currently hardcodes the OpenCC files. We will modify it to accept a generic OpenCC config identifier (e.g., `s2hk`, `s2tw`, `t2s`) and dynamically load the respective rule sequences from the OpenCC data directory.
   - *Rationale*: Hardcoding logic for each config doesn't scale. Dynamic loading based on config name allows easier extension.
2. **Glyph Fallback Implementation**: After generating the conversion mapping, we will cross-reference the required target characters against the base font's `cmap`. If missing, we will use `otfcc` to extract the glyphs from the fallback font's OTF JSON dump and inject them into the target font's JSON structure before compiling.
   - *Rationale*: `otfcc` converts the font to JSON, allowing us to surgically inject `glyf` definitions and update the `cmap`.

## Risks / Trade-offs

- **[Risk] Complex Fallback Merging** -> Font merging is complex due to differing metrics and units per em. Mitigation: Implement a simple injection approach that updates `cmap` and `glyf`, warning the user that mismatched font metrics might look visually inconsistent.
- **[Risk] Slower Generation Time** -> Merging requires dumping and parsing a second font to JSON. Mitigation: Only parse the fallback font if explicitly provided and if missing glyphs are detected.