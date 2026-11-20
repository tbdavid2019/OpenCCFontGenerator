# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

delegated: FastAPI (Python + Uvicorn) backend serving a REST + OpenAPI (`/docs`) service and a zero-build static HTML/CSS/ES-module Web UI from a single Docker container.

## Users

E-book readers (including Kobo / vertical-reading users), typography enthusiasts, and web or app developers who want to convert CJK fonts with OpenCC phrase-level OpenType rules via a browser or HTTP API without installing Python, `fontTools`, OpenCC cache tables, or `otfcc` locally.

## Product Purpose

Expose OpenCCFontGenerator's CLI and interactive wizard capabilities as a public-facing Web workbench and async REST API packaged as a self-hostable Docker image.

## Positioning

Unlike runtime text-conversion scripts or naive codepoint remapping tools, this service compiles OpenCC 1.4.2 phrase-level GSUB (`liga`/`rlig`/`ccmp`) lookup tables directly into downloadable font binaries while supporting fallback glyph merging, 90° vertical rotation, WOFF2 + CSS webfont bundling, and multi-weight family batch generation.

## Operating Context

CJK font decompilation (`otfccdump`), GSUB injection, and recompilation (`otfccbuild`) typically take 15–60+ seconds per font and consume significant memory. The web and API layer operates asynchronously: clients upload source/fallback fonts to create a job, poll status and streaming build logs by `job_id`, and download single font outputs or `.zip` bundles once complete. Deployed via multi-arch Docker (`linux/amd64` and `linux/arm64` with `otfcc` v0.10.4 built from verified source) behind reverse proxies or directly for public self-hosted access.

## Capabilities and Constraints

- **Full Pipeline Coverage**:
  1. **Single Font Conversion (`convert`)**: `s2t`, `twp`, `s2tw`, `s2hk`, `t2s`, `no_punc`, custom font name / version / TTC index, optional fallback font dual-upload (`merge_mode`: `opencc`/`universal`, `fill_charset`: `none`/`hant-common`/`opencc-hant`/`han`), `force_vertical`, `kobo`, `woff2`.
  2. **90° Vertical Rotation (`rotate90`)**: `.ttf`/`.otf`/`.ttc` input, `cw`/`ccw` direction, Han+Bopomofo-only or rotate-all, `ttc_index`, `kobo`.
  3. **Webfont Packager (`webfont`)**: convert font to `.woff2` + `fonts.css` bundle (`.zip`) with custom CSS `font-family`.
  4. **Static CJK Family Batch (`static-family`)**: multi-file / archive upload of static font weights + optional multi-file / archive fallback fonts, producing a downloadable `.zip` bundle.
  5. **Variable CJK Family Instantiation (`variable-family`)**: variable font (`fvar`/`wght`) + fallback weights archive/files, selectable weights (`Thin`..`Black`), producing a downloadable `.zip` bundle.
- **Public Access & Resource Protections**: No login required; protected by configurable upload size caps, allowed font/archive extensions, single/multi-worker bounded concurrency queue, per-IP rate limiting, isolated per-job working directories, and automatic TTL cleanup of expired jobs/artifacts.
- **Existing CLI Preservation**: Existing CLI entrypoints (`src/OpenCCFontGenerator/__main__.py`, `start.py`, `run.sh`, etc.) and unit tests must continue to work unchanged.

## Product Principles

1. **Async-First Transparency**: Surface queue position, current pipeline stage, elapsed time, and real execution logs clearly so long-running font builds feel predictable.
2. **Isolation & Resource Safety**: Run heavy font jobs in isolated per-job directories/workers without shared log collisions, path traversal risk, or disk leaks.
3. **UI-API Parity**: Every Web UI workflow uses the exact public REST API documented in `/docs`.
4. **Familiar Typography Craft**: Respect Traditional Chinese typography terminology and OpenType conventions without decorative clutter.
