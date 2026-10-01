# Chart recipes for a page you write (Step 4)

Copy-paste recipes for the charts a hand-written page most often needs: a KPI card with a delta,
horizontal bars, vertical bars, a line over time, a stacked bar, and a compact table. Each one is
a small plain function that takes rows exactly as `dashies.data` delivers them and returns
markup. There is no library to load and nothing to configure: paste the shared block once, paste
the recipes you use, and wire each one to a subscription.

**They exist because a hand-written page otherwise re-derives the same hundred-odd lines of
SVG scaling code for every chart**, and a first-time author should not have to. They are a starting point you own
and restyle, not a component library, so change anything - but keep the six properties below,
because each one is a rule of this path rather than a taste.

## What every recipe keeps

- **Nothing loads from outside the page.** No `<script src>`, no stylesheet, no font, no image
  URL. Every dashboard is served under a `sandbox allow-scripts` content security policy, which
  runs your script on an opaque origin with no storage and no session; `SKILL.md` rule 2 says
  your script never calls out, and its **Make it good** closes with inlining everything so the
  page depends on nothing that can change underneath it. A page whose chart code is inline
  renders the same in a year.
- **Responsive through `viewBox`.** Every SVG declares a `viewBox` and `preserveAspectRatio`,
  and the stylesheet gives it `width: 100%; height: auto`, so one drawing fits a phone and a
  wall. Text scales with it: `W` is the card width the 12px type is sized for, and 360 is
  about what a three-column grid gives a card on a desktop and what a phone gives one full
  width, so both read at roughly the size written. A wider card wants a wider `W`.
- **Every number drawn is a delivered value, in the order it was delivered.** The recipes lay out -
  a bar's length, a point's position, a colour - and never work a figure out, or reorder or cut the
  rows: no totals, no differences, no shares, no axis ticks the page invented, no sort, no top N, no
  threshold on a row - an order, a top N and a threshold are asked for with `sort`, `limit` and
  `having` on `dashies.data`. A KPI's delta is a `ratio` you declare in the spec and read off the row. A
  test on a number may colour something, as the KPI's delta takes its up or down colour, or hide it
  through a class, and never chooses text, a row or an order: no word, sign, unit or other glyph is
  written under an `if` on a number or picked by a ternary on one. A row is picked by a category
  value, or by anything worked out from one alone (`r.plan === 'pro'`, `r.region.startsWith('E')`, a
  date's month). To leave a value label off a bar too short to hold it, write the label every time
  and hide it with the `is-hidden` class the stylesheet below carries, chosen by the bar's own size:
  `'<text class="num' + (h < 14 ? ' is-hidden' : '') + '">'` in a string, or
  `t.classList.toggle('is-hidden', h < 14)` on an element. Never draw the label inside an `if` on
  the size, and never return early out of the row. That is `SKILL.md` rule 1, it is why a stacked
  column carries no total label, and **publish refuses a script that crosses it**, naming what to
  declare instead.
- **Numbers are formatted by the runtime.** `dashies.format(value, measure)` hands a delivered
  value back as the text to draw: the measure's `format` (`currency`, `percent`, `integer`,
  `decimal`, `compact`, or none), its `scale` for a `cents` or `points` measure, its own currency
  code and `decimals`, the way the runtime's own widgets draw it, and `-` for `null`. A value the
  runtime could not hand over as a Number arrives as its exact digits in a string and is drawn as
  those digits. `measure` is the entry on `ds.measures`, which the `measure()` helper below finds.
  No `toFixed`, no `toLocaleString`, no division: each works a new number out of the one you were
  handed, and publish refuses it.
- **Every string from the data is escaped.** A dimension value is text somebody typed into a
  source system. `esc()` wraps every one before it reaches `innerHTML`, so a value carrying `<`
  is drawn, never parsed.
- **Colours are custom properties.** One `:root` block carries the palette, one
  `prefers-color-scheme: dark` block overrides it, and every recipe refers to a variable. Retint
  the page by editing `:root`; the type stays legible in both schemes because the ink and the
  surface move together.

