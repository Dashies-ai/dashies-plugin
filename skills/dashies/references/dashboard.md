# Reference: the escape hatches + the legacy hand-authored path

Part of the `dashies` skill. **This is NOT the primary authoring path anymore** - a
refreshable dashboard is authored by writing a spec (`references/spec.md`, Step 4) and the
server compiles the HTML + island + manifest for you. Load this reference only for the two
things the spec's managed `tiles` cannot express on its own:

1. **A `custom` tile's body** (spec escape hatch 1): when a `type: custom` tile ships `html`/
   `js`, the data-island shape below + the sandbox CSP tell you what a custom tile's script
   can read and do. The spec still owns the datasets/manifest; you are only writing the tile's
   inner render.
2. **A whole-look body** (spec escape hatch 2, `#555`-guarded): a fully bespoke dashboard body
   instead of `tiles`. Since v1.1 this has a spec-native form - `look: { html }` in the SAME
   spec that declares `datasets`/`source` (mutually exclusive with `tiles`/`theme`/`layout`;
   see `references/spec.md`) - where the compiler still compiles the manifest and SEEDS it
   live, and only splices the seeded island into your body's existing `#dashies-data` element.
   There is also still an older, fully non-spec form: hand-author the body AND its
   `source_config` manifest yourself and publish with `publish_dashboard`'s `body` +
   `source_config` (NOT `spec` at all) - reach for that only when you need to bypass the spec
   format entirely. Either form forfeits the spec's compile-time guarantees for the markup
   itself (you become responsible for the `data-dash` <-> island <-> manifest consistency the
   compiler otherwise enforces from `tiles`); the publish-time consistency gate (`#555`) still
   rejects an obvious mismatch in both. To convert an EXISTING non-spec dashboard into a
   `look`-mode spec instead of hand-writing one, use the `derive_dashboard_spec` MCP tool (see
   Step 7 in `SKILL.md`).

Everything below is the depth for those two cases: the self-contained HTML shape, the
`data-dash` bindings, the data island, the serve-time runtime marker, the sandbox CSP, and the
single-manifest `source_config` (v1 / v3 / v2) that the fully non-spec `body` + `source_config`
publish still needs. For an ordinary dashboard, do NOT hand-write any of this - write the spec
instead. The full source-of-truth, `web/dashboard-runtime/CONTRACT.md`, is maintainer depth for
the monorepo, not required reading here.

## The HTML: markup + island + runtime marker

A refreshable dashboard is one self-contained HTML file with three parts in the
`<body>`: your marked-up content, the data island, then the runtime marker Dashies
fills on serve.

```html
<!doctype html>
<html lang="en">
  <head> <!-- your page <title> and CSS --> </head>
  <body>
    <!-- 1. your markup, with data-dash slots -->
    ...
    <!-- 2. the data island (the cube) -->
    <script type="application/json" id="dashies-data"> { ...spec... } </script>
    <!-- 3. the runtime marker - Dashies fills this on serve -->
    <script data-dashies-runtime></script>
  </body>
</html>
```

### Mark up elements with `data-dash`

The runtime fills only elements carrying a `data-dash` attribute; it never replaces
your body, so you own all layout and chrome. The common roles (full tables in
CONTRACT.md):

- **`metric`** - one KPI number. `data-measure` + optional `data-agg` (see the caveat
  below - on a `cube` only `sum` re-aggregates correctly) + `data-format`; the value lands
  in the first descendant `[data-dash-value]`. Ratio mode: `data-num` + `data-den` renders
  `sum(num)/sum(den)` - this is how you show averages and rates (add
  `data-num-scope`/`data-den-scope="all"` for percent-of-total).
- **`filter`** - a dimension slicer. `data-dim="<key>"` renders a `<select>` of that
  dimension's values plus "All"; filters compose with AND. (Add `data-multi` for a
  multi-select or `data-range` for a date range - see Viewer controls below.)
- **`chart`** - a sober SVG chart. `data-type` (`bar` default, `hbar`, `line`,
  `area`), `data-x="<dimension key>"`, `data-measure="<measure key>"`, optional
  `data-sort` / `data-limit` / `data-height`. (Add `data-controls` for viewer sort/top-N,
  `data-xfilter` for chart cross-filter, or `data-measures`/`data-series` for multi-series
  - see Viewer controls below.)
- **`table`** - the cube as a table. Optional `data-columns`, `data-group`,
  `data-sort="col:desc"`, `data-limit`. (Add `data-controls="sort,limit"` + `data-tile`
  for viewer sort/top-N - see Viewer controls below.)
- **`updated-at`** - the freshness stamp, rendered as relative time (`8 hours ago`),
  or absolute with `data-format="absolute"`.

**`data-agg` on a `cube` is restricted to `sum` / `min` / `max`.** `data-agg` overrides a tile's
aggregation, but on a `cube` dataset it re-aggregates the PRE-AGGREGATED cells, not raw rows -
so only operations that compose over partitions give the same answer the source rows would.
Anything else is **rejected at publish** and renders **UNAVAILABLE (`-`)** at runtime, on metric
tiles, charts and tables alike. It is not a style preference: `data-agg="avg"` returns the mean
of the group TOTALS, which live displayed `550.0000` where the true per-row average was
`10.8911` (50x). `count` over cells can only mean "number of groups"; `distinct` is exact only
when the distinct key is a dimension at the resolving grain, which collapsed cells cannot offer.

- **For a true average on a cube, use a ratio.** Declare a count measure next to the sum measure
  and bind them as `ratio: { num: <the sum measure>, den: <the count measure> }` (in raw markup,
  `data-num` + `data-den`). That is exactly sum divided by count over the currently-filtered
  cube - the true weighted mean over the underlying rows - and it stays exact under every
  filter. Dashies will not infer the denominator for you: a cube measure carries no source
  column, so the only count it can hold is `count(*)`, and `sum(x) / count(*)` is not `avg(x)`
  when `x` has NULLs.
- **For an exact distinct count / median / percentile,** declare the measure with that `agg` on
  a **`lattice`** (exact per single-select filter) or a **`hybrid`** / **`rows`** dataset, which
  recompute it exactly, rather than overriding a cube measure.
- **`data-agg="avg_of_groups"`** renders the mean of the cells deliberately, under a name that
  says so. Use it only when the aggregate rows ARE the population you mean to average.

(`data-agg` is NOT gated on a `rows` dataset - there it runs real SQL over the raw rows, so
`avg` / `median` / `count_distinct` recompute correctly.)

