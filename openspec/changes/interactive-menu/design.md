## Context

The tool currently requires users to pass all arguments on the command line. A guided wizard (`start.py`) will replace that experience for users who prefer not to use flags. The existing `build_font()` API in `font.py` stays unchanged; `start.py` is purely a new front-end.

## Goals / Non-Goals

**Goals:**
- Provide a standalone `start.py` script that a user can run with `python start.py` and be guided through all inputs step-by-step
- Support the same set of options available in `__main__.py` (input/output path, name-header file, version, TTC index, `--twp`, `--no-punc`)
- Use only Python standard library (no extra dependencies)

**Non-Goals:**
- Replacing `__main__.py` (CLI flags remain fully supported)
- Building a TUI (curses, rich, etc.) — plain `input()` is sufficient for v1
- Internationalisation of wizard prompts

## Decisions

**Decision 1: Standalone `start.py`, not a subcommand of `__main__.py`**
Rationale: Keeping the wizard completely separate avoids any risk of breaking the existing CLI. Users run `python start.py` for the wizard and `python -m OpenCCFontGenerator` for scripting. Simple, discoverable, no flag conflicts.

Alternative considered: Add `--interactive` flag to `__main__.py`. Rejected because it mixes two UX patterns in one entry point.

**Decision 2: Use `input()` with inline validation, no third-party library**
Rationale: The project currently has zero runtime dependencies (only `opencc<1.2` for setup). Keeping `start.py` dependency-free makes it easy to run in any Python 3.8+ environment without `pip install`.

Alternative considered: `questionary` / `InquirerPy` for richer menus. Rejected due to added dependency and overkill for the use case.

**Decision 3: Re-prompt on invalid input instead of crashing**
Rationale: Users running a wizard expect forgiveness. For fields like file paths, `start.py` SHALL validate existence before proceeding; for optional fields, empty input SHALL use defaults.

## Risks / Trade-offs

- **Risk**: `start.py` duplicates the argument mapping logic from `__main__.py`.  
  → Mitigation: Both call the same `build_font()` function. Changes to `build_font()`'s signature must be reflected in both, but that is low-frequency work.
- **Trade-off**: Plain `input()` provides a limited UX compared to proper TUI frameworks.  
  → Accepted for v1; can be enhanced later.