**The four states are handled once, outside the recipes, and so is the empty answer.** A recipe
is only ever called with a non-empty `rows` from a `ready` dataset. `notReady()` draws the
sentence for `pending`, `loading` and `error`, where `rows` is `null`; `draw()` adds the case
those three do not cover, a `ready` dataset carrying zero rows, which is the honest answer
whenever a filter matches nothing. **Keep both halves.** A recipe handed `null` throws, and one
that reads a particular row - the KPI reads the latest month - throws on `[]` too, and a throw
inside the callback costs the whole region rather than one card.

## The shared block, pasted once

The stylesheet. The four `--ch-s*` variables are tints of the one accent, for a stacked bar's
segments; everything else is neutral, per **Make it good** in `SKILL.md`.

```html
<style>
:root {
  --ch-ink: #111827;      --ch-muted: #6b7280;    --ch-rule: #e5e7eb;
  --ch-surface: #ffffff;  --ch-canvas: #f4f5f7;
  --ch-accent: #2563eb;   --ch-s2: #93c5fd;  --ch-s3: #1e3a8a;  --ch-s4: #bfdbfe;  --ch-s5: #60a5fa;
  --ch-up: #15803d;       --ch-down: #b91c1c;
  --ch-sans: Inter, system-ui, -apple-system, "Segoe UI", sans-serif;
  --ch-mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --ch-ink: #f3f4f6;    --ch-muted: #9ca3af;    --ch-rule: #374151;
    --ch-surface: #111827; --ch-canvas: #030712;
    --ch-accent: #60a5fa; --ch-s2: #1d4ed8;  --ch-s3: #bfdbfe;  --ch-s4: #1e3a8a;  --ch-s5: #93c5fd;
    --ch-up: #4ade80;     --ch-down: #f87171;
  }
}
body { margin: 0; background: var(--ch-canvas); color: var(--ch-ink); font: 14px/1.4 var(--ch-sans); }
/* `align-items: start` because the default `stretch` makes every card as tall as the tallest in
   its row, so one long table leaves its neighbours mostly empty space. */
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; padding: 16px; max-width: 1200px; margin: 0 auto; align-items: start; }
.ch { background: var(--ch-surface); border: 1px solid var(--ch-rule); border-radius: 8px; padding: 16px; min-width: 0; overflow-x: auto; }
.ch h2 { margin: 0 0 12px; font-size: 11px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: var(--ch-muted); }
.ch svg { display: block; width: 100%; height: auto; }
.ch text { font: 12px var(--ch-sans); fill: var(--ch-ink); }
.ch text.muted { fill: var(--ch-muted); }
.ch .num { font-family: var(--ch-mono); font-variant-numeric: tabular-nums; }
/* A label a bar is too short to hold keeps its text and is hidden by this class, never left undrawn. */
.ch .is-hidden { display: none; }
.ch .bar, .ch .dot, .ch .s1 { fill: var(--ch-accent); }
.ch .s2 { fill: var(--ch-s2); }  .ch .s3 { fill: var(--ch-s3); }  .ch .s4 { fill: var(--ch-s4); }  .ch .s5 { fill: var(--ch-s5); }
/* `fill` paints an SVG shape and does nothing to an HTML element, so the legend chips take the
   same colours through `background`. Both read the same variable, so one `:root` retints both. */
.ch .swatch.s1 { background: var(--ch-accent); }  .ch .swatch.s2 { background: var(--ch-s2); }
.ch .swatch.s3 { background: var(--ch-s3); }  .ch .swatch.s4 { background: var(--ch-s4); }
.ch .swatch.s5 { background: var(--ch-s5); }
.ch .rule { stroke: var(--ch-rule); stroke-width: 1; }
.ch .line { fill: none; stroke: var(--ch-accent); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.ch .state { margin: 0; color: var(--ch-muted); }
.kpi .value { font: 600 40px/1.1 var(--ch-mono); font-variant-numeric: tabular-nums; letter-spacing: -.02em; }
.kpi .delta { margin-top: 8px; color: var(--ch-muted); }
.kpi .up { color: var(--ch-up); }  .kpi .down { color: var(--ch-down); }
.ch table { width: 100%; border-collapse: collapse; }
.ch th { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--ch-rule); font-size: 11px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: var(--ch-muted); }
.ch td { padding: 6px 8px; border-bottom: 1px solid var(--ch-rule); }
.ch th.num, .ch td.num { text-align: right; }
.ch .legend { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 8px; font-size: 12px; color: var(--ch-muted); }
.ch .swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 6px; vertical-align: -1px; }
</style>
```