**On a `lattice` or `hybrid`, `data-agg` must AGREE with the measure's declared agg.** A lattice
cell holds exactly ONE precomputed value per measure - the exact answer for that measure's
declared agg at that filter state - so there is no second aggregate in the cell to compute.
Naming a different agg is **rejected at publish** and renders **UNAVAILABLE** at runtime
(previously it was accepted and silently dropped, so `data-agg="max"` on a `sum` measure showed
the SUM labelled "max"). Repeating the declared agg is a harmless no-op. **To get a different
aggregate, declare a SECOND measure with that `agg`** - the lattice precomputes it exactly for
every filter state - and point the tile at that measure. This is the normal authoring move, and
it is what you should reach for instead of `data-agg` on any pre-aggregated dataset.

Formats (`data-format`, or a measure's `format`): `currency`, `percent` (expects a
0..1 ratio - do not pre-multiply by 100), `decimal`, `integer`, `compact`, or omit
for a thousands-separated number. Options: `data-decimals`, `data-currency`.

### Viewer controls + interactions (v4, additive)

Beyond the static roles above, a v4 tile can carry **interaction** attributes that let the
VIEWER slice, sort, cross-filter, drill, and compare - no model, no re-publish. Every one is
**additive**: a tile without it renders exactly as before, and a v1/v2/v3 dashboard is
byte-identical without them (these are wired only on the v4 runtime path). Three properties
hold for all of them, so you can emit them and trust the result:

- **Never-wrong.** The runtime resolves each control EXACTLY at the current filter state (via
  the same per-mode math the static numbers use), or shows an honest "unavailable" / "updating"
  - it never renders an approximate or wrong number.
- **A11y ships with the runtime.** Keyboard operation, screen-reader labels, focus management,
  and WCAG-AA contrast are built into every control. You add the attribute; you do not build
  the affordance.
- **Shareable state.** A viewer's filters / sort / cross-filter selection are written into the
  URL hash, so a sliced view survives reload and can be shared as a link.

**Multi-select filter** - `data-multi` on a `filter` tile renders a checkbox dropdown (instead
of the single `<select>`) over the same dimension's values, so the viewer picks several at once
(hash `region=us,eu`). Use it on a **low-cardinality** dim - the same bounded dims a
`cube`/`lattice` uses. Pairs naturally with a `hybrid` dataset (the mode built for exact
non-additive metrics under multi-select).
```html
<div data-dash="filter" data-dataset="sales" data-dim="region" data-multi></div>
```

**Date-range filter** - `data-range` on a `filter` tile over a **date** dimension renders a
two-ended From / To range over that dim's buckets (inclusive, hash `month=2026-01..2026-06`).
Date dims only; on a non-date dim it falls back to the single-select.
```html
<div data-dash="filter" data-dataset="sales" data-dim="month" data-range></div>
```

**Viewer sort + top-N** - `data-controls="sort,limit"` on a `chart` or `table` tile adds a
small toolbar the viewer uses to reorder and truncate the ALREADY-resolved rows (a VIEW
operation - it never changes a number). **`data-tile="<id>"` is required** alongside
`data-controls` (a short unique id per tile; it keys the view in the hash). `sort` and `limit`
are independent - list either or both.
```html
<div data-dash="table" data-dataset="sales" data-controls="sort,limit" data-tile="top-regions"></div>
```
Do **not** put `sort` on a chart whose `data-x` is a **date** dimension - a time series is
inherently chronological, so the runtime suppresses the sort control there (top-N still
applies). `sort,limit` on a category-axis chart, or `limit` alone anywhere, is fine.

**Chart cross-filter** - `data-xfilter` on a `chart` tile makes clicking a bar toggle that
bar's `data-x` value into the GLOBAL filter state (the same state the `filter` tiles read and
write), so a chart doubles as a slicer that stays in sync with the filters. It maps on **`bar` /
`hbar`** charts only - the viewer clicks a bar, so on a `line` / `area` chart there is nothing to
click and the runtime silently no-ops it (put `data-xfilter` on a bar chart). **Single-series
charts only**, and **mutually exclusive with `data-measures`/`data-series`** (a multi-series
chart is not a cross-filter source) - never put both on one tile.
```html
<div data-dash="chart" data-dataset="sales" data-x="region" data-measure="revenue" data-xfilter></div>
```

**Drill-through to detail** - `data-drill="<dataset>"` on any tile adds a "View detail" trigger
that opens a dialog of ROW-LEVEL detail from the named dataset, filtered to the current state.
The **target MUST be a rows-bearing dataset** - `mode: "rows"`, or a `hybrid`'s row slice; point
it at a `cube`/`lattice` and there are no rows to show. It degrades honestly (an empty state
when nothing matches; a "windowed" note when the slice is a `rows_window`).
```html
<div data-dash="metric" data-dataset="kpis" data-measure="orders" data-drill="order_detail"><span data-dash-value>-</span></div>
```

**Multi-series charts** - a `chart` over a **`cube`** dataset can plot several series on one
shared-axis chart, with an automatic legend: `data-measures="m1,m2"` (2-4 measures at the same
grain, one series per measure) **XOR** `data-series="<dim>"` (one `data-measure` split into one
series per value of a **low-cardinality** dim, capped at 5). Overlaid lines / grouped bars -
**no stacking, no dual-axis** (two measures of different scale share the y-axis, so prefer
measures of similar magnitude or split into two charts).
```html
<div data-dash="chart" data-dataset="kpis" data-x="month" data-measures="revenue,orders" data-type="line"></div>
<div data-dash="chart" data-dataset="kpis" data-x="month" data-measure="revenue" data-series="plan"></div>
```
Multi-series is **CUBE datasets only** in v4.0 - route a multi-series chart to a `cube` dataset
(a `lattice`/`hybrid`/`rows` multi-series chart renders an honest "unavailable"). `data-x` is
required; `data-measures` needs 2-4 known measures; `data-series` needs a real dim with <=5
values. Never combine with `data-xfilter`, and do not add a viewer `sort` control to it (it
does not honor viewer sort/top-N in v4.0, so the toolbar is suppressed).

**Percent-of-total ("of all")** - on a ratio `metric` (`data-num` + `data-den`), add
`data-num-scope="all"` and/or `data-den-scope="all"` to evaluate that operand over the
dataset's UNFILTERED total instead of the filtered slice - i.e. this slice's share of the
whole. (The un-scoped operand still follows the active filters.)
```html
<div data-dash="metric" data-dataset="sales" data-num="revenue" data-den="revenue" data-den-scope="all" data-format="percent"><span data-dash-value>-</span></div>
```

