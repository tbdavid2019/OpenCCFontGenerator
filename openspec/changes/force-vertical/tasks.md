## 1. Core Logic (`font.py`)

- [ ] 1.1 Update `remove_glyph()` to safely delete `glyph_name` from `obj['vmtx']`, `obj['VORG']`, `obj['hmtx']` and `obj['vhea']` if present.
- [ ] 1.2 Implement `apply_force_vertical(obj)`:
  - Find all `GSUB` lookups linked to `vert` or `vrt2` features.
  - Traverse these lookups (supporting `gsub_single` type) to build a mapping dict.
  - Loop through `obj['cmap']` and update entries that have a mapping.
  - Update `obj['cmap_rev']` to keep it in sync.
- [ ] 1.3 Add `force_vertical=False` parameter to `build_font()` and call `apply_force_vertical()` before `font_version` update.

## 2. CLI and Wizard

- [ ] 2.1 Update `__main__.py` to add `--force-vertical` flag and pass it to `build_font()`.
- [ ] 2.2 Update `start.py` to add a prompt for "Force Vertical" mode (Step 8).

## 3. Documentation

- [ ] 3.1 Update `README.md` to include Force-Vertical mode instructions.
- [ ] 3.2 Update `CHANGELOG.md` with the new feature.

## 4. Verification

- [ ] 4.1 Run on a CJK font and verify `cmap` points to `.vert` glyphs for brackets.