The helpers. Every recipe below calls these and `dashies.format`, and nothing else.

```js
// Every string from the data goes through this before it reaches innerHTML.
function esc(s) {
  return String(s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  });
}
// The entry on ds.measures for a key: what `dashies.format(value, measure)` formats a value with.
function measure(ds, key) {
  for (var i = 0; i < ds.measures.length; i++) if (ds.measures[i].key === key) return ds.measures[i];
  return null;
}
// A label trimmed to about `width` user units at roughly `per` units a character. The ellipsis
// is THREE of the characters the budget allows, so the cut is at `max - 3`: taking `max - 1` and
// appending it returns two characters MORE than the budget, which is a silent overrun of exactly
// the kind this pair exists to stop.
//
// APPROXIMATE, AND ONLY EVER ABOUT PROPORTIONS. A real glyph advance depends on the font and the
// characters - all-caps runs far wider than this assumes - so the estimate decides how much room a
// label is given, never whether it stays inside it. `capLabels` below is what guarantees that,
// and it measures rather than assuming.
function fit(s, width, per) {
  var max = Math.floor(width / per);
  return s.length <= max ? s : max < 4 ? s.slice(0, Math.max(1, max)) : s.slice(0, max - 3) + '...';
}
// THE EXACT BOUND, applied once after the markup is in the document. A page CAN measure its own
// text: `getComputedTextLength()` answers as soon as the element is in the DOM, before anything
// depends on it for layout. So a label that fits is left exactly as it is, and one that does not
// is compressed into its budget with `textLength`, which no font and no glyph set can defeat.
// Call it on any container you inserted a recipe into; `draw()` below does.
function capLabels(root) {
  var els = root.querySelectorAll('text[data-fit]');
  for (var i = 0; i < els.length; i++) {
    var el = els[i], budget = parseFloat(el.getAttribute('data-fit'));
    if (!(budget > 0)) continue;
    var w = 0;
    try { w = el.getComputedTextLength(); } catch (e) { continue; }
    if (w > budget) {
      el.setAttribute('textLength', budget);
      el.setAttribute('lengthAdjust', 'spacingAndGlyphs');
    }
  }
}
// A value as a LENGTH, for layout only. Never drawn as a number.
function num(v) {
  var n = v === null || v === undefined ? 0 : Number(v);
  return isFinite(n) ? n : 0;
}
// A dimension value as a label: '' for null, otherwise its text.
function label(v) { return v === null || v === undefined ? '' : String(v); }
// A date dimension value as the day it names. The runtime delivers it as the ISO day already;
// an instant in milliseconds becomes its UTC day, the same rule the runtime applies. An epoch
// outside the range a Date can hold DEGRADES rather than throwing, because `toISOString` throws
// on one where the runtime's own `getUTC*` does not, and a throw here costs the whole callback.
function day(v) {
  if (typeof v === 'number' && isFinite(v)) {
    try { return new Date(v).toISOString().slice(0, 10); } catch (e) { return String(v); }
  }
  return label(v);
}
// The three states that draw no numbers, as one sentence. '' when there are rows to draw.
function notReady(ds) {
  if (ds.status === 'ready') return '';
  var s = ds.status === 'pending' ? 'No data yet. It fills in after the first refresh.'
        : ds.status === 'loading' ? 'Updating...'
        : 'Could not load: ' + ds.error;
  return '<p class="state">' + esc(s) + '</p>';
}
```

## Wiring: one subscription per grain

