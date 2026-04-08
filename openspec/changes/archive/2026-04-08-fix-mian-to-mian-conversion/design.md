## Context

The OpenCC Font Generator uses pre-calculated character and word conversion tables stored in the `src/OpenCCFontGenerator/cache/` directory. These tables are used to generate OpenType GSUB substitution rules. The `twp` (Taiwan Phrases) configuration was found to have an incorrect character-level mapping for "面" (U+9762), causing it to always be replaced by "麵" (U+9EB5).

## Goals / Non-Goals

**Goals:**
- Correct the character-to-character mapping for "面" in the `twp` cache.
- Ensure no regressions occur for other configurations or phrase-based conversions.

**Non-Goals:**
- Implementing a dynamic table generation script (out of scope for this urgent bug fix).
- Modifying the underlying OpenCC dictionary files (the generator relies on the cached tables).

## Decisions

### Decision 1: Direct Modification of Cache Files
We will directly edit `src/OpenCCFontGenerator/cache/convert_table_chars_twp.txt`.
- **Rationale**: The tool currently relies on these cached files as the primary source of truth for font generation. There is no automated build script in the repository that regenerates these from the raw dictionaries.
- **Alternative**: Attempting to find or write a regeneration script. This is rejected because it introduces risk of wider changes to the dictionaries that might not be desired.

### Decision 2: Conservative Mapping for Ambiguous Characters
"面" (Simplified) maps to both "面" (Traditional: face/surface) and "麵" (Traditional: noodles). 
- **Rationale**: In a font generator, a 1-to-1 character mapping should be conservative. Mapping `面` to `面` preserves the face/surface meaning. Phrases like "泡麵" (instant noodles) are already handled correctly by the word conversion table (`convert_table_words_twp.txt`), ensuring "noodles" are still correctly converted in context.

## Risks / Trade-offs

- **[Risk]**: Single instances of "面" that truly mean "noodles" (rare in isolation) will no longer be converted to "麵".
- **[Mitigation]**: This is a much better user experience than the current bug where *all* surfaces/faces become noodles. Most noodle-related terms appear in phrases already covered by the word table.
