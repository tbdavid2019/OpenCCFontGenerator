## ADDED Requirements

### Requirement: Punctuation excluded from conversion when no_punc is enabled
When the `--no-punc` flag is passed, the generator SHALL exclude all non-Han characters (as defined by `build_codepoints_non_han()`) from both the character-level and word-level OpenCC conversion tables before building the GSUB substitution table.

#### Scenario: Single-character punctuation excluded
- **WHEN** `--no-punc` is set and the source font contains a punctuation mapping (e.g. `"` → `「`)
- **THEN** the generated font's `liga_s2t` GSUB table SHALL NOT contain a substitution rule for that punctuation character

#### Scenario: Word entry containing punctuation excluded
- **WHEN** `--no-punc` is set and a word-level OpenCC entry contains at least one non-Han codepoint
- **THEN** that word entry SHALL NOT be included in the `word2pseu` or `pseu2word` GSUB subtables

#### Scenario: Han character conversion unaffected
- **WHEN** `--no-punc` is set
- **THEN** all Han character substitution rules SHALL remain present and unchanged in the generated font

#### Scenario: Default behaviour preserved
- **WHEN** `--no-punc` is NOT set (default)
- **THEN** the generated font SHALL behave identically to a font generated without this feature (backwards compatible)

### Requirement: CLI exposes no-punc flag
The command-line interface SHALL accept a `--no-punc` boolean flag (default: false) that maps directly to the `no_punc` parameter of `build_font()`.

#### Scenario: Flag accepted without error
- **WHEN** the user runs the generator with `--no-punc`
- **THEN** the process SHALL complete successfully without error