One `dashies.data` call carries one grain per dataset, so a page that draws the same dataset by
month, by region and by channel subscribes three times, and each recipe is handed rows at the
grain it draws. The data block comes first, the marker after the markup, and the script last.
`draw()` is where every case that draws no numbers is handled: the sentence for `pending`,
`loading` and `error`, the same sentence for a `ready` dataset carrying zero rows, and otherwise
the recipe. It then calls `capLabels`, which is what makes a label's budget exact rather than
estimated.

```html
<script type="application/json" id="dashies-data">{}</script>
<main class="grid">
  <section class="ch" id="kpi"><h2>Revenue, latest month</h2><div class="body"></div></section>
  <section class="ch" id="trend"><h2>Revenue by month</h2><div class="body"></div></section>
  <section class="ch" id="regions"><h2>Revenue by region</h2><div class="body"></div></section>
  <section class="ch" id="channels"><h2>Orders by channel</h2><div class="body"></div></section>
  <section class="ch" id="mix"><h2>Revenue by month and region</h2><div class="body"></div></section>
  <section class="ch" id="detail"><h2>By region and channel</h2><div class="body"></div></section>
</main>
<script data-dashies-runtime></script>
<script>
// PASTE THE HELPERS AND THE RECIPES HERE

function draw(id, ds, render) {
  // `ready` WITH ZERO ROWS IS A REAL ANSWER, not a fifth state: any filter combination matching
  // nothing reaches it, and a shared link can open the page in it. A recipe that reads one
  // particular row (the KPI below reads the latest month) would throw on it, and a throw costs
  // the whole callback, so the guard is here rather than in each recipe.
  var rows = ds.status === 'ready' && ds.rows.length === 0 ? null : ds.rows;
  var el = document.querySelector('#' + id + ' .body');
  el.innerHTML = notReady(ds) || (rows ? render(rows) : '<p class="state">No rows.</p>');
  // Then bound every label that declared a budget, by MEASURING it now that it is in the
  // document. Without this the margins are only as good as the per-character estimate above.
  capLabels(el);
}
// By month: the trend, and the KPI reads the latest month off the same rows. A grain arrives in
// value order, so the months arrive oldest first and the latest is the last row CARRYING a month:
// a row whose month is null sorts after every dated one, so the last row outright can be the one
// with no date at all. Keeping the dated rows is a null test, which is a pick a page may make.
dashies.data(function (d) {
  var ds = d.sales;
  draw('trend', ds, function (rows) { return line(rows, 'month', 'revenue', measure(ds, 'revenue')); });
  draw('kpi', ds, function (rows) {
    var dated = rows.filter(function (r) { return r.month !== null && r.month !== undefined; });
    return dated.length ? kpi(ds, dated[dated.length - 1], 'revenue', 'change', 'prior_revenue', 'the month before')
      : '<p class="state">No dated rows.</p>';
  });
}, { sales: { by: ['month'] } });
dashies.data(function (d) {
  draw('regions', d.sales, function (rows) { return hbar(rows, 'region', 'revenue', measure(d.sales, 'revenue')); });
}, { sales: { by: ['region'] } });
dashies.data(function (d) {
  draw('channels', d.sales, function (rows) { return vbar(rows, 'channel', 'orders', measure(d.sales, 'orders')); });
}, { sales: { by: ['channel'] } });
dashies.data(function (d) {
  draw('mix', d.sales, function (rows) { return stacked(rows, 'month', 'region', 'revenue', measure(d.sales, 'revenue')); });
}, { sales: { by: ['month', 'region'] } });
dashies.data(function (d) {
  draw('detail', d.sales, function (rows) {
    return table(d.sales, rows, [
      { dim: 'region', label: 'Region' }, { dim: 'channel', label: 'Channel' },
      { measure: 'orders', label: 'Orders' }, { measure: 'revenue', label: 'Revenue' },
      { measure: 'aov', label: 'Avg order' }, { measure: 'discount_rate', label: 'Discount' },
    ]);
  });
}, { sales: { by: ['region', 'channel'] } });
</script>
```