**Binding consistency - keep the markup, the manifest, and the cube SQL in lockstep.** Every
attribute that names a dim, measure, or dataset must name one that actually exists: the bound
name has to be **declared in that dataset's manifest** (`dimensions[].key` / `measures[].key`)
**and** be a column the `cube_sql` emits. The static invariant already ties the manifest to the
SQL ("dimension keys + measure keys == every column the SELECT returns"); these interaction
bindings must name into that same set. The name-bearing bindings include (not limited to):

- `data-dataset`, and `data-drill`'s target -> a real **dataset** key in the island (drill's must also be rows-bearing).
- `data-dim` (filter / multi / range), `data-x` (chart axis), and `data-series` -> a declared **dimension** key.
- `data-measure`, each key in `data-measures`, and `data-num` / `data-den` -> a declared **measure** key.
- On a `table`: each key in `data-columns`, the `data-group` dimension, and the author `data-sort` column -> a declared **dimension** / **measure** key (a `data-group` on a missing key silently collapses every row into one bogus "undefined" group).

You hand-write the cube SQL, the manifest declarations, and this markup as three separate things,
so they drift: a typo or a renamed column leaves a binding pointing at nothing.

**The server now REFUSES this at publish, and you should let it.** A refreshable HTML publish
runs a cross-namespace consistency gate that resolves every binding against the island and the
executed cube, on the final post-seed bytes and **before any R2 or database write**, so a
mismatch persists nothing and returns a pointered error naming the binding - for a missing
measure it says the tile "would render a fake 0 (or an empty tile) that never refreshes - fix
the binding or declare the measure". **Do not hand-roll your own binding checker; check the
publish error instead.** Two exemptions, and they are the cases where you are still on your
own: a **static** dashboard (no `source_config` - there is nothing to cross-check against) and
a **custom-renderer** dashboard are both skipped by the validator.

What follows is what the runtime does when a bad binding is NOT caught - which is now only the
two exempt cases above, and is why the gate exists. A wrong *shape* renders an
honest "unavailable", but a wrong *name* has nothing to resolve against, so the runtime
**overwrites** the slot with a wrong or empty value: most dangerously a **mis-summed `0`** (a
metric sums a missing measure key as 0, so a typo'd `data-measure` shows `0` / `$0`), and
otherwise a bare `-`, an empty control, a table mis-grouped under one "undefined" bucket, or an
honest empty tile for an unknown dataset - but **never the real number, and never a signal that
the binding failed**. A fabricated `0` is worse than a blank: the author sees a number and assumes
it resolved; it publishes clean and looks right while the value is silently wrong, which is the
worst way a dashboard can fail. **Self-check to get the error EARLIER, not because you are
unprotected:** on a refreshable publish the gate above is the safety net and it fails closed, so
this is about a faster loop, not about catching what the server misses. For every binding above,
confirm the name is declared in that dataset's manifest `dimensions`/`measures`, and that the cube
actually produces it with `validate_cube_sql`. Read its output columns per mode: for a `cube` / `lattice`
they are the dim keys + measure keys (the SQL aliases each measure to its key), but for a `rows`
dataset they are the raw selected columns - a dim key (a rows dim must be a real column) and each
measure's underlying `column`, which can differ from its `key` (measure `customers` over column
`customer_id`). So verify a rows measure by its `column`, not its `key`; every markup binding still
names the declared manifest **key**.

**Never emit a shape the runtime renders unavailable or wrong** (each is guarded, but author it
right - do not lean on the guard):

- Multi-series (`data-measures`/`data-series`) -> a **`cube`** dataset only.
- `data-xfilter` is **mutually exclusive** with `data-measures`/`data-series` (never both), and maps on **`bar` / `hbar`** charts only (silent no-op on `line`/`area`).
- No viewer `sort` on a **date-axis** chart; and no `data-controls` on a multi-series chart.
- `data-drill` target MUST be a **rows-bearing** dataset (`rows`, or a `hybrid` row slice).
- `data-controls` REQUIRES `data-tile`; `data-multi` and `data-series` want **low-cardinality** dims.
- `data-measures` is 2-4 measures at the same grain; `data-series` is one dim with <=5 values.

### Write the data island

Exactly one `<script type="application/json" id="dashies-data">` per dashboard, and
it must be valid JSON (no comments, no trailing commas) - the refresh finds it by
that id and rewrites its contents wholesale.

```json
{
  "version": 1,
  "updated_at": "2026-06-27T09:15:00Z",
  "dimensions": [
    { "key": "month", "label": "Month", "type": "date" },
    { "key": "region", "label": "Region" },
    { "key": "plan", "label": "Plan" }
  ],
  "measures": [
    { "key": "revenue", "label": "Revenue", "agg": "sum", "format": "currency" },
    { "key": "orders", "label": "Orders", "agg": "sum", "format": "integer" }
  ],
  "format": { "currency": { "code": "USD", "decimals": 0 } },
  "cube": [
    { "month": "2026-06", "region": "EMEA", "plan": "Pro", "revenue": 7594, "orders": 329 }
  ]
}
```

- `version` is `1` for the additive cube (`3` for a grain-compiler `GROUP BY CUBE`
  lattice - see Manifest v3; `2` for row-level - see Manifest v2).
- `updated_at` is when you computed the cube (ISO 8601); Dashies overwrites it on refresh.
  Render it from the full ISO timestamp, never a date-only slice, or the "refreshed
  N ago" stamp anchors to midnight and reads stale.
- Each `cube` row is one `GROUP BY` result - a flat object keyed by the dimension +
  measure keys. Paste in the rows `validate_cube_sql` returned.
- `dimensions` / `measures` / `format` must be **byte-identical to the manifest**,
  since Dashies rebuilds the island on refresh from `manifest + fresh rows`.

### Emit the runtime marker

Do not ship the runtime yourself. Emit a single empty marker where it belongs:

```html
<script data-dashies-runtime></script>
```

