# Styling the page and its widgets (Step 4)

The runtime draws every widget your page marks with `data-dash` (`references/widgets.md`), and styles
what it draws with stylesheets of its own. This file is everything those stylesheets expose to your
CSS: the custom properties they read, the classes they style, and the states they key on. It is the
runtime's own style contract, held to the runtime by a check that fails when a token is dropped or a
class renamed, so the lists below are complete.

**Write the full token block on every page, with every value set to the style you are designing to.**
A token you leave out draws at the runtime's default, which is how a page in somebody's brand ends up
with one widget in Dashies' own blue. The block is under **The full token block**; copy it whole and
change the values.

## Your CSS outranks the runtime's

Every stylesheet the runtime injects sits in one cascade layer, `drt`, which it declares first in
`<head>`. A rule you write outside any layer outranks every layer, and a layer of your own is declared
after `drt`, so it outranks it too. **Your CSS beats every runtime rule, whatever its specificity or
position, with no `!important`.** The runtime writes no `!important` of its own. The one thing a rule
of yours beats only with `!important` is an inline style, and the few colours the runtime writes inline
are under **What no token or class reaches**.

Two ways to restyle, and both work:

- **Set the tokens** on your `:root`. Every colour and every font the runtime's stylesheets use comes
  from them.
- **Write rules against the classes.** `.drt-table td { padding: 4px 8px; }` changes every table's cell
  padding.

**A generic rule reaches the widgets too.** A rule such as `svg text { ... }`, `table td { ... }` or
`button { ... }` wins over the runtime's class rules, so it restyles every widget as well as your own
markup. If you mean it for your own markup only, scope it: `.my-chart svg text`, not `svg text`. The
recipes in `references/charts.md` scope theirs under `.ch` for exactly this reason.

**Fonts load only from inside the page.** A published dashboard reaches nothing outside Dashies, so a
web font from a font service never arrives. Use a system font stack, or a font file the user hands you
embedded as a `data:` URI in your own `@font-face` - never one you type. The defaults below name
`'Inter'`, which draws only where the viewer has it installed.

Two older-browser cases, which draw the defaults rather than your tokens:

- **No cascade layers** (Chrome before 99, Firefox before 97, Safari before 15.4): the runtime's
  stylesheets go in unlayered, and there only `!important` beats them.
- **No `color-mix()`** (Chrome before 111, Firefox before 113, Safari before 16.2): focus rings,
  shadows, the detail dialog's backdrop and the fill under an area chart keep their default colours,
  whatever tokens you set.

## Tokens

Set them on `:root`. A default is what the runtime draws when your page sets nothing, so **set every
one**, and nothing is left at a default by omission.

### Accent

| Token | Default | What it paints |
|---|---|---|
| `--drt-blue` | `#2563eb` | Bars, lines, points, gauge fills, focus borders and the pending bar, and, mixed with transparency, every focus ring and the fill under an area chart. |
| `--drt-blue-700` | `#1d4ed8` | A bar or mark on hover, the View detail button on hover, and the selected mark of a cross-filter. |
| `--drt-blue-soft` | `#eff6ff` | Nothing the runtime draws. Defined for your own CSS. |
| `--drt-accent` | `currentColor` | The drill-down's breadcrumb links, and a row's descend control on hover. The default is the surrounding text colour. |
| `--drt-on-blue` | `#fff` | Text and marks drawn on the accent: the treemap's labels, the check mark in a selected option, and a heatmap cell's text when that contrasts more with its fill than `--drt-ink`. |

### Text

| Token | Default | What it paints |
|---|---|---|
| `--drt-ink` | `#0f172a` | Primary text (table cells, figures, dialog text), a waterfall's total, a gauge's target, and a heatmap cell's text when that contrasts more with its fill than `--drt-on-blue`. |
| `--drt-muted` | `#475569` | Nothing the runtime draws. Defined for your own CSS. |
| `--drt-subtle` | `#64748b` | Labels, captions, legends, the notes under a widget, a waterfall's decreases, and the arrow on the filter, date-range, sort and top-N dropdowns. It is held to `4.5:1` contrast, because those notes are text a viewer has to read. |
| `--drt-faint` | `#94a3b8` | Axis numbers, separators, disabled controls and control borders on hover. |