The dataset that page reads declares `month` (a `date` dimension), `region` and `channel`, the
sum measures `revenue`, `orders`, `discount`, `prior_revenue` and `revenue_delta`, and three
ratios: `change` is `revenue_delta` over `prior_revenue`, `aov` is `revenue` over `orders`, and
`discount_rate` is `discount` over `revenue`. The delta on the KPI card and the percentage in the
table are those ratios, worked out by the runtime at every grain the page asks for - the page
reads them off the row and never divides.

## 1. KPI card with a delta

`row` is the row to read, `key` the hero measure, `deltaKey` the `ratio` you declared for the
change, and `compareKey` the comparison value drawn beside it. **The delta takes an up or down
colour and draws no arrow.** Comparing the delta with zero may choose a class, which colours a
value Dashies delivered; an arrow, a sign or a word is something a reader reads, and one a
comparison chose is a figure nothing checked, so publish refuses it. The sign is Dashies' to deliver with the
period change; until it does, a `metric` widget with `data-timeintel` draws the change with its
own arrow.

```js
function kpi(ds, row, key, deltaKey, compareKey, compareLabel) {
  var d = row[deltaKey];
  // A colour, never a glyph: a class may turn on a comparison with zero, and an arrow a reader
  // reads may not. A null delta takes neither.
  var tone = d === null || d === undefined ? '' : num(d) > 0 ? 'up' : num(d) < 0 ? 'down' : '';
  return '<div class="kpi"><div class="value">' + esc(dashies.format(row[key], measure(ds, key))) + '</div>' +
    '<div class="delta"><span class="' + tone + '">' + esc(dashies.format(d, measure(ds, deltaKey))) + '</span>' +
    ' vs ' + esc(dashies.format(row[compareKey], measure(ds, compareKey))) + ' ' + esc(compareLabel) + '</div></div>';
}
```

## 2. Horizontal bars

One bar per row, label on the left, value on the right, the longest bar the largest value.
**Both margins are sized from their own longest string**, the right from the formatted value and
the left from the dimension name, so neither end clips: a constant left margin cut the HEAD off a
long name, which is the half that says which row you are looking at. A name past the 150-unit cap
is trimmed with an ellipsis and carries its full text in a `<title>`, so the bars keep their room.
**The trim is an estimate and the BOUND is a measurement**, which is the pair that matters: an
all-caps name advances about 7.7 units a character against the 6.2 the estimate assumes, so
estimating alone cut the head off a label a second time. `capLabels` measures each one with
`getComputedTextLength()` after it is in the document and compresses only what is over budget.
Rows draw in the order Dashies delivers them, by value unless the dimension declares `domains`.
A page never sorts them: a ranking by a measure is asked for on the subscription, and arrives in
that order - `{ sales: { by: ['customer'], sort: 'revenue:desc', limit: 10 } }` hands this recipe
the ten largest, the largest first, and `other: true` adds `ds.other` for an "Other" bar drawn
after them. A negative value draws as an empty bar: signed data wants a zero line, which neither
bar recipe draws.

```js
function hbar(rows, dim, key, m) {
  var W = 360, H = 28, PAD = 8, LCAP = 150, max = 0, i, out = '', labels = [], names = [], L = PAD, R = PAD;
  for (i = 0; i < rows.length; i++) {
    max = Math.max(max, num(rows[i][key]));
    labels.push(dashies.format(rows[i][key], m));
    names.push(label(rows[i][dim]));
    // BOTH MARGINS ARE SIZED, and the left one is why: it used to be a constant, so a name longer
    // than it ran off the left edge of the viewBox and was cut there, taking the HEAD of the label
    // - the part that says which row this is. Capped, so one long name cannot eat the bars.
    R = Math.max(R, PAD + 7.5 * labels[i].length);            // 12px mono value, on the right
    L = Math.min(LCAP, Math.max(L, PAD + 6.2 * names[i].length));  // 12px sans name, on the left
  }
  for (i = 0; i < rows.length; i++) {
    var y = i * H, w = max > 0 ? Math.max(0, num(rows[i][key])) / max * (W - L - R) : 0;
    var name = fit(names[i], L - PAD, 6.2);
    out += '<text x="' + (L - PAD) + '" y="' + (y + 18) + '" text-anchor="end" class="muted" data-fit="' + (L - PAD) + '">' + esc(name) +
      (name === names[i] ? '' : '<title>' + esc(names[i]) + '</title>') + '</text>' +
      '<rect class="bar" x="' + L + '" y="' + (y + 6) + '" width="' + w + '" height="' + (H - 12) + '" rx="2"/>' +
      '<text x="' + (L + w + 8) + '" y="' + (y + 18) + '" class="num">' + esc(labels[i]) + '</text>';
  }
  return '<svg viewBox="0 0 ' + W + ' ' + Math.max(H, rows.length * H) + '" preserveAspectRatio="xMinYMin meet" role="img">' + out + '</svg>';
}
```

