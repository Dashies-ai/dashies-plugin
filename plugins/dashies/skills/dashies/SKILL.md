---
name: dashies
description: >-
  Authoring guide for building a REFRESHABLE Dashies dashboard - one that re-runs
  its own SQL on a schedule and updates itself with no AI in the loop. Use this
  whenever the user wants to publish a Dashies dashboard that stays up to date
  automatically, refreshes on a schedule (hourly / daily / weekly / monthly), is
  backed by a connected database or warehouse, or should "not go stale" - even if
  they just say "build me a dashboard" and a data connection exists. It covers the
  gate (a refreshable dashboard needs a connected data source), cube design
  (low-cardinality grain, additive vs non-additive measures), the data-island +
  data-dash binding contract, the inlined client runtime, the sandbox CSP
  constraints, choosing a schedule, and the source_config manifest. For a one-off
  static dashboard with no live data source behind it, you do not need this skill -
  just generate HTML and publish it.
---

# Building a refreshable Dashies dashboard

Dashies can refresh a published dashboard on a schedule **without re-running a
model**. You (the AI) author the dashboard once. Alongside the HTML you emit
three things that let a server-side cron keep it fresh on its own forever:

1. An embedded JSON **data cube** - the data, pre-aggregated to the dashboard's
   grain - inside a `<script type="application/json" id="dashies-data">` island.
2. An inlined client **runtime** (vanilla JS, no dependencies) that reads the
   cube, fills the marked-up slots, and re-slices the cube in the browser when a
   filter changes - with zero network calls and no browser storage.
3. A server-side **manifest** (the cube SQL + the dimensions, measures, format,
   and schedule) stored in the dashboard's `source_config`.

A cron then re-runs the manifest's SQL on the chosen cadence and rewrites **only**
the data island in the stored HTML. The runtime and your markup are never touched.
No model is in the refresh loop, so the dashboard stays correct and cheap.

This skill is how you produce that initial dashboard correctly. The hard parts are
not the HTML - they are **cube design** and **measure additivity**, because the
cube SQL you write here runs unattended forever and the runtime can only re-slice
data that is additive. Get those right and everything downstream is mechanical.

> The binding layer (the exact data-island JSON shape and every `data-dash`
> attribute) is specified in **`web/dashboard-runtime/CONTRACT.md`** (contract
> v1). That document is authoritative; this skill teaches you how to *use* it and
> condenses the parts you need below. When in doubt, read CONTRACT.md.

---

## Step 0 - Gate: is there a connected data source?

**A dashboard can only refresh against a live data source. No connection means
nothing to re-run, so there is nothing to keep fresh.**

- **Connection present** -> build a refreshable dashboard with this skill (steps 1-6).
- **No connection** -> do NOT fake a refreshable dashboard. Build a normal,
  one-shot **static** dashboard instead (generate self-contained HTML and publish
  it the ordinary way), and tell the user it will not auto-refresh because no data
  source is connected. Attaching a manifest with no connection behind it produces a
  dashboard the cron cannot ever refresh, which is worse than an honest static one.

In Phase 1 the only connection is Dashies' own database, seeded as a connection
named `self`. "Connect your own warehouse" arrives later; design the manifest's
`connection` field now so it generalises (see Manifest v1).

There is no list-connections tool. The gate is simply: **call `introspect_schema`
(Step 1) and see whether it returns tables.** If it returns a usable schema, you
have a connection to build against; in Phase 1 that is always the seeded `self`
connection's no-PII metrics view.

---

## Step 1 - Introspect the connected schema

Before designing anything, look at what is actually there. Call the introspection
tool to enumerate the tables, columns, and types of the connected source.

```
introspect_schema({ connection: "self" })
```
`connection` is optional and defaults to `"self"` (the only connection in Phase 1).
The response is a per-table column list, then a `BEGIN_JSON ... END_JSON` block:
`{ connection, tables: [{ name, columns: [{ name, type }] }] }`. It returns column
names and types only - not row counts or cardinality - so judge cardinality from
what each column means (below) and confirm the real cube size later with
`validate_cube_sql`'s `row_count`.

What you are looking for:

