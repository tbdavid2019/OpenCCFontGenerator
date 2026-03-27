## 1. Script Scaffolding

- [x] 1.1 Create `start.py` at the project root with a `main()` function and `if __name__ == '__main__': main()` guard
- [x] 1.2 Add import for `os.path`, `sys`, and `OpenCCFontGenerator.font.build_font` at the top of `start.py`

## 2. Wizard Prompts

- [x] 2.1 Implement conversion mode menu: print numbered options (1. 包含標點符號轉換 / 2. 排除標點符號轉換), read input, validate it is `1` or `2`, and set `no_punc` accordingly
- [x] 2.2 Implement required-field prompt helper: re-prompt in a loop until a non-empty value is given, with a customisable error message
- [x] 2.3 Implement path-validation prompt: wrap the required-field helper with an `os.path.exists()` check; re-prompt if the file does not exist
- [x] 2.4 Prompt for source font path using the path-validation prompt
- [x] 2.5 Prompt for output font path using the required-field prompt (output file need not exist yet)
- [x] 2.6 Prompt for name-header JSON file path using the path-validation prompt
- [x] 2.7 Prompt for font version number; validate it is a valid float; re-prompt on invalid input
- [x] 2.8 Prompt for optional TTC index (Enter to skip, otherwise integer); store `None` if skipped
- [x] 2.9 Prompt for optional Taiwan phrases conversion (`y/n`, default `n`)

## 3. Font Generation Call

- [x] 3.1 After all prompts, print a summary of the selected options and a `正在生成字型…` status message
- [x] 3.2 Call `build_font()` with all collected arguments
- [x] 3.3 Print a success message `✓ 完成！已儲存至 <output_path>` when generation completes

## 4. Verification

- [ ] 4.1 Run `python start.py` manually and walk through all prompts; confirm the font is generated correctly
- [ ] 4.2 Test invalid input paths: confirm re-prompt behaviour without crash
- [ ] 4.3 Test selecting option 2 (no punctuation); confirm `no_punc=True` is passed (if `no-punc-convert` change is also applied)
