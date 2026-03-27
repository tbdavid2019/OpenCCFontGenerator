## Why

The generator currently converts all entries from OpenCC dictionaries, including punctuation marks such as quotation symbols (`" "` → `「 」`). Some users want Han character conversion without altering punctuation, which should remain as-is from the source font.

## What Changes

- Add new CLI flag `--no-punc` to `__main__.py`
- Add filtering logic in `font.py`'s `build_font()` to exclude non-Han codepoints from the char and word conversion tables when `--no-punc` is set

## Capabilities

### New Capabilities
- `punctuation-filtering`: Ability to exclude punctuation characters from the OpenCC-driven GSUB substitution table during font generation

### Modified Capabilities
- (none)

## Impact

- `src/OpenCCFontGenerator/font.py`: `build_font()` gains a new `no_punc` parameter; filtering applied to `entries_char` and `entries_word`
- `src/OpenCCFontGenerator/__main__.py`: new `--no-punc` argument added to `argparse`
- No change to OpenCC dictionaries or cache files
- No change to existing font output when `--no-punc` is not used (fully backwards compatible)