- **Candidate dimensions** - the low-cardinality, descriptive columns the user
  will want to filter or group by (region, plan, status, category, a date column).
- **Candidate measures** - the numeric columns worth aggregating (amounts, counts,
  durations), and the row-grain facts you can `count(*)` or `sum(...)`.
- **Cardinality (estimate it)** - introspection gives names and types, not
  distinct-value counts, so judge it from meaning: a status or plan enum is
  low-cardinality and safe in the grain; a raw timestamp or a free-text id is
  high-cardinality until you bucket it (next step). `validate_cube_sql` later
  reports the actual cube row count, which is the real check.
- **Sensitivity** - which columns are personal or secret. The cube ships in public
  bytes (see Step 2), so plan to aggregate those away, never to carry them.

In Phase 1 the `self` connection exposes a curated, no-PII metrics view rather than
raw application tables. Design your cube from what introspection returns, not from
assumptions about the schema.

---

## Step 2 - Design the cube (the load-bearing step)

The **cube** is a small table of pre-aggregated rows: one row per combination of
the dimensions, with the measures already summed to that grain. The runtime never
fetches more data - every KPI, chart, table, and filtered view is computed from
these rows in the browser. So the cube's design *is* the dashboard's capability.

### 2a. The grain: every filterable field must be a dimension

The **grain** is the set of `GROUP BY` columns. A user can only filter or chart on
a field that is in the grain, because the runtime slices by matching dimension
values on the cube rows. If you want a Region filter, `region` must be a grouped
dimension. If a field is not in the grain, the cube cannot answer questions about
it - full stop.

So: **list every slice the dashboard should support, and make each one a
dimension.** Then stop. Each extra dimension multiplies the row count.

### 2b. Keep dimensions low-cardinality

The cube's row count is roughly the product of the dimensions' cardinalities. It is
shipped inside the HTML (under the publish size cap) and every `filter` renders a
`<select>` of a dimension's distinct values, so a high-cardinality dimension both
bloats the bytes and produces an unusable thousand-item dropdown. Keep each
dimension small:

- **Bucket dates.** Never put a raw timestamp in the grain. Truncate to the period
  the dashboard reports on: `date_trunc('month', created_at)::date as month` (or
  day / week). A `type: "date"` dimension is sorted as a time axis by the runtime.
- **Top-N high-cardinality categories.** If a category has hundreds of values, keep
  the top N by volume and fold the rest into an `"Other"` bucket in SQL, or drop it
  from the grain. Do not ship a 5,000-row dimension.
- **Aim for a few hundred to a few thousand cube rows, not tens of thousands.** A
  tight cube renders instantly and stays well under the size cap.

### 2c. The cube is public - aggregate away anything sensitive

Published dashboards are world-readable and the cube is embedded verbatim in the
HTML. Aggregate to a grain coarse enough that no individual row, person, or secret
is recoverable (watch small-cell counts that could re-identify someone). Carry
aggregates, never raw row-level or personal data. This is why the Phase 1 `self`
connection targets a no-PII view.

### 2d. Classify every measure: additive vs non-additive

This is the rule that makes or breaks correctness. When a filter changes, the
runtime re-aggregates by **summing** (or min / max / count) each measure across the
rows that remain. That is only correct for **additive** measures. Classify every
number you want to show before you write SQL:

**Additive - store these directly as measures.** They re-slice correctly under any
filter because the runtime can roll them up from the cube rows:

| What | Store as | `agg` |
|---|---|---|
| Sums of an amount (revenue, cost) | the summed column | `sum` |
| Counts of rows / events (orders, signups) | a `count(*)` column | `sum` (the cube already holds per-cell counts) |
| Smallest / largest in a cell | the value | `min` / `max` |

**Non-additive - never store the finished number as a measure.** You cannot recover
it by summing partial results, so a stored average / rate / distinct-count / median
goes silently wrong the moment the user filters. Handle each like this:

- **Averages, rates, ratios, "per" metrics, percentages** -> store the
  **numerator and denominator as two additive measures** and let the runtime divide
  them at render time with a `data-num` / `data-den` ratio binding. `sum(num) /
  sum(den)` stays correct under every filter because both parts are additive.
  Example: store `revenue` and `orders`; render "revenue per order" as the ratio.
  Store `conversions` and `visits`; render "conversion rate" as the ratio (the
  `percent` format expects a 0..1 ratio, which this produces - do not pre-multiply
  by 100). Never store a pre-divided average: an average of averages is wrong.
