## Context

The `build_font()` function in `font.py` reads conversion tables generated from OpenCC dictionaries and builds three GSUB subtables (`word2pseu`, `char2char`, `pseu2word`) that get embedded in the output font as the `liga_s2t` feature. The dictionaries (`STCharacters.txt`, `STPhrases.txt`) contain both Han characters and some punctuation entries, so both are currently converted unconditionally.

The codebase already has a `build_codepoints_non_han()` function that returns the exact Unicode ranges considered non-Han (punctuation, symbols, Latin, etc.).

## Goals / Non-Goals

**Goals:**
- Allow callers of `build_font()` to opt out of punctuation/symbol conversion via a `no_punc=False` parameter
- Expose this new parameter as `--no-punc` CLI flag
- Fully backwards-compatible: existing behaviour unchanged when flag is absent

**Non-Goals:**
- Changing the OpenCC dictionary files or cache generation
- Granular per-character selection (e.g., keep commas, drop quotes)
- Affecting TWP (Taiwan phrases) or TWVariants conversion entries differently

## Decisions

**Decision 1: Filter at `build_font()` time, not at cache-build time**
Rationale: The cache files are shared across runs. Filtering at build time is cheaper and avoids re-generating caches. The `entries_char` and `entries_word` lists are small in-memory structures that are trivial to filter.

Alternative considered: Add a `--no-punc` flag to `setup.py`'s `build_convert_tables()` to produce separate cache files. Rejected because it doubles the number of cache files and complicates setup.

**Decision 2: Use existing `build_codepoints_non_han()` to identify punctuation**
Rationale: This function already defines the precise Unicode ranges used for the font's coverage. Reusing it avoids an inconsistent definition of "punctuation". This means characters in `non_han` ranges (e.g. `0x3000–0x301C`) that happen to appear in OpenCC dictionaries will be excluded from conversion.

## Risks / Trade-offs

- **Risk**: Some users may want to convert *some* punctuation but not all.  
  → Mitigation: Not in scope. This is an all-or-nothing toggle. Per-character control can be a separate future change.
- **Trade-off**: Using `build_codepoints_non_han()` as the definition of "punctuation" ties the filter to the font coverage definition. If `build_codepoints_non_han()` changes, the filter changes too.  
  → Accepted: the coupling is intentional and preferable to duplication.
