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
- **Every number drawn is a delivered value.** The recipes lay out - a bar's length, a point's
  position - and never work a figure out: no totals, no differences, no shares, no axis ticks
  the page invented. A KPI's delta is a `ratio` you declare in the spec and read off the row.
  That is `SKILL.md` rule 1, and it is why a stacked column carries no total label.
- **Numbers are formatted from what the runtime hands over.** Each entry on `ds.measures`
  carries a `format` (`currency`, `percent`, `integer`, `decimal`, `compact`, or none) and,
  for a `cents` or `points` measure, a `scale` to apply. The `text()` helper reads those and
  formats a Number through `Intl.NumberFormat` with the options a managed tile uses for a measure
  that declares no `decimals`. A value the runtime could not hand over as a Number arrives as its
  exact digits in a string and is drawn as it came, except that a declared `scale` shifts its
  decimal point rather than dividing, which would round it. `null` draws as `-`. No `toFixed`, no
  `toLocaleString`, nothing that throws on `null`.
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

The helpers. Every recipe below calls these and nothing else.

```js
// Every string from the data goes through this before it reaches innerHTML.
function esc(s) {
  return String(s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  });
}
// The entry on ds.measures for a key: its `format`, and its `scale` when one was handed over.
function measure(ds, key) {
  for (var i = 0; i < ds.measures.length; i++) if (ds.measures[i].key === key) return ds.measures[i];
  return null;
}
var CURRENCY = 'USD';  // a measure entry carries no currency code, so name yours once.
// A digit string divided by its scale, EXACTLY. A value arrives as a string because the runtime
// could not hand it over as a Number, so `Number()` would round away the digits the string exists
// to keep: shift the decimal point instead, which is what the runtime's own `decimalStr` does.
//
// IT TREATS `scale` AS A POWER OF TEN, counting its digits rather than dividing by it, which is
// what makes the shift exact. That is safe because the only divisor the compiler ever emits is
// 100, for `cents` and `points` (`resolveFormat`), and there is no way to declare another. Were a
// non-power-of-ten ever emitted this would be wrong rather than imprecise - `shiftPoint('12345',
// 50)` gives 1234.5 where the true value is 246.9 - so it is tied to that fact, not to a range
// check that would read as though other values were expected.
function shiftPoint(s, scale) {
  var neg = s.charAt(0) === '-', d = neg ? s.slice(1) : s, dot = d.indexOf('.');
  var whole = dot < 0 ? d : d.slice(0, dot), frac = dot < 0 ? '' : d.slice(dot + 1);
  if (!/^[0-9]+$/.test(whole + frac)) return s;
  var all = whole + frac, cut = whole.length - (String(scale).length - 1);
  while (cut < 1) { all = '0' + all; cut++; }
  return (neg ? '-' : '') + all.slice(0, cut) + '.' + all.slice(cut);
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
// One delivered value -> the text to draw. null -> '-'. A value the runtime could not hand over
// as a Number arrives as a digit string: it is drawn as it came, except that a declared `scale`
// shifts its decimal point, because Number() would round away the digits the string exists to
// keep. A Number is divided by that same scale (cents / points) and then formatted from the
// measure's `format`, with the options a managed tile uses for a measure declaring no `decimals`.
// Never throws: a throw inside the callback blanks the whole region.
function text(v, m) {
  if (v === null || v === undefined) return '-';
  // THE SCALE HAS TO BE APPLIED ON THIS BRANCH TOO. A `cents` or `points` measure arrives
  // undivided, and dropping the divisor here would draw 100x the true figure with nothing on the
  // page saying so - the worst failure this product has, reached through the one path where a
  // scaled measure is deliverable at all.
  if (typeof v !== 'number') return m && m.scale ? shiftPoint(String(v), m.scale) : String(v);
  if (m && m.scale) v = v / m.scale;
  var f = m && m.format;
  var o = f === 'percent' ? { style: 'percent', maximumFractionDigits: 1 }
        : f === 'currency' ? { style: 'currency', currency: CURRENCY, maximumFractionDigits: 0 }
        : f === 'integer' ? { maximumFractionDigits: 0 }
        : f === 'compact' ? { notation: 'compact', maximumFractionDigits: 1 }
        : f === 'decimal' ? { minimumFractionDigits: 2, maximumFractionDigits: 2 }
        : {};
  try { return new Intl.NumberFormat(undefined, o).format(v); } catch (e) { return String(v); }
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
// By month: the trend, and the KPI reads the latest month off the same rows.
dashies.data(function (d) {
  var ds = d.sales;
  draw('trend', ds, function (rows) { return line(rows, 'month', 'revenue', measure(ds, 'revenue')); });
  draw('kpi', ds, function (rows) {
    var latest = rows.slice().sort(function (a, b) { return day(a.month) < day(b.month) ? 1 : -1; })[0];
    return kpi(ds, latest, 'revenue', 'change', 'prior_revenue', 'the month before');
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
      { key: 'region', label: 'Region' }, { key: 'channel', label: 'Channel' },
      { key: 'orders', label: 'Orders' }, { key: 'revenue', label: 'Revenue' },
      { key: 'aov', label: 'Avg order' }, { key: 'discount_rate', label: 'Discount' },
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
change, and `compareKey` the comparison value drawn beside it. The arrow's direction is the
only thing decided here, by comparing the delivered delta with zero.

```js
function kpi(ds, row, key, deltaKey, compareKey, compareLabel) {
  var d = row[deltaKey];
  var dir = d === null || d === undefined ? '' : num(d) > 0 ? 'up' : num(d) < 0 ? 'down' : '';
  var arrow = dir === 'up' ? '&#8593; ' : dir === 'down' ? '&#8595; ' : '';
  return '<div class="kpi"><div class="value">' + esc(text(row[key], measure(ds, key))) + '</div>' +
    '<div class="delta"><span class="' + dir + '">' + arrow + esc(text(d, measure(ds, deltaKey))) + '</span>' +
    ' vs ' + esc(text(row[compareKey], measure(ds, compareKey))) + ' ' + esc(compareLabel) + '</div></div>';
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
Rows draw in the order they arrive; sort them first if you want a ranking. A negative value draws
as an empty bar: signed data wants a zero line, which neither bar recipe draws.

```js
function hbar(rows, dim, key, m) {
  var W = 360, H = 28, PAD = 8, LCAP = 150, max = 0, i, out = '', labels = [], names = [], L = PAD, R = PAD;
  for (i = 0; i < rows.length; i++) {
    max = Math.max(max, num(rows[i][key]));
    labels.push(text(rows[i][key], m));
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
      '<text x="' + cx + '" y="' + (y - 6) + '" text-anchor="middle" class="num">' + esc(text(rows[i][key], m)) + '</text>' +
      '<text x="' + cx + '" y="' + (H - 8) + '" text-anchor="middle" class="muted" data-fit="' + budget + '">' + esc(name) +
      (name === full ? '' : '<title>' + esc(full) + '</title>') + '</text>';
  }
  return '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid meet" role="img">' +
    '<line class="rule" x1="0" y1="' + (H - B) + '" x2="' + W + '" y2="' + (H - B) + '"/>' + out + '</svg>';
}
```

## 4. Line over time

`dim` is a `date` dimension. On a dashboard that reads a warehouse, and on an in-file dataset of
records, the runtime delivers a date as its ISO day, `YYYY-MM-DD`, so sorting by that string is
sorting by date. **On the sample connection a dimension can instead arrive as whatever the
statement returned**, numbers staying numbers, which is why `day()` normalizes rather than
trusting the type and why the sort below goes through it. The first and last days label the axis; the highest
point and the last point carry their delivered values, which is every number the chart shows.
The baseline is zero, so a flat quarter looks flat rather than stretched to fill the box.

```js
function line(rows, dim, key, m) {
  var W = 360, H = 180, L = 8, R = 8, T = 22, B = 24, i;
  var pts = rows.slice().sort(function (a, b) { return day(a[dim]) < day(b[dim]) ? -1 : day(a[dim]) > day(b[dim]) ? 1 : 0; });
  var lo = Infinity, hi = -Infinity, top = 0;
  for (i = 0; i < pts.length; i++) {
    var v = num(pts[i][key]);
    if (v > hi) { hi = v; top = i; }
    if (v < lo) lo = v;
  }
  lo = Math.min(0, lo);
  if (!(hi > lo)) hi = lo + 1;
  function sx(i) { return L + (pts.length > 1 ? i / (pts.length - 1) : 0.5) * (W - L - R); }
  function sy(v) { return T + (1 - (v - lo) / (hi - lo)) * (H - T - B); }
  var d = '', last = pts.length - 1;
  for (i = 0; i < pts.length; i++) d += (i ? ' L' : 'M') + sx(i).toFixed(1) + ' ' + sy(num(pts[i][key])).toFixed(1);
  if (!pts.length) return '<p class="state">No rows.</p>';
  var lx = sx(last), ly = sy(num(pts[last][key])), tx = sx(top), ty = sy(hi);
  return '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid meet" role="img">' +
    '<line class="rule" x1="' + L + '" y1="' + (H - B) + '" x2="' + (W - R) + '" y2="' + (H - B) + '"/>' +
    '<path class="line" d="' + d + '"/>' +
    '<circle class="dot" cx="' + tx + '" cy="' + ty + '" r="3"/>' +
    '<text x="' + tx + '" y="' + (ty - 8) + '" text-anchor="' + (top > last / 2 ? 'end' : 'start') + '" class="num">' + esc(text(pts[top][key], m)) + '</text>' +
    (top === last ? '' : '<circle class="dot" cx="' + lx + '" cy="' + ly + '" r="3"/>' +
      '<text x="' + (lx - 6) + '" y="' + (ly < H / 2 ? ly + 16 : ly - 8) + '" text-anchor="end" class="num">' + esc(text(pts[last][key], m)) + '</text>') +
    '<text x="' + L + '" y="' + (H - 6) + '" class="muted">' + esc(day(pts[0][dim])) + '</text>' +
    '<text x="' + (W - R) + '" y="' + (H - 6) + '" text-anchor="end" class="muted">' + esc(day(pts[last][dim])) + '</text>' +
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
        '<title>' + esc(ss[s] + ', ' + xs[i] + ': ' + text(v, m)) + '</title></rect>';
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

`cols` is the columns to draw, in order. A column that names a measure is right-aligned and
formatted through `text()`; any other column is a dimension, drawn as text. Hairline rules, a
quiet uppercase header and tabular figures come from the stylesheet, so nothing here reads as a
browser default.

```js
function table(ds, rows, cols) {
  var head = '', body = '', i, c;
  for (c = 0; c < cols.length; c++) {
    head += '<th' + (measure(ds, cols[c].key) ? ' class="num"' : '') + '>' + esc(cols[c].label || cols[c].key) + '</th>';
  }
  for (i = 0; i < rows.length; i++) {
    body += '<tr>';
    for (c = 0; c < cols.length; c++) {
      var m = measure(ds, cols[c].key), v = rows[i][cols[c].key];
      body += m ? '<td class="num">' + esc(text(v, m)) + '</td>' : '<td>' + esc(label(v)) + '</td>';
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
  checked. The recipes label delivered values instead - the bar's own value, the highest and the
  last point - which is more legible on a small chart anyway.
- **A delta, a share or a total computed from the rows.** Declare a `ratio` for a change or a
  share, a measure for anything else, and `by` for a coarser grain; `SKILL.md` carries why under
  "Two rules, and both are about correctness rather than taste".
- **A tooltip layer, animation, or a zoom.** Each is a fine addition to a page you own; none of
  them is what a first page needs, and every one is a place a number can be computed by accident.
- **A currency code on the measure entry, and a declared `decimals`.** Neither reaches your
  script: a measure entry carries `format` and `scale` and stops. That is why `text()` reads the
  page-level `CURRENCY`, and it is why a `unit` declaring `decimals: 2` draws at each format's
  default precision here while a managed tile of the same measure shows the two places. Set the
  precision in `text()` if you need it, and format per column on a page mixing currencies.
