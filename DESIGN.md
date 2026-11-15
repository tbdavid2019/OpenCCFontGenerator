# Design System

Captured from the built Web Workbench (`src/OpenCCFontGenerator/web/static/index.html`, `styles.css`, `app.js`).

## Surface Mode

- **Operate**: Public font engineering workbench and async job queue paired with OpenAPI documentation (`/docs`).

## Palette & Material Tokens

- `--bg-ground`: `#F6F7F9` (specimen alabaster page ground)
- `--bg-surface`: `#FFFFFF` (header bars, specimen strip, form panels, job cards)
- `--bg-subpanel`: `#FAFBFD` (right job queue column, input fills)
- `--bg-rail`: `#141619` (fixed left navigation rail and log terminal surface)
- `--ink-primary`: `#141619`
- `--ink-secondary`: `#4B5563`
- `--ink-muted`: `#6B7280`
- `--border-hairline`: `#DCE0E6` (`1px` structural grid dividers)
- `--border-strong`: `#B8C0CC` (upload dropzone borders)
- `--accent`: `#1D5BD6` (cobalt registration blue: active mode nav, checked option pills, primary CTA, focus ring, running progress bar)
- State roles: `--state-ok` (`#0F7B5F`), `--state-warn` (`#B45309`), `--state-err` (`#B91C1C`)

## Typography

- **UI & Specimen Sans**: `"PingFang TC", "Noto Sans TC", "Microsoft JhengHei", system-ui, -apple-system, sans-serif` (`14px` body, `17px` mode header, `16px` specimen pairs)
- **Technical Monospace**: `ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace` (`tabular-nums` for quotas, job durations, file sizes, and OpenCC tokens)

## Layout & Signature Interaction

- **Desktop Shell (`> 1180px`)**: `272px` charcoal left rail + flexible main column (`64px` topbar, `70px` live OpenCC Specimen Strip, `1fr | 400px` split workspace separating form inputs on the left from the async job ledger on the right).
- **Tablet (`<= 1180px`)**: Single-column workspace stacking job ledger below the form pane.
- **Mobile (`<= 900px`)**: Off-canvas navigation drawer triggered from topbar menu button; single-column form grids (`minmax(0, 1fr)`).
- **Signature Specimen Strip**: Real-time `/api/v1/preview` conversion strip reacting to active `config` (`s2t`, `twp`, `s2tw`, `s2hk`, `t2s`), `no_punc`, and custom phrase input.

## Motion & States

- `150ms–240ms` transitions for mode switching, hover states, drawer slide, and stepped phase progress (`transition: width 240ms ease`), disabled cleanly under `prefers-reduced-motion: reduce`.
- Every interactive form control and job state covers default, hover, focus-visible (`2px solid #1D5BD6`), disabled, uploading progress, queued, running, completed, failed, and empty states.