### Surfaces and lines

| Token | Default | What it paints |
|---|---|---|
| `--drt-surface` | `#fff` | Card, control, table and dialog backgrounds, and the hairlines between scatter points and treemap rectangles. |
| `--drt-sunken` | `#f8fafc` | Table headers, row hover, totals rows and pressed controls, and with `--drt-line` the hatch on a heatmap cell whose value cannot be shown. |
| `--drt-line` | `#e2e8f0` | Hairline borders, every loading placeholder except a chart's, and with `--drt-sunken` the hatch on a heatmap cell whose value cannot be shown. |
| `--drt-line-strong` | `#cbd5e1` | Control borders, chart baselines and totals rules. |
| `--drt-grid` | `#eef2f6` | Chart gridlines, table row rules, gauge tracks and the chart's loading placeholder. |
| `--drt-shadow` | `#0f172a` | The colour every shadow and the detail dialog's backdrop are mixed from. It is not `--drt-ink`, so a dark page can lighten its text and keep dark shadows. |

### Type and motion

| Token | Default | What it paints |
|---|---|---|
| `--drt-sans` | `'Inter',ui-sans-serif,system-ui,-apple-system,sans-serif` | All prose and labels, including the notices on a page with page code. |
| `--drt-mono` | `ui-monospace,'JetBrains Mono','SF Mono',Menlo,monospace` | Every figure, with tabular numerals. |
| `--drt-ease` | `ease` | The timing of the runtime's transitions and entrance animations. The loading pulses and the pending bar keep their own. |
| `--drt-chevron` | in [the full token block](#the-full-token-block): a 16px chevron stroked in `#64748b` | The SHAPE of the arrow on the filter, date-range, sort and top-N dropdowns: the arrow is `--drt-subtle` masked by this image (`.drt-select-wrap::after`), so its own stroke colour does not show. Set it to your own `url("data:image/svg+xml;...")` to change the shape. A browser with no CSS masks draws the image itself, stroke and all. |

### Series

Five slots for the series of a multi-series chart and the slices of a pie or donut. Each default
clears `3:1` on white, the bar a mark has to clear, and the set is colourblind-checked as a group.
Five is also the ceiling on slices, because a slice's identity is its colour.

| Token | Default | What it paints |
|---|---|---|
| `--drt-series0` | `#2563eb` | The first series or slice. The same blue as `--drt-blue`, so set both. |
| `--drt-series1` | `#0d9488` | The second. |
| `--drt-series2` | `#d97706` | The third. |
| `--drt-series3` | `#db2777` | The fourth. |
| `--drt-series4` | `#65a30d` | The fifth. |

### Heatmap and matrix scales

A heatmap, and a matrix with `data-color`, fill each cell with one step of these scales and write its
text in `--drt-ink` or `--drt-on-blue`, whichever contrasts more with the fill. Each default step
clears `4.5:1` with the ink it takes. The runtime reads these tokens when it draws a heatmap, so a
token you change later reaches the cells at the next draw.

| Token | Default | What it paints |
|---|---|---|
| `--drt-heat-1` | `#dbeafe` | The lowest step of a heatmap's scale (`data-color="heat"`, a heatmap's default). Keep it clear of your page's surface: the lowest step still has to read as painted. |
| `--drt-heat-2` | `#bfdbfe` | The second step. |
| `--drt-heat-3` | `#93c5fd` | The third step. |
| `--drt-heat-4` | `#60a5fa` | The fourth step. |
| `--drt-heat-5` | `#3b82f6` | The fifth step. |
| `--drt-heat-6` | `#1d4ed8` | The highest step. |
| `--drt-diverging-1` | `#b91c1c` | The most negative step of a diverging scale (`data-color="diverging"`). |
| `--drt-diverging-2` | `#fca5a5` | The middle negative step. |
| `--drt-diverging-3` | `#fee2e2` | The least negative step. |
| `--drt-diverging-4` | `#f1f5f9` | Zero. |
| `--drt-diverging-5` | `#dbeafe` | The least positive step. |
| `--drt-diverging-6` | `#93c5fd` | The middle positive step. |
| `--drt-diverging-7` | `#1d4ed8` | The most positive step. |

