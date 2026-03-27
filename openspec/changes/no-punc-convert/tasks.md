## 1. Core Logic (`font.py`)

- [x] 1.1 Add `no_punc=False` parameter to `build_font()` function signature
- [x] 1.2 Inside `build_font()`, after building `entries_char`, add filter: when `no_punc` is True, call `build_codepoints_non_han()` and filter out entries where source codepoint is in that set
- [x] 1.3 Inside `build_font()`, after building `entries_word`, add filter: when `no_punc` is True, filter out word entries where any codepoint in the source tuple is in the non-Han set

## 2. CLI (`__main__.py`)

- [x] 2.1 Add `--no-punc` argument to `argparse` using `BooleanOptionalAction` (default `False`), with help text describing the flag
- [x] 2.2 Pass `no_punc=args.no_punc` to the `build_font()` call

## 3. Verification

- [ ] 3.1 Run the generator without `--no-punc` on a sample font and confirm punctuation rules (e.g. `"` → `「`) are present in the output font's GSUB table via `otfccdump`
- [ ] 3.2 Run the generator with `--no-punc` on the same sample font and confirm those punctuation rules are absent, while Han character rules remain