- **Distinct counts** (distinct active users, distinct accounts) are non-additive:
  distinct counts of disjoint slices do not add up. Options, best first: (1) if the
  thing you are counting is itself low-cardinality, carry it as a **dimension** so
  the runtime can recover the count by grouping; (2) **precompute the distinct count
  per slice** you actually need by adding those slice keys to the grain; (3) if
  neither fits, show it only at the cube's full grain and do not expose a filter
  that would force a wrong re-aggregation. Do not store a single distinct-count
  measure and let it be summed.
- **Medians and percentiles** cannot be reconstructed from sums at all. Precompute
  per slice (push the slice into the grain) or leave them out. There is no ratio
  trick for a median.

The runtime does expose `avg` and `distinct` aggregations, but `avg` is an
*unweighted* mean of cube rows (only correct when nothing is rolled up) and
`distinct` counts distinct values of a column among surviving rows (only correct
when that column is a grain dimension). Prefer additive measures plus ratio
bindings; reach for `avg` / `distinct` only when you have confirmed the grain makes
them correct. Put derived business logic in the cube SQL; the runtime only filters
additive numbers, divides additive pairs, and formats.

---

## Step 3 - Write and validate the cube SQL

Write one query that produces the cube. It runs **unattended on every refresh**, so
it must be correct now and stay correct without you.

Requirements:

- **A single read-only `SELECT`.** No DML, no DDL, no multiple statements, no CTEs
  that write. The refresh primitive runs it read-only with a statement timeout and a
  row/byte cap and will reject anything else.
- **`GROUP BY` exactly your dimension keys**, and `SELECT` those dimension columns
  plus one aggregate column per measure, each `AS` its manifest key. The set of
  output columns must equal `dimensions[].key` + `measures[].key`.
- **Use relative time windows, never hardcoded dates.** The cron reruns this for
  months. Write `where created_at >= now() - interval '12 months'`, not
  `where created_at >= '2026-01-01'`, or the window will silently freeze.
- **Bound the result** by keeping the grain low-cardinality (Step 2). A query that
  returns 50,000 rows will hit the cap.
- **Touch only allowlisted objects.** In Phase 1 that is the no-PII metrics view the
  `self` connection exposes.

```sql
-- shape only; column names come from your introspection
select
  date_trunc('month', created_at)::date as month,
  region,
  plan,
  sum(amount)            as revenue,
  count(*)               as orders,
  count(*) filter (where is_signup) as signups
from metrics_view
where created_at >= now() - interval '12 months'
group by 1, 2, 3
```

Validate before publishing:

```
validate_cube_sql({ sql: "<your SELECT>", connection: "self" })
```
`sql` is required; `connection` defaults to `"self"`. The SQL runs read-only under
exactly the confinement the refresh cron will later enforce (allowlist, row/byte
cap, statement timeout), so a query that validates here keeps running unattended.
On rejection you get the precise reason (read-only, single-statement, allowlist, or
row-cap) - fix and retry. On success the response is a column list and sample, then
a `BEGIN_JSON ... END_JSON` block `{ connection, ok, row_count, columns, rows }`.

Check it: confirm `columns` match your planned dimension and measure keys exactly,
`row_count` is sane (low hundreds to low thousands), and the values look right.
**Keep the returned `rows` - that is your initial cube, pasted verbatim into the
data island (Step 4).** If the grain is wrong or a column is missing, fix the SQL
here, not after publishing.

---

## Step 4 - Build the template, embed the cube, inline the runtime

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

### 4a. Mark up elements with `data-dash` (binding cheatsheet)

The runtime fills only elements carrying a `data-dash` attribute; it never replaces
your body. You own all layout and chrome. The full attribute tables are in
CONTRACT.md; the common roles:

- **`metric`** - one KPI number. `data-measure` + optional `data-agg`,
  `data-format`. The value is written into the first descendant `[data-dash-value]`
  (so you own the card). Ratio mode: `data-num` + `data-den` renders
  `sum(num)/sum(den)` (this is how you show averages and rates).