### Notices on a page with page code

The runtime draws these only on a page whose own script calls `dashies.data`.

| Token | Default | What it paints |
|---|---|---|
| `--drt-warn-ink` | `#7c2d12` | The text of the notice that says a result is partial. |
| `--drt-warn-soft` | `#fff7ed` | Its background. |
| `--drt-warn-line` | `#fed7aa` | Its border. |
| `--drt-error-ink` | `#991b1b` | The text of the notice that says one of the page's own callbacks threw. |
| `--drt-error-soft` | `#fef2f2` | Its background. |
| `--drt-error-line` | `#fecaca` | Its border. |

### Status bars

The bars fixed to the bottom of a page: the date a dashboard's data is from, when a refresh could not
bring in more, and the note on an archived version's preview. They follow the viewer's colour scheme,
so their three colours are the only tokens with a dark default, which applies under
`prefers-color-scheme: dark`. A value you set applies in both schemes.

| Token | Default | What it paints |
|---|---|---|
| `--drt-status-ink` | `#334155`, dark `#cbd5e1` | The bar's text. |
| `--drt-status-soft` | `#f1f5f9`, dark `#1e293b` | Its background. |
| `--drt-status-line` | `#cbd5e1`, dark `#334155` | Its top border. |
| `--drt-status-font` | `system-ui,-apple-system,"Segoe UI",Roboto,sans-serif` | Its text, which is the viewer's system face by default rather than `--drt-sans`. |

## The full token block

Every token at its default. Copy it into your page's `<style>` and change the values to the style you
are designing to. If your page has a dark scheme, write the block again inside your own
`prefers-color-scheme: dark` rule with that scheme's values.

```css
:root {
  --drt-blue: #2563eb;
  --drt-blue-700: #1d4ed8;
  --drt-blue-soft: #eff6ff;
  --drt-accent: currentColor;
  --drt-on-blue: #fff;
  --drt-ink: #0f172a;
  --drt-muted: #475569;
  --drt-subtle: #64748b;
  --drt-faint: #94a3b8;
  --drt-surface: #fff;
  --drt-sunken: #f8fafc;
  --drt-line: #e2e8f0;
  --drt-line-strong: #cbd5e1;
  --drt-grid: #eef2f6;
  --drt-shadow: #0f172a;
  --drt-sans: 'Inter', ui-sans-serif, system-ui, -apple-system, sans-serif;
  --drt-mono: ui-monospace, 'JetBrains Mono', 'SF Mono', Menlo, monospace;
  --drt-ease: ease;
  --drt-chevron: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 16 16' fill='none' stroke='%2364748b' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'><path d='M4 6l4 4 4-4'/></svg>");
  --drt-series0: #2563eb;
  --drt-series1: #0d9488;
  --drt-series2: #d97706;
  --drt-series3: #db2777;
  --drt-series4: #65a30d;
  --drt-warn-ink: #7c2d12;
  --drt-warn-soft: #fff7ed;
  --drt-warn-line: #fed7aa;
  --drt-error-ink: #991b1b;
  --drt-error-soft: #fef2f2;
  --drt-error-line: #fecaca;
  --drt-heat-1: #dbeafe;
  --drt-heat-2: #bfdbfe;
  --drt-heat-3: #93c5fd;
  --drt-heat-4: #60a5fa;
  --drt-heat-5: #3b82f6;
  --drt-heat-6: #1d4ed8;
  --drt-diverging-1: #b91c1c;
  --drt-diverging-2: #fca5a5;
  --drt-diverging-3: #fee2e2;
  --drt-diverging-4: #f1f5f9;
  --drt-diverging-5: #dbeafe;
  --drt-diverging-6: #93c5fd;
  --drt-diverging-7: #1d4ed8;
  --drt-status-ink: #334155;
  --drt-status-soft: #f1f5f9;
  --drt-status-line: #cbd5e1;
  --drt-status-font: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
```

