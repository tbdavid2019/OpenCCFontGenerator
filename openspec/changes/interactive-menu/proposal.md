## Why

Users who are not familiar with command-line interfaces find it hard to remember and correctly supply all required arguments (`--input-file`, `--output-file`, `--name-header-file`, `--font-version`, `--twp`, etc.). A guided wizard removes this barrier and makes the tool accessible to non-engineers.

## What Changes

- New standalone script `start.py` at the project root that runs an interactive step-by-step wizard
- The wizard collects all required inputs, then calls the existing `build_font()` function
- No changes to `__main__.py` or `font.py` (full backwards compatibility)

## Capabilities

### New Capabilities
- `interactive-wizard`: A guided command-line wizard that prompts the user for each required input and option, then invokes font generation

### Modified Capabilities
- (none)

## Impact

- New file: `start.py` (project root)
- No changes to existing source files
- No new dependencies (uses Python standard library `input()` only)
