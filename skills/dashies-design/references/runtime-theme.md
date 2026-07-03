# Retinting the Dashies runtime

The inlined runtime (`runtime.js`) draws every data widget - charts, tables,
filter `<select>`s, and the default KPI card - from CSS custom properties it
declares on `:root`, with its component styles scoped under `.drt-*` classes. So
the entire visual theme of the runtime is reachable from your own `<style>`: you
redefine the tokens, and everything retints. This file is the exhaustive map.

## The whole surface at a glance

- **~15 tokens** on `:root` control all colors, borders, surfaces, and fonts.
  Override them to retint.
- **2 colors are hardcoded** (not tokenized): the area-chart fill and the select
  focus ring. Override those two classes directly.
- That is the complete surface. Nothing else needs chasing.

## Why `!important` (the cascade gotcha)

The runtime creates its `<style>` and appends it to `<head>` **at boot**, after
your static head styles. Custom-property declarations of equal specificity
resolve by source order, so a plain `:root { --drt-blue: ... }` in your head is
*overwritten* by the runtime's later `:root`. Two ways to win:

- **`!important` on the token** (recommended - simple, order-independent). An
  important custom-property declaration beats a non-important one whatever the
  order. The runtime declares its tokens without `!important`, so yours win.
- Higher specificity (`html:root { ... }`, 0-1-1 beats `:root` 0-1-0). Works, but
  `!important` is clearer. Do not rely on a bare `html { ... }` (0-0-1) - it
  *loses* to the runtime's `:root`.

The two hardcoded class overrides (`.drt-area`, `.drt-select:focus-visible`) also
need `!important` (or higher specificity) for the same reason.

## Token map

Every token, its default, and what it paints. Override the ones you need; setting
all of them gives a fully coherent retint.

| Token | Default | Paints |
|---|---|---|
| `--drt-blue` | `#2563eb` | **The accent.** Bar fill, line stroke, dot fill, select focus border. The one brand color. |
| `--drt-blue-700` | `#1d4ed8` | Darker accent: bar/line hover. Use a shade ~15% darker than the accent. |
| `--drt-blue-soft` | `#eff6ff` | Faint accent wash (available for accent-tinted surfaces). |
| `--drt-ink` | `#0f172a` | Primary text: KPI values, table cells, body. Your near-black. Keep it genuinely dark for contrast. |
| `--drt-muted` | `#475569` | Secondary text. |
| `--drt-subtle` | `#64748b` | Labels + quiet text: KPI labels, filter labels, table headers, chart category labels. |
| `--drt-faint` | `#94a3b8` | Faintest text: chart axis ticks. |
| `--drt-line` | `#e2e8f0` | Hairline borders: card, table wrap, header separators. |
| `--drt-line-strong` | `#cbd5e1` | Stronger 1px: select border, chart baseline. |
| `--drt-sunken` | `#f8fafc` | Quiet inset fill: table head row, row hover. |
| `--drt-surface` | `#fff` | Card/control surface: KPI card, table wrap, select background. |
| `--drt-grid` | `#eef2f6` | Chart gridlines and table row separators. Keep it very light. |
| `--drt-sans` | `'Inter', ui-sans-serif, system-ui, ...` | UI font for widgets. Set a CSP-safe system stack (no web fonts). |
| `--drt-mono` | `ui-monospace, 'JetBrains Mono', ...` | Figures font (tabular). Keep it mono for aligned numbers. |
| `--drt-ease` | `ease` | Re-render fade easing. Rarely worth changing. |

## The two hardcoded overrides

These colors are literal `rgba(37,99,235,...)` in the runtime, so token overrides
do not reach them. Add both:

```css
/* area-chart fill (default rgba(37,99,235,.10)) */
.drt-area { fill: color-mix(in srgb, var(--drt-blue) 12%, transparent) !important; }
/* select focus ring (default rgba(37,99,235,.18)) */
.drt-select:focus-visible {
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--drt-blue) 22%, transparent) !important;
}
```