**Your page's own palette comes from the same style.** The recipes in `references/charts.md` read
their own `--ch-*` properties; set those from the same design, or point them at these tokens
(`--ch-accent: var(--drt-blue);`), so a chart your script draws and a widget beside it match.

## Classes

Every class the runtime's stylesheets style, and every class it puts on what it draws. Each is yours
to target.

### Every widget

| Class | What it is |
|---|---|
| `.drt` | On every widget the runtime draws: sets its font to `--drt-sans` and its text to `--drt-ink`. |
| `.drt-empty` | The sentence a widget shows when nothing matches the current filters. |
| `.drt-empty-action` | The one button that can sit under that sentence. |
| `.drt-refusal` | The sentence a widget shows when it will not draw a number it cannot show exactly. |
| `.drt-fade` | The short fade some widgets play as they redraw. |
| `.drt-sr` | Text for screen readers only, such as the loading announcement. |

### Figures you mark up yourself

The runtime styles these and never adds them: put them on your own markup to get the runtime's figure
look.

| Class | What it is |
|---|---|
| `.drt-kpi` | A figure card. |
| `.drt-kpi-label` | Its label. |
| `.drt-kpi-value` | Its figure. |
| `.drt-num` | Any figure, in the mono face with tabular numerals. |

### Filters and viewer controls

| Class | What it is |
|---|---|
| `.drt-filter` | A filter widget. |
| `.drt-filter-label` | Its label. |
| `.drt-select` | The filter, date-range, sort and top-N dropdowns. Their arrow is drawn by `.drt-select-wrap`. The View detail's sort is `.drt-drill-sort` and keeps the browser's own arrow. |
| `.drt-select-wrap` | The box every one of those dropdowns sits in. Its `::after` is the arrow: `--drt-chevron`'s shape in `--drt-subtle`. The arrow is placed on this box, not on the dropdown, so space or size a dropdown through `.drt-select-wrap` or its parent rather than through `.drt-select`'s margins, and hide or replace the arrow through `.drt-select-wrap::after` or `--drt-chevron`: a `background-image` on `.drt-select` no longer reaches it. |
| `.drt-mc-wrap` | A filter that takes several values. |
| `.drt-mc-trigger` | Its button. |
| `.drt-mc-summary` | The button's text. |
| `.drt-mc-chev` | The button's arrow, in `--drt-subtle`. |
| `.drt-mc-panel` | The open list. |
| `.drt-mc-head` | The list's top row, which holds Clear. |
| `.drt-mc-list` | The options. |
| `.drt-mc-opt` | One option. |
| `.drt-mc-box` | Its checkbox. |
| `.drt-mc-check` | The check mark in a selected box. |
| `.drt-mc-txt` | The option's text. |
| `.drt-rg` | A date-range filter. |
| `.drt-rg-field` | One end of the range. |
| `.drt-rg-cap` | Its From or To caption. |
| `.drt-rg-sel` | Its dropdown. |
| `.drt-rg-sep` | The separator between the two ends. |
| `.drt-fx-clear` | The Clear action on a filter. |
| `.drt-fx-note` | The sentence a filter shows when it has no values or too many. |
| `.drt-ctl` | The sort and top-N bar above a table or chart. |
| `.drt-ctl-group` | One control in it. |
| `.drt-ctl-lab` | Its label. |
| `.drt-ctl-sel` | Its dropdown. |
| `.drt-reset` | The floating Reset button, shown once a viewer has changed a control. |
| `.drt-reset-ico` | Its icon. |
| `.drt-reset-txt` | Its label. |

### Tables

| Class | What it is |
|---|---|
| `.drt-table-wrap` | A table's scrolling frame. |
| `.drt-table` | The table. |
| `.drt-col-num` | A numeric column's header and cells. |
| `.drt-tbl-note` | The note under a table whose rows were cut. |

### Charts

