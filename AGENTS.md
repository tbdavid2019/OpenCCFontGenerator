# AGENTS.md

Guidelines for AI coding agents working in `OpenCCFontGenerator`.

## Environment & Key Paths

- **Python / Build Virtualenv**: `$HOME/.virtualenvs/opencc_gen` (`opencc>=1.4.2`, `fonttools>=4.62.1`, `brotli`, `setuptools`, plus `otfccdump` / `otfccbuild` in `PATH`).
- **Core Font Pipeline**: `src/OpenCCFontGenerator/font.py`
- **Dictionary & Cache Builder**: `setup.py` (downloads `opencc-data@1.4.2` into `src/OpenCCFontGenerator/opencc_data/` and builds `src/OpenCCFontGenerator/cache/*.txt`, tracked via `.opencc_data_version` and `.cache_version`).
- **Taiwan Phrases Config**: `src/OpenCCFontGenerator/t2twp.json` (OpenCC `1.4.2` schema).
- **Tests**: `tests/test_font_io.py` (`PYTHONPATH=src python -m unittest discover -s tests -v`).

## Project Skills (Read Before Editing Relevant Areas)

- **OpenCC Library & Dictionary Upgrades (`opencc-dict-upgrade`)**:
  - Skill: `.agents/skills/opencc-dict-upgrade/SKILL.md`
  - Verification script: `.agents/skills/opencc-dict-upgrade/scripts/verify_opencc_upgrade.py`
  - Read and follow this skill whenever upgrading `opencc` or `opencc-data`, modifying `setup.py` cache generation, changing `t2twp.json`, or updating version checks in `run.sh`.

## Critical Invariants (Do Not Regress)

1. **No Duplicate GSUB Feature Tags**: `otfccdump` exports source font features with indexed suffixes (e.g. `liga_00036`, `rlig_00051`, `ccmp_00007`). Always merge OpenCC lookups into existing features via `ensure_gsub_feature_targets()` / `_attach_gsub_lookup()` rather than inserting duplicate `liga`/`rlig`/`ccmp` keys, and preserve `word2pseu -> char2char -> pseu2word` lookup order.
2. **Variant Filling (`apply_variants`) Order & Isolation**:
   - Run `apply_variants()` *after* `--fallback-font` merging so fallback Traditional glyphs (e.g. `後`, `發`, `髮`) are not prematurely aliased away.
   - Do not cross-map distinct homograph groups (e.g. keep `發`/`発` isolated from `髮`/`髪`) and skip `t2s`.
3. **Cache Generation Guards (`setup.py`)**:
   - Never apply `t2s(k)` to single-character variant tables (`TWVariants.txt`, `HKVariants.txt`); only retain `(k, v)` directly so `麪->麵`, `檯->枱`, `柺->枴` do not overwrite Simplified `面`, `台`, `拐`.
   - Preserve protective `k == v` guard phrases (e.g. `皇后 -> 皇后`) while pruning redundant `k == v` lines to stay within the OpenType `65,535` glyph limit.

## Verification & Changelog Rules

- After code or config edits, run syntax checks and unit tests (`bash -n run.sh`, `python -m py_compile ...`, `PYTHONPATH=src python -m unittest discover -s tests -v`).
- After OpenCC or cache edits, run `.agents/skills/opencc-dict-upgrade/scripts/verify_opencc_upgrade.py --expected-version <VER>` (and `--font <path>` on macOS when verifying GSUB/CoreText shaping).
- Every repository change must be recorded in `CHANGELOG.md` under a date heading (`## [YYYY-MM-DD]`); do **not** use `[Unreleased]`.
