## Why

To enhance the versatility and localization of `OpenCCFontGenerator`, we are adopting several key features inspired by the `TCFontCreator` project. Currently, the tool only supports basic `s2t` and `twp` (Taiwan phrase) conversions. Adding support for more regional standards (like Hong Kong and pure Taiwan standards), reverse conversion (Traditional to Simplified), and a glyph fallback mechanism will make the generated fonts much more robust and suitable for a wider audience.

## What Changes

- Add support for additional OpenCC conversion configurations, specifically `s2hk` (Simplified to Hong Kong Traditional) and `s2tw` (Simplified to Taiwan Traditional).
- Implement a "Traditional to Simplified" (T2S) font generation mode using OpenCC's `t2s.json` or `tw2s.json`.
- Implement a missing glyph fallback feature to automatically pull and merge missing glyphs from a secondary "fallback" font during the generation process.

## Capabilities

### New Capabilities
- `regional-conversion-standards`: Support for generating fonts targeting specific regional Traditional Chinese standards (`s2hk`, `s2tw`).
- `t2s-conversion`: Support for generating Traditional to Simplified (T2S) fonts.
- `glyph-fallback`: Mechanism to extract and merge missing glyphs from a fallback font when the primary font lacks certain converted characters.

### Modified Capabilities

## Impact

- `start.py`: Will need updates to ask users about regional preferences, T2S mode, and fallback font options.
- `src/OpenCCFontGenerator/__main__.py`: CLI arguments will be expanded to accept new configurations (e.g., `--config s2hk`, `--fallback-font`).
- `src/OpenCCFontGenerator/font.py`: Core logic will be modified to handle the fallback merging process and support different OpenCC JSON configurations.
- Dependencies: May require additional font manipulation logic, potentially extending usage of `otfcc` for merging glyphs.