## ADDED Requirements

### Requirement: Force-Vertical swaps horizontal punctuation with vertical variants
When `--force-vertical` is enabled, the generator SHALL map codepoints for horizontal punctuation (e.g., `U+300C` 「) to their corresponding vertical glyph names (e.g., `﹁`) in the `cmap` table.

#### Scenario: User enables Force-Vertical on a font with `vert` table
- **WHEN** the user runs the generator with `--force-vertical`
- **THEN** the `cmap` of the output font points `U+300C` to the glyph for `﹁` (usually named `bracketleft.vert` or similar)
- **AND** the standard Traditional conversion still happens.

### Requirement: Force-Vertical handles `vert` and `vrt2` features
The generator SHALL look at both `vert` and `vrt2` features in the `GSUB` table to find all substitutions.

### Requirement: Glyph removal cleans up all vertical metric tables
When a glyph is removed (via `remove_glyph()`), it SHALL also be removed from any present vertical tables (`vmtx`, `VORG`, `vhea`).

#### Scenario: Glyph removal with vertical metrics
- **WHEN** `remove_glyph("A")` is called and the font has a `vmtx` table
- **THEN** both the `glyf` entry and the `vmtx` entry for "A" SHALL be deleted.

### Requirement: Wizard support
`start.py` SHALL include a step to enable or disable Force-Vertical mode.
