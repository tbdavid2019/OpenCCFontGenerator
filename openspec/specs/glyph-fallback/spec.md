## ADDED Requirements

### Requirement: Missing glyph extraction from fallback
The system SHALL identify missing characters in the target font required for OpenCC substitution and extract their corresponding glyphs from a user-provided fallback font.

#### Scenario: Target character missing in primary font
- **WHEN** the primary font lacks the glyph for a Traditional/Simplified substitute character and a fallback font is supplied
- **THEN** system extracts the needed glyphs from the fallback font's JSON structure

### Requirement: Fallback glyph merging
The system SHALL inject extracted fallback glyphs into the target font's structure, updating `glyf` definitions and mapping them correctly in the `cmap`.

#### Scenario: Merging fallback into primary font
- **WHEN** fallback glyphs have been extracted successfully
- **THEN** system injects them into the primary font JSON, ensuring they are addressable by their substituted unicode codepoints
