## Why

Traditional Chinese book readers often prefer vertical layout (直排). However, many modern e-book devices and apps have poor or non-existent support for the OpenType `vert` feature, making it impossible to read correctly in vertical mode.

A "Force-Vertical" (Vertical-Only) font solves this by making the vertical variants the default glyphs in the `cmap`. This allows users to read vertically on any device by simply rotating the screen, even if the software only supports horizontal layout.

## What Changes

- Add `--force-vertical` flag to the CLI and a corresponding step in `start.py`
- Modify `font.py` to support `cmap` swapping based on the font's `vert` and `vrt2` features
- Improve `remove_glyph()` to handle vertical metrics (`vmtx`, `VORG`) to prevent font corruption

## Capabilities

### New Capabilities
- `force-vertical`: Generates a font where the default glyphs for punctuation and symbols are their vertical alternates.

### Modified Capabilities
- `font-generation`: Improved cleanup of vertical-specific tables during glyph removal.

## Impact

- **Compatibility**: The resulting font is intended for "Vertical-Only" use. It will look like a vertical font even in horizontal applications.
- **Source Requirements**: The source font must contain vertical variants (typically via the `vert` GSUB feature) for this to take effect.