`color-mix` (Chrome 111+, Safari 16.2+, Firefox 113+) ties both to the accent
automatically. If you need to support older engines, use a static rgba of the
brand instead, e.g. `fill: rgba(99,91,255,.12) !important;`.

## Light retint scaffold (copy, then swap values)

```css
:root {
  --drt-blue:        #635bff !important;
  --drt-blue-700:    #4b45d6 !important;
  --drt-blue-soft:   #f0efff !important;
  --drt-ink:         #0a1636 !important;
  --drt-muted:       #45507a !important;
  --drt-subtle:      #6b769c !important;
  --drt-faint:       #9aa2be !important;
  --drt-surface:     #ffffff !important;
  --drt-sunken:      #f7f8fc !important;
  --drt-line:        #e7e9f3 !important;
  --drt-line-strong: #ced2e6 !important;
  --drt-grid:        #eef0f8 !important;
  --drt-sans: ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif !important;
  --drt-mono: ui-monospace, 'SF Mono', 'JetBrains Mono', Menlo, monospace !important;
}
.drt-area { fill: color-mix(in srgb, var(--drt-blue) 12%, transparent) !important; }
.drt-select:focus-visible {
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--drt-blue) 22%, transparent) !important;
}
```

## Dark retint scaffold

For dark-first brands. The runtime is light by default, so a dark theme means
inverting the surface/ink tokens (dark surfaces, light text) and dropping the
grid/line to low-contrast dark values. Keep the accent bright enough to read on
dark. Also set your own `<body>` background to match `--drt-surface` or a slightly
darker canvas behind the cards.

```css
:root {
  --drt-blue:        #7c74ff !important;  /* brighten the accent for dark bg */
  --drt-blue-700:    #9c95ff !important;  /* hover = lighter, not darker, on dark */
  --drt-blue-soft:   #1b1e3a !important;
  --drt-ink:         #e9ecf5 !important;  /* light text                       */
  --drt-muted:       #a6adc8 !important;
  --drt-subtle:      #7b83a3 !important;
  --drt-faint:       #5b6284 !important;
  --drt-surface:     #12141f !important;  /* card surface (dark)              */
  --drt-sunken:      #0c0e17 !important;  /* inset darker than the card       */
  --drt-line:        #262a3d !important;
  --drt-line-strong: #363b54 !important;
  --drt-grid:        #1e2233 !important;
  --drt-sans: ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif !important;
  --drt-mono: ui-monospace, 'SF Mono', 'JetBrains Mono', Menlo, monospace !important;
}
.drt-area { fill: color-mix(in srgb, var(--drt-blue) 18%, transparent) !important; }
.drt-select:focus-visible {
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--drt-blue) 30%, transparent) !important;
}
body { background: #0c0e17; }  /* canvas behind the cards */
```

To adapt to the viewer's OS preference instead of committing to dark, wrap the
dark tokens in `@media (prefers-color-scheme: dark) { :root { ... } }` and keep
the light block as the default. Only do this if your chrome CSS also adapts;
half-dark (dark widgets, light chrome) looks broken.

## Keep the dashboard valid while theming

- **Never edit or move `<script id="dashies-data">`.** The refresh cron finds and
  rewrites it by id; styling belongs in `<head>` and your markup only.
- **Keep charts runtime-rendered on refreshable dashboards.** Retint them; do not
  swap them for static SVG the cron cannot refresh.
- **Do not script-replace `document.body`.** The serve layer appends a "Powered by
  Dashies" badge as the last child; filling slots and adding `<head>` styles is
  safe, wholesale body replacement is not.

## A note on stability

These token and class names are the current runtime's theming surface (contract
v1). They are stable in practice, but they are the runtime's internals, not a
frozen public API. If a dashboard you are theming inlines a runtime whose
`<style>` uses different names, read that inlined `<style>` and match the names
you find there - the *technique* (override tokens with `!important`, plus the two
hardcoded spots) is unchanged.