Dashies fills that placeholder with the current client runtime at serve time, on
every request, then drops the marker attribute - so your published HTML stays tiny
(no ~93 KB blob) and every dashboard always runs the latest runtime instead of
freezing whatever was inlined at authoring time. The runtime implements island
contracts v1 and v2 (the island's `version` picks the path), injects its own CSS at
boot, and makes no network calls; since it is not in your published body, the cube
gets essentially the whole publish size budget. Leave the marker empty and
valueless: one `<script data-dashies-runtime></script>` with nothing inside it.

You may instead hand-roll a **custom vanilla-JS renderer**: **omit** the
`data-dashies-runtime` marker and ship your own `<script>` that reads the
`#dashies-data` island directly. The built-in viewer controls above (multi-select and
date-range filters, viewer sort / top-N, chart cross-filter, drill-through, multi-series)
already cover the common interactive cases, so prefer them; reach for a custom renderer only
for UI the `data-dash` roles genuinely cannot express (tabs, a bespoke chart type, a custom
layout). It stays refreshable because the refresh rewrites **only** the `#dashies-data`
island; your markup and scripts are untouched. Keep the island shape and manifest contract
intact and stay within the CSP.

### Respect the sandbox CSP (load-bearing)

Published dashboards are served under `Content-Security-Policy: sandbox
allow-scripts` - inline scripts run, but the document is an opaque origin. So your
markup and any script MUST:

- **Keep all state in memory and the URL hash only.** No `localStorage`,
  `sessionStorage`, cookies, or IndexedDB - they throw here. The runtime already
  mirrors active filters to the hash (`#region=EMEA`), so a filtered view is a
  shareable, reload-surviving link with no storage.
- **Make no network calls.** No `fetch` / `XMLHttpRequest` / `WebSocket`, and no
  external scripts, fonts, CSS, or images by URL - everything on screen comes from
  the inline cube. Inline or omit assets (fonts degrade to system stacks).
- **Keep `<body>` structurally normal.** The serve layer appends a "Powered by
  Dashies" badge as the last child of `<body>`; never script-replace `document.body`
  wholesale. Filling slots and appending to `<head>` is fine.

To see it rendered, open the **published Dashies URL** - the client runtime is
injected on serve, so a marker-only file opened locally (`file://` or a local
`http://` server) shows empty `data-dash` slots. For a quick offline visual check,
temporarily paste the runtime inline, then revert to the marker before publishing. A
`private` dashboard only renders for its signed-in owner.

## Make it beautiful, not just correct

A dashboard that works but looks like a bare template is a missed opportunity - the
person who opens it forms an opinion in the first second. Treat the design as part of
the job, not an afterthought:

- **Give it a hierarchy.** Lead with one hero metric that dominates; supporting
  metrics, charts, and the detail table should read as clearly secondary. A wall of
  ten equal-weight cards tells no story.
- **Give it a real header** - a title that says what question the dashboard answers,
  plus the freshness stamp - not a bare `<h1>`.
- **Be deliberate about type, space, and color.** Generous whitespace, a clear type
  scale, one restrained accent color, tabular numbers for figures. Sober and
  considered beats decorative.
- **Fit the audience.** A dashboard for a specific company should feel like it belongs
  to them - their color, a real header - not default blue-on-white.

For a genuinely designed, on-brand result - brand colors and type, a real logo, the
charts retinted to match - reach for the companion **`dashies-design`** skill once the
structure and data here are in place. It restyles only; it never touches the cube, the
island, or how the dashboard refreshes.

## Publish with the manifest

Publish the self-contained HTML with the manifest attached as `source_config`:

```
publish_dashboard({
  path: "<slug>/index.html",
  content_type: "text/html",
  body: "<self-contained HTML>",
  source_config: { ...manifest... }
})
```

There is no separate `frequency` argument - the cadence is the manifest's own
`schedule`. A publish with no `source_config` is an ordinary static dashboard. After
publishing, `get_source_config({ slug })` reads back the stored manifest and
`get_refresh_status({ slug })` shows whether it is refreshing and its recent runs.

> **The default manifest for a new dashboard is v4** (see "Manifest v4" below). The v1 /
> v3 / v2 sections that follow describe the single-manifest contracts that are also the
> per-dataset **modes** v4 wraps (`cube` = v1, `lattice` = v3, `rows` = v2): read them to
> author each v4 dataset's SQL, island shape, and measures. A single-manifest v1 / v3 / v2
> publish stays valid (existing dashboards use it, and a large-warehouse v2 + parquet cube
> stays on that path), but a new dashboard is emitted as v4 (inline-only).

### Manifest v1 (the additive cube)

This is `source_config` - a shared contract: this skill emits it, the authoring tools
validate and store it, and Dashies reads it to rebuild the island on refresh. Keep it minimal
and exact.

```json
{
  "manifest_version": 1,
  "connection": "self",
  "schedule": "daily",
  "timezone": "America/Los_Angeles",
  "cube_sql": "select ... group by 1,2,3",
  "dimensions": [
    { "key": "month", "label": "Month", "type": "date" },
    { "key": "region", "label": "Region", "type": "category" }
  ],
  "measures": [
    { "key": "revenue", "label": "Revenue", "agg": "sum", "additive": true, "format": "currency" },
    { "key": "orders", "label": "Orders", "agg": "sum", "additive": true, "format": "integer" }
  ],
  "format": { "currency": { "code": "USD", "decimals": 0 } },
  "derived": [
    { "label": "Revenue per order", "kind": "ratio", "num": "revenue", "den": "orders", "format": "currency" }
  ]
}
```

| Field | Required | Meaning |
|---|---|---|
| `manifest_version` | yes | `1` for the additive cube. |
| `connection` | yes | `"self"` or a warehouse connection `id` you own. Only the reference - never credentials. |
| `schedule` | yes | `manual` / `hourly` / `daily` / `weekly` / `monthly` - the refresh cadence. |
| `cube_sql` | yes | The single read-only `SELECT` from `cube.md`. |
| `timezone` | no | IANA business zone the time buckets are in (absent = UTC). `cube_sql` must bucket in this zone explicitly. |
| `dimensions` | yes | The grain: `{ key, label?, type: "category" \| "date" }`. |
| `measures` | yes | The aggregate columns: `{ key, label, agg: sum\|count\|min\|max, additive: true, format }`. |
| `format` | no | Global format defaults, copied into the island. |
| `derived` | no | Documents ratio metrics (`{ label, kind: "ratio", num, den, format }`) - rendered from your `data-num`/`data-den` bindings, not from this field. |

Invariants: `dimensions[].key` == the `GROUP BY` == the grain; every `measures[].key`
is an additive aggregate column; dimension keys + measure keys == every column the
SELECT returns == every key on each cube row; `dimensions` / `measures` / `format`
are byte-identical to the island. No non-additive measure is stored, and the publish
gate rejects a `cube_sql` that computes one.

### Manifest v3 - the grain compiler (`GROUP BY CUBE`)

When your metrics are non-additive but every filter / chart / table dimension is
low-cardinality, author **v3**. `cube_sql` is a `GROUP BY CUBE` lattice that
precomputes the exact aggregate for **every single-select filter state**, and the
island stores those cells flat under `cube` (like v1). The browser looks up the cell
matching the active filters, so distinct counts, medians, and percentiles stay exact
under any filter with no engine to load. Design and validate the SQL with **"Write a
v3 grain-compiler cube"** in `cube.md`; this is the manifest and island it produces.

Same envelope as v1 - **no `schema`, no `data`** - with the CUBE `cube_sql` and the
widened aggregate set:

```json
{
  "manifest_version": 3,
  "connection": "<warehouse id, or self>",
  "schedule": "daily",
  "timezone": "America/Los_Angeles",
  "cube_sql": "select month, region, plan, grouping(month) as __g_month, grouping(region) as __g_region, grouping(plan) as __g_plan, count(*) as orders, count(distinct customer_id) as customers, percentile_cont(0.5) within group (order by amount) as median_order from (select date_trunc('month', created_at at time zone 'America/Los_Angeles')::date as month, region, plan, customer_id, amount from orders where created_at >= now() - interval '12 months') src group by cube(month, region, plan)",
  "dimensions": [
    { "key": "month",  "label": "Month",  "type": "date" },
    { "key": "region", "label": "Region", "type": "category" },
    { "key": "plan",   "label": "Plan",   "type": "category" }
  ],
  "measures": [
    { "key": "orders",       "label": "Orders",       "agg": "count" },
    { "key": "customers",    "label": "Customers",    "agg": "count_distinct",  "column": "customer_id" },
    { "key": "median_order", "label": "Median order", "agg": "percentile_cont", "column": "amount", "percentile": 0.5 }
  ],
  "domains":    { "region": ["AMER", "EMEA", "APAC"], "plan": ["Free", "Pro", "Enterprise"] },
  "buckets":    { "month": 12 },
  "format": { "currency": { "code": "USD", "decimals": 0 } }
}
```

- **`cube_sql` is exactly `GROUP BY CUBE(<the plain dimension keys>)`** with one
  `GROUPING(<dim>) AS __g_<dim>` tag per dimension. The hard rules (plain-key CUBE
  args, a tag per dimension, no `GROUPING_ID` / `GROUPING SETS` / quoted identifiers,
  no expression inside `cube()`) are in `cube.md` and enforced at publish.
- **`measures[].agg`** may be any of `sum` / `count` / `min` / `max` / `avg` /
  `count_distinct` / `median` / `percentile_cont` / `percentile_disc` / `stddev` /
  `variance` / `mode` - each is exact per CUBE cell, so there is **no additivity
  requirement**. `column` and `percentile` work exactly as in v2.
- **`domains` (per category dimension) and `buckets` (per date dimension) are
  REQUIRED**, and they are what the publish checks the lattice's size against: a
  category dimension's `domains` is a non-empty array of its values, a date
  dimension's `buckets` is the max number of buckets (a positive integer). The
  lattice materializes about `prod(cardinality_i + 1)` cells - one per combination of
  the dimensions' values, plus each dimension's rolled-up state - and a publish over
  **50,000** cells is REJECTED, naming the count and the dimension to bound. Omitting
  them is also rejected: the size cannot be computed without them, and a lattice
  nobody can measure is not a lattice known to fit. This is the same ceiling, checked
  the same way, as a v4 `lattice`/`hybrid` dataset.
- **No `schema`, no `data`** - v3 stores its cells under the island `cube`, like v1.
- **Inline-only.** v3 is never offloaded to parquet or auto-promoted; keep the
  lattice under the inline cap by bounding dimensions.

The **v3 island** carries `"version": 3`, the same `dimensions` and `format`
(byte-identical to the manifest), the `measures` with only the fields the runtime
reads to look up and label each value (`key` / `label` / `agg`, plus any per-measure
`format`), and a `cube` array of the **flat CUBE cells** `validate_cube_sql`
returned. The manifest's `column` and `percentile` name the raw column and the
quantile for the cube SQL; the lattice looks each measure up by `key`, so the island
need not carry them. Each cell is one lattice row: the dimension
values (a rolled-up dimension is `null`), the per-dimension grouping flags
`__g_<dim>` (`0` active, `1` rolled up), and the measure values.

```json
{
  "version": 3,
  "updated_at": "2026-07-16T09:15:00Z",
  "dimensions": [
    { "key": "month", "label": "Month", "type": "date" },
    { "key": "region", "label": "Region", "type": "category" },
    { "key": "plan", "label": "Plan", "type": "category" }
  ],
  "measures": [
    { "key": "orders", "label": "Orders", "agg": "count" },
    { "key": "customers", "label": "Customers", "agg": "count_distinct" },
    { "key": "median_order", "label": "Median order", "agg": "percentile_cont" }
  ],
  "format": { "currency": { "code": "USD", "decimals": 0 } },
  "cube": [
    { "month": "2026-06", "region": "EMEA", "plan": "Pro", "__g_month": 0, "__g_region": 0, "__g_plan": 0, "orders": 329, "customers": 210, "median_order": 78 },
    { "month": "2026-06", "region": null, "plan": "Pro", "__g_month": 0, "__g_region": 1, "__g_plan": 0, "orders": 1240, "customers": 806, "median_order": 80 },
    { "month": null, "region": null, "plan": null, "__g_month": 1, "__g_region": 1, "__g_plan": 1, "orders": 21875, "customers": 9004, "median_order": 79 }
  ]
}
```

The first cell is fully specified (`region` = EMEA, `plan` = Pro, a specific month);
the second rolls up region (`__g_region: 1`, `region: null`), so the runtime serves
it when the Region filter is "All"; the last is the grand total (every dimension
rolled up). Your `data-dash` markup is unchanged from v1 - `metric`, `filter`,
`chart`, `table` all read the looked-up cell. Paste the rows `validate_cube_sql`
returned straight into `cube`; they already carry the `__g_<dim>` flags because your
SELECT projects them. Optionally add a top-level `"domains": { "region":
["AMER","EMEA","APAC"], ... }` to fix filter-menu order and membership; otherwise the
runtime derives each menu from the single-dimension cells. This is the ISLAND's
`domains` and it is a rendering choice, separate from the MANIFEST's required
`domains`/`buckets` above, which the server reads only to size the lattice - keep them
consistent, but do not expect one to stand in for the other.

### Manifest v2 - row-level metrics

When a metric additivity cannot express is the point - **distinct counts, medians,
percentiles, true averages** - author v2: the island ships **row-level rows**, and every metric is recomputed from those rows in the browser under each filter - correct by construction. Keep v1 for purely-additive cubes - it is
the lighter artifact (smaller page, no engine to load, aggregated bytes are the
privacy-safest shape). Two v2 costs: the first view has a one-time load (cached
after), and the island carries raw rows, so the "no sensitive data" rule tightens to
per-column - select only what you would publish.

Same envelope as v1, with these changes:

```json
{
  "manifest_version": 2,
  "connection": "<warehouse id, or self>",
  "schedule": "daily",
  "cube_sql": "select order_date, region, amount, customer_id from orders where order_date >= now() - interval '60 days'",
  "schema": [
    { "name": "order_date", "type": "DATE" }, { "name": "region", "type": "VARCHAR" },
    { "name": "amount", "type": "DOUBLE" }, { "name": "customer_id", "type": "BIGINT" }
  ],
  "dimensions": [ { "key": "region", "label": "Region", "type": "category" } ],
  "measures": [
    { "key": "revenue",   "label": "Revenue",   "agg": "sum",             "column": "amount" },
    { "key": "customers", "label": "Customers", "agg": "count_distinct",  "column": "customer_id" },
    { "key": "p95",       "label": "p95 order", "agg": "percentile_cont", "column": "amount", "percentile": 0.95 }
  ],
  "data": { "mode": "inline" }
}
```

- **`cube_sql` selects row-level rows** (or a fine pre-aggregation), not a GROUP BY
  cube. Every `cube.md` SQL rule still applies.
- **`schema`** (required): one `{ name, type }` per column, with exact SQL column types
  (`DATE`, `VARCHAR`, `DOUBLE`, `BIGINT`, ...). The runtime registers the rows as
  table `t`.
- **`measures[].agg`** may be any of `sum` / `count` / `min` / `max` / `avg` /
  `count_distinct` / `median` / `percentile_cont`. `measures[].column` names the raw
  column when it differs from the key; `measures[].percentile` (0..1) is for
  `percentile_cont`. `additive` is dropped. Each `dimensions[].key` must be a real
  column in `schema`.
- **`data`** (required): `{ "mode": "inline" }`, or `{ "mode": "parquet" }` for a
  warehouse cube too large to inline (below).

The **v2 island** carries `"version": 2`, the `schema`, and the row-level data in
place of v1's `cube`. Your `data-dash` markup is unchanged - only the number source
changes. For a **new** v2 inline dashboard, prefer the columnar `data.cols`
(object-of-arrays) over the row-major `data.rows` (array-of-objects): it is the same
data but ~2-3x denser on the wire, so the same ~8 MB island carries 2-3x the rows.
Both are supported and refresh preserves whichever an island uses - `cols` is simply
the better default for new work.

**The placeholder flow (row-level cubes).** `validate_cube_sql` echoes only a sample
of rows, so publish with a **tiny placeholder `data.rows`** (the sample works) and
let the **first refresh fill the full set** - pick a real cadence so it happens on
its own, and say the live page shows placeholder data until then.

**Caps.** A refresh writes at most **100,000 rows / 8 MB** into the island - **except on a
SQL Server (`mssql`) connection, whose confined executor caps a result at 5,000 rows /
2,000,000 bytes and offers no Parquet offload, so an over-cap cube must be coarsened rather
than offloaded**. The publish body itself caps at **~5 MB**, so a big row set can only
arrive via the placeholder flow. Beyond the island cap, a **warehouse** cube switches to
`data.mode: "parquet"`: the rows live in a separate file (ceiling ~128 MiB) instead
of the island, it publishes in a "preparing" state, and the first refresh fills it.
`self` always stays inline. Dashies reads the parquet with **HTTP range reads** - it
fetches only the row-groups a filtered / grouped query needs, not the whole file - so
a big parquet loads fine on desktop; only a full unfiltered scan on a low-RAM phone
still streams a lot, which shows a soft "may be large" advisory with a "Load anyway"
control, never a hard block. Check the table size with `introspect_schema` and
aggregate to the grain you actually chart so the extract stays small.

**Range-read capability tag.** On a v2 dashboard, add a top-level `"reader": "range"`
field to the `#dashies-data` island (a sibling of `version` / `schema` / `data` - NOT
inside `data`). It records that this dashboard's runtime range-reads its parquet, and
Dashies uses it to pick the parquet size ceiling. It is additive (no version bump)
and preserved across refreshes. It is load-bearing for a parquet dashboard; emitting
it on any v2 island is harmless and future-proofs an inline cube that later grows to
parquet.

### Manifest v4 - the default: many datasets in one dashboard

**This is the manifest you emit for a new refreshable dashboard.** A real report often
needs **several grains at once** - a KPI strip at the daily grain, a distinct-count trend
by month, a row-level detail table - which a single v1/v2/v3 manifest cannot do (each
ships one materialization). **v4 is one dashboard carrying up to 8 named `datasets`, each
independently one of the `cube` (v1) / `lattice` (v3) / `hybrid` / `rows` (v2)
materializations.** You author each dataset's SQL exactly as you would a standalone cube of
that mode; v4 just groups them under one connection + schedule and lets each tile pick its
dataset. A single-metric dashboard is simply a v4 manifest with one dataset.

> **Inline is the default; `parquet` is live for one specific case.** Emit `cube`,
> `lattice`, `hybrid` and inline `rows` datasets by default. **v4's parquet refresh path
> IS live** (A6 / #510, 2026-07-17): the cron diverts any non-`hybrid` v4 dataset carrying
> `data.mode: "parquet"` to the extract queue, and the delegate is wired for all five
> warehouse engines. An earlier version of this note said the path "is not live yet"; that
> was already wrong when it was written.
>
> **Reach for it only for a row-level slice too large to inline, and leave aggregates
> alone.** `cube` and `lattice` datasets are inline *by design* - the grain compiler
> precomputes them precisely so the numbers ship as small static bytes, and moving one to
> parquet trades that away for nothing. A real seven-dataset dashboard had exactly one
> row-level dataset, so parquet would have cut about 9% of its bytes; if you are reaching
> for parquet to shrink a lattice, the shape is wrong, not the storage. Constraints:
> **warehouse-only** (a `self` connection is rejected on any dataset mode), at most
> **`PARQUET_DATASETS_MAX` = 2** parquet datasets per dashboard, and `hybrid` is still
> **inline-only** - it ships both its lattice and its row-level slice in the island, and a
> `hybrid` + `parquet` publish is rejected.
>
> **Author it through the SPEC, not by hand (#772).** A spec can now declare
> `data: { mode: parquet }` on a `rows` dataset, and the compiler emits the island's pending
> pointer (`{ "mode": "parquet", "url": null }`), the top-level `"reader": "range"`
> capability tag, and the `_pending` marker for you. On THIS hand-authored path you must emit
> all three yourself - and omitting the `reader` tag silently caps that dataset at the 128 MiB
> legacy floor instead of 256 MiB, with no error anywhere. The spec is also deliberately
> stricter than this path: it accepts parquet on `rows` alone (this path would also let a
> `cube`/`lattice` divert to an extract whose object nothing reads) and refuses a
> `rows_window` beside it (inert on an extract). Prefer the spec.
>
> **Maturity, stated plainly so you can weigh it:** this path is live and unit-tested with
> injected deps, but it has **no end-to-end test against a real warehouse** - `parquet`
> appears in none of the 12 `*.live.test.ts` files. It is not battle-tested, and it is not
> a reason to avoid it either; the fail-safe is real, because a parquet pointer whose `url`
> is still `null` renders `_pending` ("Updating") rather than summing an empty payload to a
> fake 0. Prefer inline when inline fits, and verify the first parquet dashboard you ship.
>
> Existing v1/v2/v3 dashboards keep refreshing on their own contracts unchanged.

**The manifest.** Dashboard-level `connection` + `schedule` + `timezone` + `format`
(one connection, one snapshot per run), then a `datasets` **array** (1..8, ordered, the
first is the default). Each dataset is a per-mode cube: the field is **`sql`** (not
`cube_sql`), `mode` is `cube` / `lattice` / `hybrid` / `rows` (only a `rows` dataset may offload to parquet), and a
`lattice` **or `hybrid`** dataset must declare `domains` (the value list per category
dim) + `buckets` (the max bucket count per date dim, e.g. `24` - a number, not a grain
string). A `hybrid` (like a `rows` dataset) additionally carries `schema` + `data` and a
second `rows_sql` - see **"The `hybrid` dataset"** below. Validate each dataset's `sql`
with `validate_cube_sql` passing the matching `mode` (for a `hybrid`, validate its
`rows_sql` separately with `mode: "rows"`), and bake its returned rows into that dataset's
island section.

```json
{
  "manifest_version": 4,
  "connection": "self",
  "schedule": "daily",
  "timezone": "America/Los_Angeles",
  "format": { "currency": { "code": "USD", "decimals": 0 } },
  "datasets": [
    {
      "name": "kpis",
      "mode": "cube",
      "sql": "select month, region, sum(amount) as revenue, count(*) as orders from orders group by 1,2",
      "dimensions": [ { "key": "month", "type": "date" }, { "key": "region" } ],
      "measures":   [ { "key": "revenue", "agg": "sum", "additive": true, "format": "currency" },
                      { "key": "orders",  "agg": "sum", "additive": true } ]
    },
    {
      "name": "trend",
      "mode": "lattice",
      "sql": "select month, region, grouping(month) as __g_month, grouping(region) as __g_region, count(distinct customer_id) as customers from orders group by cube(month, region)",
      "dimensions": [ { "key": "month", "type": "date" }, { "key": "region" } ],
      "measures":   [ { "key": "customers", "agg": "count_distinct", "column": "customer_id" } ],
      "domains":    { "region": ["AMER", "EMEA"] },
      "buckets":    { "month": 24 }
    },
    {
      "name": "order_detail",
      "mode": "rows",
      "sql": "select order_id, order_date, region, amount from orders where order_date >= now() - interval '60 days'",
      "schema":     [ { "name": "order_id", "type": "BIGINT" }, { "name": "order_date", "type": "DATE" },
                      { "name": "region", "type": "VARCHAR" }, { "name": "amount", "type": "DOUBLE" } ],
      "dimensions": [ { "key": "region" } ],
      "measures":   [ { "key": "amount", "agg": "sum", "column": "amount", "format": "currency" } ],
      "data":       { "mode": "inline" }
    }
  ]
}
```

**The island.** `"version": 4`, dashboard-level `updated_at` + `format`, then
`datasets` as an **object keyed by name** (key order = the manifest order; the first is
the default). Each dataset spec is the same shape its standalone version would carry - a
`cube` dataset has `dimensions`/`measures`/`cube`; a `lattice` dataset has the flat CUBE
`cube` + `domains`; a `rows` dataset has `schema` + `data` - plus a per-dataset `as_of`.

```json
{
  "version": 4,
  "updated_at": "2026-07-16T09:15:00Z",
  "format": { "currency": { "code": "USD", "decimals": 0 } },
  "datasets": {
    "kpis": {
      "mode": "cube",
      "as_of": "2026-07-16T09:15:00Z",
      "dimensions": [ { "key": "month", "type": "date" }, { "key": "region" } ],
      "measures":   [ { "key": "revenue", "agg": "sum", "format": "currency" }, { "key": "orders", "agg": "sum" } ],
      "cube": [ { "month": "2026-06", "region": "AMER", "revenue": 8100, "orders": 300 } ]
    },
    "trend": {
      "mode": "lattice",
      "as_of": "2026-07-16T09:15:00Z",
      "dimensions": [ { "key": "month", "type": "date" }, { "key": "region" } ],
      "measures":   [ { "key": "customers", "agg": "count_distinct" } ],
      "cube": [ { "month": null, "region": null, "__g_month": 1, "__g_region": 1, "customers": 9004 } ],
      "domains": { "region": ["AMER", "EMEA"] }
    },
    "order_detail": {
      "mode": "rows",
      "as_of": "2026-07-16T09:15:00Z",
      "schema": [ { "name": "order_id", "type": "BIGINT" }, { "name": "order_date", "type": "DATE" },
                  { "name": "region", "type": "VARCHAR" }, { "name": "amount", "type": "DOUBLE" } ],
      "data": { "rows": [
        { "order_id": 1857, "order_date": "2026-06-14", "region": "AMER", "amount": 120 },
        { "order_id": 1858, "order_date": "2026-06-14", "region": "EMEA", "amount": 340 }
      ] }
    }
  }
}
```

**Route each tile to its dataset with `data-dataset`.** A tile with
`data-dataset="trend"` reads the `trend` dataset; a tile with no `data-dataset` reads the
default (first) dataset. Everything else - `metric` / `filter` / `chart` / `table` /
`updated-at`, the formats, the ratio bindings - is unchanged.

```html
<div data-dash="metric" data-dataset="kpis"  data-measure="revenue"><span data-dash-value>-</span></div>
<div data-dash="metric" data-dataset="trend" data-measure="customers"><span data-dash-value>-</span></div>
<div data-dash="chart"  data-dataset="trend" data-x="month" data-measure="customers"></div>
<div data-dash="filter" data-dataset="trend" data-dim="region"></div>
```

Filters are **global**: a `region` filter re-renders every dataset that declares a
`region` dimension. If a dataset's `as_of` lags the dashboard `updated_at` (its last
refresh partially failed or was skipped), its tiles show a quiet "as of `<time>`" note
and still render the exact last-good numbers - never a wrong or fake value.

**A worked interactive example.** The same datasets, now with viewer controls - a multi-select
region filter, a multi-series trend, a cross-filter chart, a top-N table, and drill-through to
the `order_detail` rows (each additive over the static tiles above):

```html
<!-- multi-select region filter (global) -->
<div data-dash="filter" data-dataset="kpis" data-dim="region" data-multi></div>
<!-- multi-series trend: revenue + orders on one CUBE chart, one shared axis + a legend -->
<div data-dash="chart"  data-dataset="kpis" data-x="month" data-measures="revenue,orders" data-type="line"></div>
<!-- cross-filter chart: click a bar to filter the whole dashboard by region (SINGLE-series) -->
<div data-dash="chart"  data-dataset="kpis" data-x="region" data-measure="revenue" data-xfilter></div>
<!-- viewer top-N + sort table (data-tile is REQUIRED with data-controls) -->
<div data-dash="table"  data-dataset="kpis" data-controls="sort,limit" data-tile="top-regions"></div>
<!-- drill a KPI into row-level detail (order_detail is the rows dataset declared above) -->
<div data-dash="metric" data-dataset="kpis" data-measure="orders" data-drill="order_detail"><span data-dash-value>-</span></div>
```

Each control is independent and additive, and the viewer's choices ride in the URL hash. Note
the routing the controls require: the multi-series and cross-filter charts both sit on a `cube`
dataset (multi-series is cube-only; a cross-filter chart is single-series, so it carries
`data-measure`, not `data-measures`, and never both), and the drill targets `order_detail`, the
`rows` dataset declared in the manifest above - a drill needs a real, declared, rows-bearing
target (aim it at `kpis` or `trend` and there are no rows to show).

#### The `hybrid` dataset (a lattice + an inline row slice)

A `lattice` precomputes every **single-select** filter state, so a non-additive measure
(distinct count, median, percentile) is exact when the viewer picks one value. But a
**multi-value** filter - a multi-select (`region = us,eu`) or a range
(`month = 2026-01..2026-06`) - has no precomputed cell, and for a **non-composable** measure
the lattice cannot build one: `count(distinct)` over a `us, eu` multi-select is not the sum
of the two per-region cells (a customer in both is double-counted), and a true average,
median, or percentile of the combined selection is not any combination of per-cell values
(a `sum` / `count` / `min` / `max` measure, by contrast, composes exactly from the cells). A `hybrid` closes exactly that gap: it ships
the **raw rows** for the grain alongside the lattice, so the runtime can recompute the
non-composable measure over the selected slice with DuckDB.

**When to choose it.** Your metrics are non-additive and your dimensions are low-cardinality
(so a `lattice` fits) **and** the dashboard needs multi-select or range filters on a
non-composable measure - i.e. you put a `data-multi` or `data-range` control (see Viewer
controls) on a dim that a distinct-count / average / median / percentile reads. If every filter
is single-select, a plain `lattice` is enough; if a dimension cannot be bounded to low
cardinality at all, use `rows`. Positioning is `cube` < `lattice` < `hybrid` < `rows`.

**The resolver ladder (what the runtime does per tile).** In resolution order, always exact
or an honest empty state - never an approximation:

1. **Single-select (or no filter)** -> look up the exact **lattice cell**. No engine.
2. **Multi-value filter, composable measure** (`sum` / `count` / `min` / `max`, or a ratio of
   them) -> compose the answer from the relevant lattice cells. No engine.
3. **Multi-value filter, non-composable measure** (`count_distinct` / `avg` / `median` /
   `percentile_*` / `stddev` / `variance` / `mode` - anything but `sum` / `count` / `min` /
   `max`) -> recompute over the **row slice** with DuckDB-WASM.

So the common, cheap interactions stay engine-free; DuckDB loads only when a multi-value
filter actually hits a non-composable measure. The runtime resolves all three rungs of this
ladder today - single-select from the lattice, composable multi-value composed from cells,
and the non-composable multi-value fallback recomputed over the rows slice.

**The manifest.** A hybrid dataset carries a lattice `sql` (a `GROUP BY CUBE`, exactly the
`lattice` shape) **and** a `rows_sql` (the row-level SELECT for the same grain, run in the
same refresh at the same instant), plus the lattice's `domains` (+ `buckets` per date dim)
**and** the row slice's `schema` + `data`. Validate the `sql` with
`validate_cube_sql({ mode: "hybrid" })` and the `rows_sql` separately with `mode: "rows"`.
The `rows_sql` projects the raw columns the non-composable measures read (here `customer_id`,
so `count(distinct customer_id)` can be recomputed over any multi-value slice), under a
relative time window like any refresh SQL.

```json
{
  "name": "buyers",
  "mode": "hybrid",
  "sql": "select region, grouping(region) as __g_region, count(distinct customer_id) as buyers from orders group by cube(region)",
  "rows_sql": "select region, customer_id from orders where created_at >= now() - interval '12 months'",
  "dimensions": [ { "key": "region" } ],
  "measures":   [ { "key": "buyers", "agg": "count_distinct", "column": "customer_id" } ],
  "domains":    { "region": ["us", "eu"] },
  "schema":     [ { "name": "region", "type": "VARCHAR" }, { "name": "customer_id", "type": "BIGINT" } ],
  "data":       { "mode": "inline" }
}
```

**The island.** The hybrid dataset carries both halves: the lattice under `cube` (the flat
`GROUP BY CUBE` rows, each tagged `__g_<dim>`) with its `domains`, and the row slice under
`schema` + inline `data.rows`.

```json
"buyers": {
  "mode": "hybrid",
  "as_of": "2026-07-16T09:15:00Z",
  "dimensions": [ { "key": "region" } ],
  "measures":   [ { "key": "buyers", "agg": "count_distinct", "column": "customer_id" } ],
  "cube": [ { "region": null, "__g_region": 1, "buyers": 9 },
            { "region": "us", "__g_region": 0, "buyers": 4 },
            { "region": "eu", "__g_region": 0, "buyers": 3 } ],
  "domains": { "region": ["us", "eu"] },
  "schema":  [ { "name": "region", "type": "VARCHAR" }, { "name": "customer_id", "type": "BIGINT" } ],
  "data":    { "mode": "inline", "rows": [ { "region": "us", "customer_id": 1 } ] }
}
```

**Inline-only, and keep the row slice small.** A hybrid ships both halves in the island - a
`hybrid` + `data.mode: "parquet"` publish is **rejected** (the parquet path for a hybrid's
row slice is not live). The lattice half obeys the `LATTICE_MAX_CELLS` budget like any
lattice; the row slice counts against the 8 MB island ceiling, so a typical narrow slice fits
**roughly 69k rows** before it. Bound it with `rows_window` (the first N rows of the
`rows_sql`'s own top-level ORDER BY, which is REQUIRED - order by time descending to make that
the most recent N; the aggregates stay exact over full history, only the row-level detail and
any drill are windowed). If the slice genuinely cannot be bounded, use a single-manifest v2 + parquet
dashboard instead.
