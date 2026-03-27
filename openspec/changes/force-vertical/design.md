## Context

The goal is to implement "Option B: Vertical-Only" as requested by the user. The project already manipulates Cmap and GSUB tables; we will extend this to find vertical variants and swap them into the `cmap`.

## Goals / Non-Goals

**Goals:**
- Provide a `--force-vertical` flag that swaps horizontal glyphs with vertical variants in the `cmap`
- Ensure the `vmtx` and other vertical tables are cleaned up when glyphs are removed
- Support both CLI and the interactive wizard

**Non-Goals:**
- Manually rotating glyph contours 90 degrees CCW (out of scope for v1, rely on existing `.vert` glyphs)
- Modifying the font's internal names (e.g., adding "Vertical" to the font name) automatically

## Decisions

**Decision 1: Use `vert` and `vrt2` features for mapping**
Rationale: These are the standard OpenType features for vertical layout. If a font supports vertical layout, it will have these features defined.

**Decision 2: Update `cmap` and `cmap_rev` in place**
Rationale: `font.py` already uses these two dictionaries. Updating both ensures that subsequent logic (like `remove_glyph` or `build_font`'s own range logic) remains consistent.

**Decision 3: Update `remove_glyph` to handle more tables**
Rationale: A CJK font with vertical support has a `vmtx` table (Vertical Metrics) and `VORG` (Vertical Origin). `otfccdump` exports these as top-level keys in the JSON. If we delete a glyph but leave it in `vmtx`, the font might become invalid.

## Risks / Trade-offs

- **Risk**: Source font doesn't have `vert` variants.  
  → Mitigation: The feature will simply have no effect on those glyphs, which is safe.
- **Risk**: `vmtx` table format in `otfcc` JSON.  
  → Mitigation: We will use a safe `try-except` pattern when attempting to delete from these optional tables.