| Class | What it is |
|---|---|
| `.drt-chart` | A chart widget. |
| `.drt-axis` | An axis's numbers. |
| `.drt-cat` | A category label. |
| `.drt-bar` | A bar. |
| `.drt-line` | A line. |
| `.drt-area` | The fill under an area chart, `--drt-blue` at 10%. |
| `.drt-dot` | A point on a line. |
| `.drt-gridline` | A gridline. |
| `.drt-baseline` | The zero line. |
| `.drt-xf` | A mark that filters the page when clicked. |
| `.drt-xf-sel` | The selected mark. |
| `.drt-xf-dim` | The other marks while one is selected. |
| `.drt-legend` | A legend. |
| `.drt-legend-item` | One entry. |
| `.drt-legend-sw` | Its swatch. |
| `.drt-legend-lab` | Its label. |
| `.drt-ms-line` | A series line on a multi-series chart. |
| `.drt-ms-bar` | A series bar. |
| `.drt-ms-dot` | A series point. |
| `.drt-ms-endlab` | The label at the end of a series line. |

A chart measures its labels after it draws. When your CSS gives one another size or another face
(`.drt-axis { font-size: 15px; }`, say) and it runs past the chart's edge, the chart grows its padding
on that side and draws once more, so the label sits inside. A label still in the runtime's own font is
left as it is.

### Stacked and combo charts

| Class | What it is |
|---|---|
| `.drt-sc-seg` | A stacked segment. |
| `.drt-sc-total` | The total above a stacked column. |
| `.drt-sc-axis2` | A combo chart's second axis. |
| `.drt-sc-note` | The note under the chart. |

### Matrix and heatmap

| Class | What it is |
|---|---|
| `.drt-mx` | The matrix. |
| `.drt-mx-corner` | Its corner cell. |
| `.drt-mx-total` | A total. |
| `.drt-mx-blank` | An intersection with no data. |
| `.drt-mx-note` | The note under the matrix. |
| `.drt-hm-cell` | A heatmap cell. |
| `.drt-hm-void` | A cell with no value. |
| `.drt-hm-legend` | The heatmap's legend. |
| `.drt-hm-ramp` | The legend's colour ramp. |
| `.drt-hm-sw` | One step of the ramp. |
| `.drt-hm-end` | A value at either end of the ramp. |

### Pie, donut and gauge

| Class | What it is |
|---|---|
| `.drt-rad` | The chart. |
| `.drt-rad-wrap` | The chart and its key. |
| `.drt-rad-fig` | The chart's half. |
| `.drt-rad-key` | The key's half. |
| `.drt-rad-item` | A row of the key. |
| `.drt-rad-val` | That row's value. |
| `.drt-rad-center` | The figure at the centre of a donut or gauge. |
| `.drt-rad-caption` | The caption under it. |
| `.drt-rad-scale` | A gauge's scale ends. |
| `.drt-rad-track` | A gauge's track. |
| `.drt-rad-fill` | A gauge's filled arc. |
| `.drt-rad-target` | A gauge's target mark. |
| `.drt-rad-note` | The note under the chart. |

### Scatter, treemap, waterfall and funnel

| Class | What it is |
|---|---|
| `.drt-sc-pt` | A scatter point. |
| `.drt-sc-lab` | A scatter point's label. |
| `.drt-tm-rect` | A treemap rectangle. |
| `.drt-tm-key` | Its label. |
| `.drt-tm-val` | Its value. |
| `.drt-wf-bar` | A waterfall step that rises. |
| `.drt-wf-down` | A step that falls. |
| `.drt-wf-total` | The total. |
| `.drt-wf-link` | The dashed line between steps. |
| `.drt-fn-bar` | A funnel stage. |
| `.drt-fn-empty` | A stage with no value. |
| `.drt-an-note` | The note under any of these. |

### Drill down

| Class | What it is |
|---|---|
| `.drt-dq` | The drill-down table. |
| `.drt-dq-crumbs` | The breadcrumb row. |
| `.drt-dq-crumb` | A breadcrumb link, in `--drt-accent`. |
| `.drt-dq-cur` | The current level. |
| `.drt-dq-sep` | A separator. |
| `.drt-dq-into` | A row's descend control, in `--drt-accent` on hover. |
| `.drt-dq-lab` | A row label that does not descend. |
| `.drt-dq-other` | The Other row. |
| `.drt-dq-note` | The note under the table. |