## 3. Vertical bars

One column per row, its value above it, its label beneath. **What decides whether the axis is
readable is the LABEL'S WIDTH against its own slot, `W / n`, never the column count**: three
columns of ordinary names collide where eight short ones do not. Each label is therefore trimmed
to its slot, bounded exactly by `capLabels` once it is in the document, and carries its full text
in a `<title>`. When the trimming starts eating the names,
that is the signal to ask for a grain with fewer members, or to use the horizontal recipe, whose
left margin grows with the name instead.

```js
function vbar(rows, dim, key, m) {
  var W = 360, H = 200, T = 24, B = 28, n = rows.length, max = 0, i, out = '';
  for (i = 0; i < n; i++) max = Math.max(max, num(rows[i][key]));
  var slot = n ? W / n : W, bw = slot * 0.6;
  for (i = 0; i < n; i++) {
    var h = max > 0 ? Math.max(0, num(rows[i][key])) / max * (H - T - B) : 0;
    var x = i * slot + (slot - bw) / 2, y = H - B - h, cx = i * slot + slot / 2;
    // A LABEL IS TRIMMED TO ITS OWN COLUMN'S SLOT. Centred and untrimmed, two ordinary names
    // overlap each other long before the column count looks unreasonable, and the end ones run
    // off the viewBox. The full text stays reachable in the <title>.
    var full = label(rows[i][dim]), name = fit(full, slot - 4, 6.2), budget = Math.max(1, slot - 4);
    out += '<rect class="bar" x="' + x + '" y="' + y + '" width="' + bw + '" height="' + h + '" rx="2"/>' +
      '<text x="' + cx + '" y="' + (y - 6) + '" text-anchor="middle" class="num">' + esc(dashies.format(rows[i][key], m)) + '</text>' +
      '<text x="' + cx + '" y="' + (H - 8) + '" text-anchor="middle" class="muted" data-fit="' + budget + '">' + esc(name) +
      (name === full ? '' : '<title>' + esc(full) + '</title>') + '</text>';
  }
  return '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid meet" role="img">' +
    '<line class="rule" x1="0" y1="' + (H - B) + '" x2="' + W + '" y2="' + (H - B) + '"/>' + out + '</svg>';
}
```

## 4. Line over time

`dim` is a `date` dimension. Dashies delivers a grain in value order, so a date dimension's rows
arrive oldest first and the line is drawn in the order it is handed: a page never sorts. On a
dashboard that reads a warehouse, and on an in-file dataset of records, a date arrives as its ISO
day, `YYYY-MM-DD`. **On the sample connection a dimension can instead arrive as whatever the
statement returned**, numbers staying numbers, which is why `day()` normalizes the axis labels
rather than trusting the type. The first and last days label the axis and the last point carries
its delivered value, which is every number the chart shows. **The highest point is not
labelled**: finding it means comparing the values, which publish refuses, so the largest is asked
for with a second subscription, `sort: '<measure>:desc', limit: 1`, whose one row is it. The scale's top and bottom are a `Math.max` and a
`Math.min`, which only scale the drawing. The baseline is zero, so a flat quarter looks flat
rather than stretched to fill the box.

