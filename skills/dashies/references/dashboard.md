# Reference: build the HTML and write the manifest

Part of the `dashies` skill (Steps 4 + 6). Once the cube is designed and validated
(`cube.md`), you assemble one self-contained HTML file that renders it, and you
attach a **manifest** that lets Dashies rebuild the cube on a schedule. The exact,
authoritative binding spec is `web/dashboard-runtime/CONTRACT.md`; this condenses
what you need.

## The HTML: markup + island + runtime

A refreshable dashboard is one self-contained HTML file with three parts in the
`<body>`: your marked-up content, the data island, then the runtime.

```html
<!doctype html>
<html lang="en">
  <head> <!-- your page <title> and CSS --> </head>
  <body>
    <!-- 1. your markup, with data-dash slots -->
    ...
    <!-- 2. the data island (the cube) -->
    <script type="application/json" id="dashies-data"> { ...spec... } </script>
    <!-- 3. the runtime, inlined verbatim -->
    <script> /* contents of runtime.js */ </script>
  </body>
</html>
```

### Mark up elements with `data-dash`

The runtime fills only elements carrying a `data-dash` attribute; it never replaces
your body, so you own all layout and chrome. The common roles (full tables in
CONTRACT.md):

- **`metric`** - one KPI number. `data-measure` + optional `data-agg`, `data-format`;
  the value lands in the first descendant `[data-dash-value]`. Ratio mode:
  `data-num` + `data-den` renders `sum(num)/sum(den)` - this is how you show
  averages and rates.
- **`filter`** - a dimension slicer. `data-dim="<key>"` renders a `<select>` of that
  dimension's values plus "All"; filters compose with AND.
- **`chart`** - a sober SVG chart. `data-type` (`bar` default, `hbar`, `line`,
  `area`), `data-x="<dimension key>"`, `data-measure="<measure key>"`, optional
  `data-sort` / `data-limit` / `data-height`.
- **`table`** - the cube as a table. Optional `data-columns`, `data-group`,
  `data-sort="col:desc"`, `data-limit`.
- **`updated-at`** - the freshness stamp, rendered as relative time (`8 hours ago`),
  or absolute with `data-format="absolute"`.

Formats (`data-format`, or a measure's `format`): `currency`, `percent` (expects a
0..1 ratio - do not pre-multiply by 100), `decimal`, `integer`, `compact`, or omit
for a thousands-separated number. Options: `data-decimals`, `data-currency`.

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

- `version` is `1` for the additive cube (`2` for row-level - see Manifest v2).
- `updated_at` is when you computed the cube (ISO 8601); Dashies overwrites it on refresh.
  Render it from the full ISO timestamp, never a date-only slice, or the "refreshed
  N ago" stamp anchors to midnight and reads stale.
- Each `cube` row is one `GROUP BY` result - a flat object keyed by the dimension +
  measure keys. Paste in the rows `validate_cube_sql` returned.
- `dimensions` / `measures` / `format` must be **byte-identical to the manifest**,
  since Dashies rebuilds the island on refresh from `manifest + fresh rows`.

### Inline the runtime

The runtime is the canonical `web/dashboard-runtime/runtime.js` in this repo (it
implements contracts v1 and v2; the island's `version` picks the path). Publish
stores your HTML byte-for-byte, so replace the `<script src="runtime.js">` placeholder
with `<script>` + the file's contents + `</script>`. It injects its own CSS at boot,
and it is small, so the cube gets essentially the whole size budget.

You may instead hand-roll a **custom vanilla-JS renderer** that reads the
`#dashies-data` island directly - reach for one when you need UI the built-in
bindings do not cover (multi-select filters, date-range pickers, tabs, bespoke
charts). It stays refreshable because the refresh rewrites **only** the
`#dashies-data` island; your markup and scripts are untouched. Keep the island shape
and manifest contract intact and stay within the CSP.

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

Preview over a local `http://` server, not `file://` (relative-path behavior
differs). A `private` dashboard only renders for its signed-in owner.

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

Publish the inlined HTML with the manifest attached as `source_config`:

```
publish_dashboard({
  path: "<slug>/index.html",
  content_type: "text/html",
  body: "<inlined HTML>",
  source_config: { ...manifest... }
})
```

There is no separate `frequency` argument - the cadence is the manifest's own
`schedule`. A publish with no `source_config` is an ordinary static dashboard. After
publishing, `get_source_config({ slug })` reads back the stored manifest and
`get_refresh_status({ slug })` shows whether it is refreshing and its recent runs.

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
| `dimensions` | yes | The grain: `{ key, label?, type: "category" | "date" }`. |
| `measures` | yes | The aggregate columns: `{ key, label, agg: sum|count|min|max, additive: true, format }`. |
| `format` | no | Global format defaults, copied into the island. |
| `derived` | no | Documents ratio metrics (`{ label, kind: "ratio", num, den, format }`) - rendered from your `data-num`/`data-den` bindings, not from this field. |

Invariants: `dimensions[].key` == the `GROUP BY` == the grain; every `measures[].key`
is an additive aggregate column; dimension keys + measure keys == every column the
SELECT returns == every key on each cube row; `dimensions` / `measures` / `format`
are byte-identical to the island. No non-additive measure is stored, and the publish
gate rejects a `cube_sql` that computes one.

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

The **v2 island** carries `"version": 2`, the `schema`, and `data.rows` (an
array-of-objects) in place of v1's `cube`. Your `data-dash` markup is unchanged -
only the number source changes. An inline island may instead use a columnar
`data.cols` (object-of-arrays, same columns) to pack ~2-3x more rows into the size
budget.

**The placeholder flow (row-level cubes).** `validate_cube_sql` echoes only a sample
of rows, so publish with a **tiny placeholder `data.rows`** (the sample works) and
let the **first refresh fill the full set** - pick a real cadence so it happens on
its own, and say the live page shows placeholder data until then.

**Caps.** A refresh writes at most **100,000 rows / 8 MB** into the island; the
publish body itself caps at **~5 MB**, so a big row set can only arrive via the
placeholder flow. Beyond the island cap, a **warehouse** cube switches to
`data.mode: "parquet"`: the rows live in a separate file (ceiling ~128 MiB,
desktop-first) instead of the island, it publishes in a "preparing" state, and the
first refresh fills it. `self` always stays inline. Check the table size with
`introspect_schema` and aggregate to the grain you actually chart so the extract
stays small.
