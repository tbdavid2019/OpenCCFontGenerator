# Design System

Captured from the built Web Workbench (`src/OpenCCFontGenerator/web/static/index.html`, `styles.css`, `app.js`).

## Surface Mode

- **Operate**: Public font engineering workbench and async job queue paired with OpenAPI documentation (`/docs`).

## Palette & Material Tokens (David888.com WCAG AA/AAA Theme)

- `--saffron`: `#FFB010` (`--saffron-hover`: `#F2A600`, `--saffron-soft`: `#FFF0CC`) — active rail navigation item, primary CTA fill, selection highlight, and brand accents
- `--deep-blue`: `#17324D` (`--deep-blue-dark`: `#0F2337`, `--clay`: `#9A3F18`) — fixed left navigation rail background, headings, primary action ink/border, checked option borders, focus rings, and running progress indicators
- `--bg-ground`: `#FFF2D1` (warm saffron-tinted ground)
- `--bg-surface`: `#FFFEFA` (header bars, specimen strip, form panels, job cards, and site footer)
- `--bg-subpanel`: `#FFF9E8` (warm cream input fills and right job queue ledger)
- `--bg-rail`: `#17324D` (fixed deep-navy left navigation rail; `#0F2337` for worker log terminal)
- `--ink-primary`: `#2B251A`, `--ink-heading`: `#17324D`, `--ink-secondary`: `#594E36`, `--ink-muted`: `#665A40` (all >= 6.4:1 contrast on paper/cream surfaces)
- `--border-hairline`: `#D6BC7C` (`1px` structural grid dividers), `--border-control`: `#877653` / `--border-strong`: `#7A6A49` (WCAG 1.4.11 >= 3:1 control boundaries)
- State roles: `--state-ok` (`#1B5329`), `--state-warn` (`#854700`), `--state-err` (`#8F3511`)

## Typography

- **UI & Specimen Sans**: `"PingFang TC", "Noto Sans TC", "Microsoft JhengHei", system-ui, -apple-system, sans-serif` (`14px` body, `17px` mode header, `16px` specimen pairs)
- **Technical Monospace**: `ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace` (`tabular-nums` for quotas, job durations, file sizes, and OpenCC tokens)

## Layout & Signature Interaction

- **Desktop Shell (`> 1180px`)**: `272px` deep-navy left rail + flexible main column (`64px` topbar, `70px` live OpenCC Specimen Strip, `1fr | 400px` split workspace separating form inputs on the left from the async job ledger on the right, plus a semantic `.site-footer` crediting `david888.com 技術提供`).
- **Tablet (`<= 1180px`)**: Single-column workspace stacking job ledger below the form pane.
- **Mobile (`<= 900px`)**: Off-canvas navigation drawer triggered from topbar menu button; single-column form grids (`minmax(0, 1fr)`).
- **Signature Specimen Strip**: Real-time `/api/v1/preview` conversion strip reacting to active `config` (`s2t`, `twp`, `s2tw`, `s2hk`, `t2s`), `no_punc`, and custom phrase input.

## Motion & States

- `150ms–240ms` transitions for mode switching, hover states, drawer slide, and stepped phase progress (`transition: width 240ms ease`), disabled cleanly under `prefers-reduced-motion: reduce`, with explicit `@media (forced-colors: active)` system fallbacks.
- Every interactive form control and job state covers default, hover, focus-visible (`2px solid #17324D`, or `#FFB010` inside the navy rail), disabled, uploading progress, queued, running, completed, failed, and empty states.