### View detail

| Class | What it is |
|---|---|
| `.drt-drill-btn` | The View detail button. |
| `.drt-drill-overlay` | The dialog's backdrop, `--drt-shadow` at 44%. |
| `.drt-drill-panel` | The dialog. |
| `.drt-drill-head` | Its header. |
| `.drt-drill-title` | Its title. |
| `.drt-drill-sort` | Its sort dropdown. |
| `.drt-drill-close` | Its close button. |
| `.drt-drill-note` | Its note line. |
| `.drt-drill-body` | Its scrolling body. |
| `.drt-drill-empty` | What it shows when there are no records. |

### Lines under a widget

| Class | What it is |
|---|---|
| `.drt-asof` | "as of" and a time, on a widget whose data is not the latest. |
| `.drt-scope` | The line naming a filter that does not apply to the widget. |
| `.drt-ti` | The line that says what a period change compares. |
| `.drt-retry` | The retry button on a refusal a viewer can act on. |

### Loading

| Class | What it is |
|---|---|
| `.drt-skel` | A placeholder block. |
| `.drt-skel-anim` | A placeholder that pulses. |
| `.drt-skel-value` | A figure's placeholder. |
| `.drt-skel-label` | A label's placeholder. |
| `.drt-skel-control` | A control's placeholder. |
| `.drt-skel-block` | A chart's placeholder. |
| `.drt-skel-table` | A table's placeholder. |
| `.drt-skel-row` | One row of it. |

### Page notices and bars

| Class | What it is |
|---|---|
| `.drt-author-bar` | The thin bar across the top while a page with page code is waiting for data. |
| `.drt-author-truncated` | The notice that a result is partial. |
| `.drt-author-thrown` | The notice that one of the page's own callbacks threw. |
| `.drt-capacity-bar` | The bar that gives the date a dashboard's data is from. |
| `.drt-archived-version-bar` | The bar on an archived version's preview. |

## States

The attributes the runtime's stylesheets key on. Each can be part of your selectors too.

| Attribute | Where | What it means |
|---|---|---|
| `aria-busy` | a widget | `true` while its data is on the way. |
| `data-drt-served` | a widget | Its numbers come from Dashies when the page is opened, so a change of filter waits on the network. |
| `data-dash` | a widget | Its role. |
| `aria-expanded` | `.drt-mc-trigger` | `true` while its list is open. |
| `aria-selected` | `.drt-mc-opt` | `true` on a selected option. |
| `disabled` | `.drt-retry`, `.drt-fx-clear` | The control cannot be used right now. |
| `hidden` | `.drt-reset` | No control has been changed, so there is nothing to reset. |
| `data-dashies-pending` | `<html>` | A dataset the page's code asked for is on the way. |
| `data-dashies-truncated` | `<html>` | A result the page's code was handed is partial. |
| `data-dashies-indicators` | `<html>` | Set it to `none` to hide the pending bar and the partial-result notice. |

## What no token or class reaches

- **Inline colours.** The runtime writes some colours inline, from tokens: a multi-series chart's marks
  and a pie or donut's slices from `--drt-seriesN`, and a heatmap's cells, its legend swatches and its
  hatch from the heatmap tokens, `--drt-ink`, `--drt-on-blue`, `--drt-sunken` and `--drt-line` (a matrix
  with `data-color` draws them too). A class rule without `!important` loses to an inline style, so set
  the tokens.
- **`--drt-bottom-bars`.** The runtime sets it on `<html>` while the archived-version bar is up, to lift
  the Reset button above both bars. It is layout state, not a token to set.

## Check it worked

1. **Set the whole token block to the style and read the page back.** Nothing the runtime draws should
   keep a default colour.
2. **Tab through the controls.** Each focus ring should be your accent.
3. **Write one class rule without `!important`**, such as a new padding on `.drt-table td`, and confirm
   it applies.