```js
function line(rows, dim, key, m) {
  var W = 360, H = 180, L = 8, R = 8, T = 22, B = 24, i, n = rows.length;
  if (!n) return '<p class="state">No rows.</p>';
  var lo = 0, hi = 0;
  for (i = 0; i < n; i++) {
    hi = Math.max(hi, num(rows[i][key]));
    lo = Math.min(lo, num(rows[i][key]));
  }
  if (!(hi > lo)) hi = lo + 1;
  function sx(i) { return L + (n > 1 ? i / (n - 1) : 0.5) * (W - L - R); }
  function sy(v) { return T + (1 - (v - lo) / (hi - lo)) * (H - T - B); }
  var d = '', last = n - 1;
  for (i = 0; i < n; i++) d += (i ? ' L' : 'M') + sx(i).toFixed(1) + ' ' + sy(num(rows[i][key])).toFixed(1);
  var lx = sx(last), ly = sy(num(rows[last][key]));
  return '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid meet" role="img">' +
    '<line class="rule" x1="' + L + '" y1="' + (H - B) + '" x2="' + (W - R) + '" y2="' + (H - B) + '"/>' +
    '<path class="line" d="' + d + '"/>' +
    '<circle class="dot" cx="' + lx + '" cy="' + ly + '" r="3"/>' +
    '<text x="' + (lx - 6) + '" y="' + (ly < H / 2 ? ly + 16 : ly - 8) + '" text-anchor="end" class="num">' + esc(dashies.format(rows[last][key], m)) + '</text>' +
    '<text x="' + L + '" y="' + (H - 6) + '" class="muted">' + esc(day(rows[0][dim])) + '</text>' +
    '<text x="' + (W - R) + '" y="' + (H - 6) + '" text-anchor="end" class="muted">' + esc(day(rows[last][dim])) + '</text>' +
    '</svg>';
}
```

The `toFixed` calls above round coordinates, not values: a path attribute is geometry, and
nothing in it is drawn as a number.

## 5. Stacked bars

Rows are at the grain `[x, series]`. One column per `x` value, one segment per `series` value,
in the order each first appears; each segment carries its own delivered value in a `<title>`,
which a browser shows on hover. **The column's total is not printed.** It would be a number this
page worked out, so if the design wants it, subscribe a second time at `by: [x]` and draw that
delivered value over the column.

```js
function stacked(rows, xKey, sKey, key, m) {
  var W = 360, H = 200, T = 8, B = 28, xs = [], ss = [], cell = {}, i, s, x;
  for (i = 0; i < rows.length; i++) {
    x = day(rows[i][xKey]); s = label(rows[i][sKey]);
    if (xs.indexOf(x) < 0) xs.push(x);
    if (ss.indexOf(s) < 0) ss.push(s);
    cell[JSON.stringify([x, s])] = rows[i][key];
  }
  var max = 0, tall;
  for (i = 0; i < xs.length; i++) {
    for (tall = 0, s = 0; s < ss.length; s++) tall += Math.max(0, num(cell[JSON.stringify([xs[i], ss[s]])]));
    max = Math.max(max, tall);
  }
  var slot = xs.length ? W / xs.length : W, bw = slot * 0.64, out = '', legend = '';
  for (i = 0; i < xs.length; i++) {
    var y = H - B, cx = i * slot + slot / 2;
    for (s = 0; s < ss.length; s++) {
      var v = cell[JSON.stringify([xs[i], ss[s]])], h = max > 0 ? Math.max(0, num(v)) / max * (H - T - B) : 0;
      y -= h;
      out += '<rect class="s' + (s % 5 + 1) + '" x="' + (cx - bw / 2) + '" y="' + y + '" width="' + bw + '" height="' + h + '">' +
        '<title>' + esc(ss[s] + ', ' + xs[i] + ': ' + dashies.format(v, m)) + '</title></rect>';
    }
    if (i === 0 || i === xs.length - 1 || xs.length <= 6) {
      var t = xs[i].length === 10 && xs[i].charAt(4) === '-' ? xs[i].slice(0, 7) : xs[i];
      var anchor = xs.length <= 6 ? 'middle' : i === 0 ? 'start' : 'end';
      var ax = anchor === 'start' ? cx - bw / 2 : anchor === 'end' ? cx + bw / 2 : cx;
      out += '<text x="' + ax + '" y="' + (H - 8) + '" text-anchor="' + anchor + '" class="muted">' + esc(t) + '</text>';
    }
  }
  for (s = 0; s < ss.length; s++) legend += '<span><i class="swatch s' + (s % 5 + 1) + '"></i>' + esc(ss[s]) + '</span>';
  return '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid meet" role="img">' +
    '<line class="rule" x1="0" y1="' + (H - B) + '" x2="' + W + '" y2="' + (H - B) + '"/>' + out + '</svg>' +
    '<div class="legend">' + legend + '</div>';
}
```