- **`filter`** - a dimension slicer. `data-dim="<dimension key>"`. Renders a
  `<select>` of that dimension's values plus "All"; filters compose with AND.
- **`chart`** - a sober SVG chart. `data-type` (`bar` default, `hbar`, `line`,
  `area`), `data-x="<dimension key>"`, `data-measure="<measure key>"`, optional
  `data-sort` / `data-limit` / `data-height`.
- **`table`** - the cube as a table. Optional `data-columns`, `data-group`,
  `data-sort="col:desc"`, `data-limit`.
- **`updated-at`** - the freshness stamp. Renders `updated_at` as relative time
  (`8 hours ago`), or absolute with `data-format="absolute"`.

Formats (`data-format` or a measure's `format`): `currency`, `percent` (expects a
0..1 ratio), `decimal`, `integer`, `compact`, or omit for a sober
thousands-separated number. Options: `data-decimals`, `data-currency`.

### 4b. Write the data island

Exactly one `<script type="application/json" id="dashies-data">` per dashboard. It
must be valid JSON - no comments, no trailing commas - because the refresh cron
finds it by that id and rewrites its contents wholesale.

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
    { "key": "orders", "label": "Orders", "agg": "sum", "format": "integer" },
    { "key": "signups", "label": "Signups", "agg": "sum", "format": "integer" }
  ],
  "format": { "currency": { "code": "USD", "decimals": 0 } },
  "cube": [
    { "month": "2026-06", "region": "EMEA", "plan": "Pro", "revenue": 7594, "orders": 329, "signups": 103 }
  ]
}
```

- `version` is `1` (the contract version).
- `updated_at` is when you computed this cube (ISO 8601); the cron overwrites it.
- Each `cube` row is one `GROUP BY` result: a flat object whose keys are exactly the
  dimension keys + measure keys. Paste in the rows `validate_cube_sql` returned.
- `dimensions` / `measures` / `format` mirror the manifest (Manifest v1 below) - keep
  them identical, since the cron rebuilds this island from `manifest + fresh rows`.

### 4c. Inline the runtime

The runtime is the canonical `web/dashboard-runtime/runtime.js` (contract v1). There
is **no server-side baking** - `publish_dashboard` stores the HTML byte-for-byte, so
you must produce fully inlined HTML. Replace the `<script src="runtime.js"></script>`
placeholder with `<script>` + the file's contents + `</script>`. It injects its own
CSS at boot, so nothing else needs inlining. The runtime is small (well under the
size cap), so the cube data has essentially the whole publish budget.

Get the bytes from `web/dashboard-runtime/runtime.js` in this repo - the one source
of truth, kept in lockstep with the binding contract. There is no runtime-supplying
tool; the publish path stores whatever HTML you send. The committed dogfood (see the
worked example) is a full inlined reference you can copy the assembly from.

### 4d. Respect the sandbox CSP (load-bearing)

Published dashboards are served under `Content-Security-Policy: sandbox
allow-scripts`. Inline scripts run, but the document is an opaque origin with **no**
`allow-same-origin`. Your markup and any script you add MUST therefore:

- **Keep all state in memory and the URL hash only.** No `localStorage`,
  `sessionStorage`, cookies, or IndexedDB - they throw in this sandbox. The runtime
  already mirrors active filters to the hash (`#region=EMEA&plan=Pro`), so a
  filtered view is a shareable, reload-surviving link with no storage.
- **Make no network calls.** No `fetch` / `XMLHttpRequest` / `WebSocket`. Everything
  on screen comes from the inline cube. Do not load external scripts, fonts, CSS, or
  images by URL; inline or omit them. (Fonts degrade gracefully to system stacks.)
- **Keep `<body>` structurally normal.** The serve layer appends a "Powered by
  Dashies" badge as the last child of `<body>`. Never script-replace `document.body`
  wholesale, or you clobber it. Filling slots and appending to `<head>` is fine.

---

## Step 5 - Pick a schedule

