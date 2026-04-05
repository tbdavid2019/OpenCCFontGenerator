## 1. Project Configuration Update

- [x] 1.1 Update `start.py` interactive wizard to prompt users for OpenCC configuration (e.g., `s2t`, `twp`, `s2hk`, `s2tw`, `t2s`).
- [x] 1.2 Update `start.py` to prompt users if they want to provide a fallback font file.
- [x] 1.3 Add CLI argument support in `src/OpenCCFontGenerator/__main__.py` for `--config` (to replace/supplement `--twp`) and `--fallback-font`.

## 2. OpenCC Data Dynamic Loading

- [x] 2.1 Refactor `src/OpenCCFontGenerator/font.py` to accept a `config` string (e.g., `s2hk`) instead of boolean flags like `twp`.
- [x] 2.2 Modify `font.py` to read the OpenCC dictionary files dynamically based on the chosen config instead of hardcoding `t2twp.json`.
- [x] 2.3 Verify the generation of `s2hk`, `s2tw`, and `t2s` mapping data works correctly with the OpenCC `.txt` files.

## 3. Fallback Font Processing

- [x] 3.1 Implement a function in `font.py` to check the primary font's `cmap` against the required substitution target characters.
- [x] 3.2 If missing glyphs are found and a fallback font is provided, run `otfccdump` on the fallback font.
- [x] 3.3 Extract the missing `glyf` definitions and `cmap` mappings from the fallback JSON.
- [x] 3.4 Inject the extracted glyphs into the primary font's JSON structure.
- [x] 3.5 Ensure `otfccbuild` compiles the merged JSON back into a valid font without errors.