The legend chips read the same palette variables the segments do, through `background` rather
than `fill`: `fill` paints an SVG shape and has no effect on an HTML element, so a chip styled
only by the segment classes renders transparent. Both halves point at one `:root`, so retinting
it retints both. Six or more series share colours: bound the series dimension
with `domains` so the stack stays readable, which is also what keeps a dashboard on the sample
connection cheap.

## 6. Compact table

`cols` is the columns to draw, in order, each saying what it draws: `{ dim: 'region' }` is a
dimension, drawn as text, and `{ measure: 'orders' }` a measure, right-aligned and formatted
through `dashies.format`; `label` is its header. **The column names its kind** because publish
tells a dimension from a measure by the name a cell is read through, and a key that is one on some
columns and the other on the rest reads as neither: publish refuses a value drawn that way, since
it could be a measure shown raw. Hairline rules, a quiet uppercase header and tabular figures come
from the stylesheet, so nothing here reads as a browser default.

```js
function table(ds, rows, cols) {
  var head = '', body = '', i, c;
  for (c = 0; c < cols.length; c++) {
    head += '<th' + (cols[c].measure ? ' class="num"' : '') + '>' + esc(cols[c].label) + '</th>';
  }
  for (i = 0; i < rows.length; i++) {
    body += '<tr>';
    for (c = 0; c < cols.length; c++) {
      var col = cols[c];
      body += col.measure
        ? '<td class="num">' + esc(dashies.format(rows[i][col.measure], measure(ds, col.measure))) + '</td>'
        : '<td>' + esc(label(rows[i][col.dim])) + '</td>';
    }
    body += '</tr>';
  }
  return '<table><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table>';
}
```

A table is for reading, so ask for the columns a person will look at and a grain that gives it
a few dozen rows; past that, the `by` you subscribe with is the lever, not a scrollbar. A table
wider than its card scrolls inside the card (`.ch` has `overflow-x: auto`) rather than pushing the
page wide. **Six columns already overflow a card in a three-column grid, on a desktop and not only
on a phone**, so the last one is off-screen until a reader scrolls: the honest fix at any width is
fewer columns, or a card given the full row.

## What is deliberately not here

- **Axis ticks the page works out.** A "nice" axis of 0, 25k, 50k is a set of numbers nothing
  checked. The recipes label delivered values instead - the bar's own value and the line's last
  point - which is more legible on a small chart anyway.
- **A delta, a share or a total computed from the rows.** Declare a `ratio` for a change or a
  share, a measure for anything else, and `by` for a coarser grain; `SKILL.md` carries why under
  "Two rules, and both are about correctness rather than taste".
- **A tooltip layer, animation, or a zoom.** Each is a fine addition to a page you own; none of
  them is what a first page needs, and every one is a place a number can be computed by accident.
- **A sort, a top N, a threshold or a highest point worked out in the page.** Each chooses or
  orders rows by comparing values, which publish refuses. Dashies delivers a grain in value order
  (or in the member order a dimension's `domains` declares), and in the order a subscription asks
  with `sort`, cut by its `limit` and restricted by its `having`, each row carrying its
  `__rank_pos`; a table or chart widget sorts and cuts with `data-sort` and `data-limit`.
- **Text a number decides**: a word such as "High" or "Above target", a sign, a unit, any glyph,
  whether a ternary picks it or it is written under an `if` on the number. A test on a number may
  colour something, or hide it through a class; text a reader sees is a delivered value drawn
  through `dashies.format`, or a dimension the dataset's SQL works out (a `CASE` that names the
  band), drawn like any other label.