Choose one cadence: **`manual`**, **`hourly`**, **`daily`**, **`weekly`**, or
**`monthly`**. Match it to how fast the underlying data actually moves and the grain
you chose - a dashboard bucketed by `month` gains nothing from hourly refreshes.
`manual` means it only refreshes when someone triggers it (no cron). `daily` is a
sensible default for most reporting dashboards. This value goes in the manifest's
`schedule` and sets the dashboard's refresh frequency.

Pick only the **cadence** here: the end-user sets the exact day, time, and
timezone for it in the app (the **Schedules** page), and the cron honors that
wall-clock time in their zone. They can also refine the cadence into a sub-daily
**interval** there - "every N hours" (e.g. an `hourly` manifest becomes "every 4
hours from 09:00"), or "every N days/weeks/months". The manifest `schedule` stays
the coarse cadence string - no manifest-shape change.

---

## Step 6 - Publish with the manifest

Produce the inlined HTML (Step 4) and publish it with the manifest attached as
`source_config`, the slug, and the schedule.

```
publish_dashboard({
  path: "<slug>/index.html",
  content_type: "text/html",
  body: "<inlined HTML>",
  source_config: { ...Manifest v1, including its schedule... }
})
```
The manifest rides on `publish_dashboard`'s optional `source_config` argument - there
is **no separate `frequency` argument**. The cadence is the manifest's own `schedule`
field (Step 5); the server derives the dashboard's `frequency` and `status` from it.
A publish with no `source_config` is an ordinary static dashboard. (The metadata args
`name`, `tags`, `chart`, `visibility`, `workspace` work as usual.)

The publish writes the R2 object and the `public.dashboards` row and stores your
manifest in `source_config`. Share the returned URL. From then on the cron refreshes
the cube on the schedule with no model involved.

---

## Manifest v1 (shared contract)

**This is `source_config`. It is a shared contract: this skill (PR6) emits it, the
authoring tools (PR3) validate and store it, and the refresh cron (PR4) reads it to
rebuild the data island on every run. Keep it minimal and exact.** Treat this block
as the source of truth for the manifest shape; flag changes as a version bump.

```json
{
  "manifest_version": 1,
  "connection": "self",
  "schedule": "daily",
  "cube_sql": "select date_trunc('month', created_at)::date as month, region, plan, sum(amount) as revenue, count(*) as orders from metrics_view where created_at >= now() - interval '12 months' group by 1,2,3",
  "dimensions": [
    { "key": "month", "label": "Month", "type": "date" },
    { "key": "region", "label": "Region", "type": "category" },
    { "key": "plan", "label": "Plan", "type": "category" }
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
| `manifest_version` | yes | Manifest contract version. `1` today. Distinct from the data island's `version`. |
| `connection` | yes | Which data source to run `cube_sql` against, by name (a string). Phase 1: `"self"` (Dashies' own no-PII metrics view). Future warehouse connections add more names; it stays a string. |
| `schedule` | yes | One of `manual` / `hourly` / `daily` / `weekly` / `monthly`. Sets the refresh cadence. |
| `cube_sql` | yes | The single read-only `SELECT` from Step 3. Its `GROUP BY` columns must equal `dimensions[].key`; its output columns must equal `dimensions[].key` + `measures[].key`. |
| `dimensions` | yes | The grain. Same shape as the data island's dimension specs (`key`, optional `label`, `type` of `category` (default) or `date`). |
| `measures` | yes | The stored aggregate columns. Same shape as the island's measure specs (`key`, `label`, `agg`, `format`) plus `additive`. |
| `measures[].agg` | yes | Roll-up the runtime applies: `sum` / `count` / `min` / `max`. |
| `measures[].additive` | yes | Must be `true`. Records that this measure re-slices correctly. Non-additive metrics are not stored as measures - they appear in `derived` (ratios) or as a dimension (distinct counts). The flag forces the classification from Step 2d and lets PR3 reject a non-additive measure. |
| `format` | no | Global format defaults keyed by format name (e.g. `currency`), copied verbatim into the data island. |
| `derived` | no | Documents non-additive metrics rendered at display time as a ratio of two additive measures: `{ label, kind: "ratio", num, den, format }`. Auditing + validation metadata; the runtime renders these from the `data-num` / `data-den` bindings in your HTML, not from this field. |

**Invariants the manifest must satisfy:**

1. `dimensions[].key` == the cube SQL's `GROUP BY` columns == the cube grain.
2. Every `measures[].key` is an aggregate column in `cube_sql`, additive, rolled up
   by its `agg`.
3. `dimensions[].key` + `measures[].key` == every column the SELECT returns ==
   every key on each cube row.
4. No non-additive measure is stored. Ratios live in `derived` (and in `data-num` /
   `data-den` bindings); distinct counts become dimensions or grain keys.
5. `dimensions`, `measures`, and `format` are byte-identical to what you put in the
   data island, so the cron can rebuild the island from `manifest + fresh rows`.

---

## Worked example: Dashies usage metrics (the dogfood)

The reference dashboard is Dashies' own usage metrics, refreshed daily off the
Phase 1 no-PII view via the `self` connection. It is committed - fully inlined and
ready to publish - at `.claude/skills/dashies/assets/dogfood/` (the HTML, the
manifest, and a README). Copy its assembly when you build your own.

1. **Gate:** `introspect_schema` returns the `self` schema -> refreshable.
2. **Introspect:** the `self` connection exposes one view, `dashies_usage_metrics`,
   with a `day` date column and eight additive count columns
   (`dashboards_published`, `public_count`, `private_count`, `active_count`,
   `paused_count`, `failed_count`, `archived_count`, `scheduled_count`). No
   categorical dimension, no PII.
3. **Design the cube:** grain = `{ day }` (the one dimension, a date). Each count is
   an additive `sum` measure. The two "share" metrics (public share, scheduled share)
   are non-additive, so they are NOT stored - they render as `num/den` ratios
   (`public_count / dashboards_published` and `scheduled_count / dashboards_published`).
   Because the only dimension is a date, the dashboard charts the trend rather than
   offering a filter dropdown of every day.
4. **SQL + validate:** `select day, dashboards_published, public_count, private_count,
   active_count, paused_count, failed_count, archived_count, scheduled_count from
   public.dashies_usage_metrics where day >= (now() - interval '90 days')::date order
   by day` -> `validate_cube_sql` -> confirm the columns equal the grain + measures,
   then paste the returned `rows` into the island.
5. **Template:** an `updated-at` stamp; `metric` KPIs for the counts plus two
   `num`/`den` ratio metrics for the shares; an `area` chart of `dashboards_published`
   by `day` and a `line` chart of `scheduled_count` by `day`; a `table` grouped by
   `day`. Inline the runtime; respect the CSP; no filter (a single date dimension).
6. **Schedule + publish:** `schedule: "daily"` in the manifest, then
   `publish_dashboard` with that manifest as `source_config`.

> **Do not publish this dogfood until dashies-mcp is deployed with PR3's tools.** The
> artifact is committed and verified to render standalone; the live publish is a
> coordinated follow-up. Once the deploy lands, re-inline the current runtime,
> `validate_cube_sql` the manifest's `cube_sql`, paste the fresh rows, and publish -
> then confirm it refreshes daily, slices client-side under `sandbox allow-scripts`,
> and uses no `localStorage`.

---

## Guardrails recap

- **Refresh needs a connection.** No connection -> honest static dashboard, not a
  fake refreshable one.
- **Additivity is correctness, not style.** Only additive measures are stored; ratios
  are `num` / `den`; distinct counts and medians go in the grain or are dropped.
- **The cube is public, aggregated bytes.** No PII, no raw rows, no small-cell
  re-identification.
- **The SQL runs forever.** One read-only SELECT, relative time windows, low grain.
- **The sandbox is strict.** No storage, no network, no wholesale `<body>` replace.
- **Style:** match Dashies' sober tone. Use plain ASCII hyphens, never em dashes or
  en dashes, in any dashboard copy or your prose. Do not give time estimates ("a few
  minutes", "quick") - describe scope, not duration. Do not invent features the data
  does not support.

For the exhaustive binding reference read `web/dashboard-runtime/CONTRACT.md`. The
tool calls in Steps 1, 3, and 6 (`introspect_schema`, `validate_cube_sql`, and
`publish_dashboard` with `source_config`) match the shipped MCP tools.
