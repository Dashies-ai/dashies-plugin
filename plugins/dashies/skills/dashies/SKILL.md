---
name: dashies
description: >-
  Authoring guide for building and EDITING a REFRESHABLE Dashies dashboard - one
  that re-runs its own SQL on a schedule and updates itself with no AI in the loop.
  Use this whenever the user wants to publish a Dashies dashboard that stays up to
  date automatically, refreshes on a schedule (hourly / daily / weekly / monthly),
  is backed by a connected database or warehouse, or should "not go stale" - even if
  they just say "build me a dashboard" and a data connection exists - AND whenever
  they want to EDIT an existing dashboard: "change a measure", "edit my dashboard",
  "add a chart", "reload / update the spec". You author by writing a SPEC (a small
  YAML document of datasets + tiles + a source) that you pass to publish_dashboard's
  `spec` argument; the server compiles it into the HTML + data island + refresh
  manifest, validates it (a structurally broken or silently wrong spec is rejected
  with a pointered error, not a rendering surprise), and seeds it live. It covers the
  gate (a refreshable dashboard needs a connected data source), cube design
  (low-cardinality grain, additive vs non-additive measures), filling the spec, the
  four dataset modes (cube / lattice / hybrid / rows), publishing with a dry run, and
  the get -> edit -> republish loop. For a one-off static dashboard with no live data
  source behind it, you do not need this skill - just generate HTML and publish it.
---

# Building a refreshable Dashies dashboard

Dashies can refresh a published dashboard on a schedule **without re-running a
model**. You (the AI) author the dashboard once, by writing a **spec** - one small
YAML document. You pass it to `publish_dashboard`'s `spec` argument and the server:

1. **Compiles** the spec into the self-contained HTML - your tiles become `data-dash`
   markup, the pre-aggregated data goes into a `<script id="dashies-data">` island, and
   the client runtime marker is emitted - plus the refresh **manifest** (the cube SQL +
   dimensions + measures + schedule). You write NONE of that; the compiler owns it.
2. **Validates** the whole thing: a role-less tile, a binding that names a column the
   SQL never returns, a non-additive measure in an additive cube - each is a **pointered
   publish error naming the exact field**, not a blank tile or a silently-wrong number
   that ships and rots.
3. **Seeds** it: it runs each dataset's `sql` once through the same confined read-only
   executor `validate_cube_sql` uses and bakes the real first numbers into the island,
   so the published bytes are correct immediately - and a dataset that fails, returns
   zero rows, or whose bindings do not match the seeded columns cannot publish.

Dashies then re-runs the manifest's SQL on the chosen cadence and rewrites **only**
the data island in the stored HTML. Your spec's markup and the runtime are never touched.
No model is in the refresh loop, so the dashboard stays correct and cheap.

This skill is how you produce that spec correctly. The hard parts are **not** the spec -
they are **cube design** and **measure additivity** (Steps 1-3), because the cube SQL you
write there runs unattended forever and the runtime can only re-slice data that is
additive. Get those right and the spec (Step 4) is mechanical: turn the cube into datasets
and tiles, and the server compiles, validates, and seeds it.

A new refreshable dashboard is a **manifest v4** report under the hood: **one dashboard
carrying up to 8 named `datasets`, each independently one materialization mode**, under a
single connection and schedule. Most dashboards need one dataset; a real report that needs
several grains at once - a KPI strip, a distinct-count trend by month, a row-level detail
table - uses several, and each tile picks its dataset (`dataset:`). Each dataset chooses its
**mode** by exactly the mechanical rule the single-metric choice always used (declare it, or
let the server auto-select `cube`/`lattice` and read `mode_choices` back):

- **`cube`** (the baseline additive cube) ships pre-aggregated rows the runtime re-sums in
  JS - the smallest, engine-free, correct **only** for additive measures. (The v1
  materialization.)
- **`lattice`** (the grain compiler) ships a **`GROUP BY CUBE` lattice**: every
  single-select filter state is precomputed as one cell and the browser just LOOKS UP the
  exact answer, so non-additive metrics (distinct counts, medians, percentiles, true
  averages) stay exact under any filter, the artifact stays MB-scale, and no engine loads.
  It is the **default the moment a metric is non-additive AND every filter/chart/table
  dimension is low-cardinality** and every filter is **single-select**. (The v3
  materialization.)
- **`hybrid`** (the grain compiler **plus** a row-level slice) ships **both** a `GROUP BY
  CUBE` lattice *and* the raw rows for that grain, in one dataset. Single-select filters, and
  **composable** multi-value filters (sum / count / min / max / a ratio of them), resolve
  from the lattice with no engine; a **multi-value** filter (multi-select or a range) on a
  **non-composable** measure (distinct count, true average, median, percentile, stddev,
  variance, mode) recomputes exactly from the row slice via DuckDB. It is the choice when a
  non-additive metric must stay exact under **multi-value** filters, which a pure `lattice`
  cannot compose. Inline-only. (Declared with a `rows_sql`.)
- **`rows`** (row-level + DuckDB-WASM) ships **row-level rows** and recomputes each metric
  from them in the browser. It is the **fallback for genuine row-level needs** - a dimension
  you cannot bound to low cardinality, or a need for row-level detail. (The v2
  materialization.)

Positioning is **`cube` < `lattice` < `hybrid` < `rows`** in both power and cost. So per
dataset the choice is mechanical: the moment any measure is non-additive, leave `cube` - use
`lattice` when every dimension is low-cardinality and its filters are single-select, `hybrid`
when those low-cardinality dimensions also need multi-select / range filters on a
non-composable measure, else `rows`. The additive rule is **enforced at publish** (a `cube`
dataset whose SQL computes `count(DISTINCT ...)`, `avg`, `median`, `percentile_*`, `stddev`,
`variance`, or `mode()` is rejected, naming the construct), so a wrong mode is a pointered
error, not a silent regression. Validate each dataset's SQL with `validate_cube_sql` passing
the matching `mode` (`references/cube.md`).

**Aggregates ride inline; row-level detail can offload to Parquet.** Every `cube` /
`lattice` / `hybrid` dataset's data lives in the island, which is capped at 8 MiB / 100k rows
across the WHOLE dashboard - so keep those bounded (coarser buckets, top-N a big category, a
tighter window). A **`rows` dataset on a warehouse connection** can instead declare
`data: { mode: parquet }`: its rows are extracted to a Parquet object on each refresh and
range-read by the runtime instead of inlined.

**Parquet does not change what you can declare. It changes where the bytes go and how large
the dataset may grow.** Two different ceilings, and only the second one moves:

- **At publish / republish** - the SQL you WRITE must return **<= 100,000 rows and
  <= 8,000,000 serialized bytes**, because the publish still SEEDS it through the same
  confined authoring executor `validate_cube_sql` uses (that is what proves the SQL runs and
  types its columns), and that executor treats an overflow as a hard error, never a silent
  truncation. That is the SAME row cap as an inline dataset and a marginally TIGHTER byte cap
  (the inline island allows 8,388,608 - binary 8 MiB - so the executor is 388,608 bytes
  lower). Declaring parquet buys you nothing here.
- **At refresh** - the dataset may GROW into 256 MiB / 50M rows, which is where those figures
  come from.

So `data: { mode: parquet }` is not a way to declare a 5M-row detail table today; bound the
declared statement exactly as you would an inline one. What it does buy is real and worth
having - you are publishing a small dataset that can grow large on refresh:

- the dataset's rows leave the **shared 8 MiB island budget**, so every other dataset gets all
  of it - this is the composite-model value, and usually the reason to reach for it,
- the dataset can **GROW** past the inline caps between publishes without breaking, since only
  publish is capped and refresh is not,
- the runtime **range-reads** the object instead of downloading it whole.

That is the **composite model**, and it is the shape a large report should take: a `lattice`
serves the aggregates (exact under any filter, MB-scale, no engine), and a Parquet-backed
`rows` dataset carries the drill-through detail behind it. At most **2** parquet datasets per
dashboard, which is sized for exactly that. The rules, and the reasons, are in
`references/spec.md` under `data`.

`self` always stays inline (its no-PII view is small by construction), and existing v1/v2/v3
dashboards keep refreshing on their own contracts forever, untouched.

## How this skill is organized

This file is the **orchestrator**: the gate, the workflow spine, the schedule / publish /
edit steps, and the guardrails. The depth for each step lives in a **reference file** you
load when you reach that step - do not front-load them all. The map is at the bottom under
**References**.

---

## Step 0 - Gate: is there a connected data source?

**A dashboard can only refresh against a live data source. No connection means
nothing to re-run, so there is nothing to keep fresh.**

- **Connection present** -> build a refreshable dashboard with this skill (steps 1-7).
- **No connection** -> do NOT fake a refreshable dashboard. Build a normal,
  one-shot **static** dashboard instead (generate self-contained HTML and publish
  it the ordinary way with `body`, not `spec`), and tell the user it will not
  auto-refresh because no data source is connected. A spec with no connection behind
  it cannot seed, so it cannot publish - an honest static dashboard is the answer.

**A spec publishes to a personal dashboard OR into a workspace.** Both work. Scope
comes from the grant your MCP connection was authorized with, plus an optional
`workspace` argument - exactly the same rule as a `body` publish, so there is
nothing spec-specific to remember:

- **Personal grant, no `workspace`** -> a personal dashboard at
  `https://<handle>.dashies.xyz/<slug>`.
- **`workspace: "<slug>"`, or a workspace-LOCKED grant** -> a team dashboard at
  `https://<workspace-slug>.dashies.xyz/<slug>`, visible to members. Any member of
  the workspace may publish and republish it, including one who did not create it.

Two differences from a personal publish, both deliberate:

- A workspace dashboard defaults to **private** (members-only) where a personal one
  defaults to public. Pass `visibility` explicitly if you want otherwise.
- The connection behind it must belong to the SAME space. A workspace dashboard
  refreshes from a workspace connection; a personal one from a personal connection.
  A connection belongs permanently to the space it was created in, so if
  `list_connections` shows nothing usable from inside a workspace, the user has to
  add the warehouse from inside that workspace - you cannot move an existing one.

*(Historical note, because it was true until recently and the refusal text is still
findable: a spec publish into a workspace used to be rejected with "spec
(file-format) dashboards are personal-only in v1". That gate is gone. If you ever
see that string, the deployed server is older than this skill.)*

Two kinds of data source can back a refreshable dashboard:

- **`self`** - Dashies' own database, a built-in connection named `self` that is
  always available and needs no setup. It exposes a curated, no-PII metrics view. In a
  spec, **`source.connection` is required and has no default** - set it explicitly to
  `connection: self` (omitting it is an L2 "missing required property" error). The
  omit-it-for-`self` default applies only to the `introspect_schema` /
  `validate_cube_sql` tool arguments while exploring, before you have written a spec -
  it does not carry over to the spec's `source` block.
- **A warehouse connection you own** - a paid user connects their own warehouse (a
  **Postgres** database, a **BigQuery** project, a **Snowflake** account, an
  **Amazon Redshift** warehouse, a **Databricks** workspace, or a **Microsoft SQL Server** database) in the Dashies web app, on the **Connections** page
  (`/app/connections`). Credentials are entered through that SPA form only; they never
  pass through the AI or the MCP, so you cannot connect a warehouse for the user - if
  they need one and have not connected it, they do that in the app first. Once
  connected, the tables they imported (Postgres) or the datasets/databases they
  allowlisted (BigQuery / Snowflake / Redshift), the catalog + schemas they allowlisted (Databricks), or the schemas they allowlisted (SQL Server) are readable for cube SQL. The cube
  SQL **dialect follows the engine**: a Postgres connection takes PostgreSQL (the
  examples throughout this skill); a BigQuery connection takes **GoogleSQL**; a
  Snowflake connection takes **Snowflake SQL**; a Redshift connection takes **Redshift
  SQL** (a PostgreSQL dialect); a Databricks connection takes **Databricks SQL** (Spark
  SQL - lowercase-folding, backtick-quoted identifiers); a SQL Server connection takes **T-SQL** (Transact-SQL - `[bracket]`-quoted identifiers, and it requires a read-only login) - see the dialect table in `references/cube.md`.
  `list_connections` returns each connection's `engine` (`postgres` / `bigquery` /
  `snowflake` / `redshift` / `databricks` / `mssql`), so you know which dialect to write - the connection is
  otherwise chosen, introspected, and validated exactly the same way.

Use **`list_connections`** to see the warehouse connections the user owns; it
returns each connection's `id`, label, engine, status, and **observed health**, and
never returns secrets. Pass that `id` to `introspect_schema` (Step 1) and
`validate_cube_sql` (Step 3) to design and check the cube against that warehouse, then
set the spec's `source.connection` to the same `id` when you publish. `self` needs no
lookup and is not listed.

**Read `status` and `health_state` as two separate facts.** `status: active` only means
the connection is configured and enabled - it is what an explicit Test concluded, and
that Test may be days old. `health_state: failing` means the last refreshes or authoring
calls Dashies actually made to that warehouse failed at the connection level (a rejected
credential, a TLS failure, or no usable response), with `health_error` naming which. A
connection reading `active` + `failing` is a normal combination, not a contradiction.

If the connection you are about to build on reads `health_state: failing`, **say so
before you start**: the user's credential has probably expired or been rotated, and the
cube you author will validate against a warehouse that is about to stop answering. This
is not a hard block - health gates nothing, and `introspect_schema` /
`validate_cube_sql` will tell you soon enough with a real error - but surfacing it up
front saves the user a confusing round of authoring against a dead credential. It clears
by itself on the next successful call.

The gate, then: pick the data source the dashboard's numbers live in. For the
user's own business data, confirm a warehouse connection exists with
`list_connections` (if none, they connect one in the app first). For Dashies' own
metrics, use `self`. Either way, `introspect_schema` on the chosen connection
returning tables confirms you have a real schema to build a cube from.

---

## The workflow (Steps 1-7)

Steps 0-7 build and edit the dashboard. Load the reference for each step when you reach it.

- **Steps 1-3 - Design the cube and write its SQL** -> **`references/cube.md`**.
  Look at the connected schema, then design the cube: its grain (every field you
  want to filter or chart on must be a grouped dimension), keeping dimensions
  low-cardinality (bucket dates in the business zone), aggregating away anything
  sensitive (the cube ships in public bytes), and the load-bearing classification
  of every measure as **additive vs non-additive**. Then write the single read-only
  `SELECT`, validate it with `validate_cube_sql`, and handle the per-engine dialects
  (PostgreSQL / GoogleSQL / Snowflake / Redshift / Databricks / SQL Server) and large
  warehouse tables. **`validate_cube_sql` proves the SQL runs, not that it is correct:
  before publishing, verify the numbers - cross-check each additive-declared
  measure's summed cube total against an independent aggregate, which catches a
  hidden non-additive (a ratio / distinct buried in a CTE or subquery) or a fan-out
  JOIN double-count (`references/cube.md`).** This is the step that makes or breaks a
  refreshable dashboard.
- **Step 4 - Fill the Dashies spec** -> **`references/spec.md`**.
  Turn the cube into the spec: `datasets` (each dataset's `sql` + `dimensions` + `measures`,
  the mode you chose above) and `tiles` (kpi / chart / table / matrix / heatmap / scatter / treemap / waterfall / funnel / drilldown / stacked / combo / pie / donut / gauge / filter / text / custom,
  each data tile pointed at a dataset with `dataset:`), under one `source` (connection + schedule). You
  write **no `data-dash` markup, no data island, no manifest** - the compiler emits all of
  them from the spec and enforces that they agree. The two escape hatches (a `custom` tile;
  the whole-look `look` field) are in `references/spec.md`.
- **Step 5 - Pick a schedule** (inline below).
- **Step 6 - Publish the spec** with a dry run first (inline below).
- **Step 7 - Edit a published dashboard** (inline below): `get_dashboard_spec` -> change a
  field -> republish with `base_spec_hash`.

---

## Step 5 - Pick a schedule

Choose one cadence for `source.schedule`: **`manual`**, **`hourly`**, **`daily`**,
**`weekly`**, or **`monthly`**. Match it to how fast the underlying data actually moves and
the grain you chose - a dashboard bucketed by `month` gains nothing from hourly refreshes.
`manual` means it only refreshes when someone triggers it (no automatic refresh). `daily` is a
sensible default for most reporting dashboards.

`source.schedule` is only the coarse **cadence**. To set the exact timing yourself, call the
**`set_refresh_schedule`** tool after publishing (personal dashboards): pass `slug`
and `frequency` plus an optional every-N interval (`every_n`) and an
`hour`/`dow`/`dom`/`timezone` anchor - e.g. `hourly` with `every_n: 6` for every 6
hours, or `daily` with `hour: 9` and `timezone: "America/New_York"` for 09:00 ET.
Per-cadence interval caps apply (hourly every 1/2/3/4/6/8/12 hours; daily up to 30;
weekly up to 4; monthly up to 12). The end-user can still change any of it in the
app on the **Schedules** page, where Dashies honors that wall-clock time in their
zone.

---

## Step 6 - Publish the spec (dry run first)

Publish with the spec on `publish_dashboard`'s `spec` argument. The `path` slug is the
dashboard's target; a `spec.slug`, if present, must equal it. Do NOT pass `body`,
`content_type`, or `source_config` with a spec - the compiled dashboard is text/html and its
manifest is compiled from the spec.

**Dry run first.** Pass `dry_run: true` to run the full compile + validation + a read-only
SEED of every dataset and get the report back **without writing anything**. Fix any pointered
error it returns (each names the exact field - e.g. `[semantic] /datasets/main/measures/revenue:
measure \`revenue\` has no matching output column; the query outputs day, orders`), then
publish for real.

```
# 1. Dry run - compile + validate + seed, no write.
publish_dashboard({ path: "<slug>", spec: "<the YAML spec>", dry_run: true })
# -> { ok, published: false, mode_choices, warnings, obligations, bytes, [errors] }

# 2. Fix any errors, then publish.
publish_dashboard({ path: "<slug>", spec: "<the YAML spec>" })
# -> { ok: true, published: true, url, spec_hash, mode_choices, warnings, obligations, bytes }
```

Read the report back in plain words: `mode_choices` tells the user what each dataset resolved
to and why (e.g. `main -> lattice: a distinct count over low-cardinality dimensions`);
`warnings` are non-blocking advisories; `obligations` is the one place the format asks you to
run the Step-3 manual additivity cross-check (a cube built over more than one row source - a
JOIN, a CTE, a comma join or a derived table - which no static check can judge; see the
guardrail below). Share the returned `url`.

**One `warnings` entry is worth reading closely: a DISPLAYED rolled-up value that disagrees
with its siblings.** When two datasets compute the same measure with the same aggregate over
the same column, and their fully-rolled-up values differ, and a tile actually SHOWS the
differing one, the report says so and gives you four facts per dataset - aggregate, column,
scope, value. This catches the error a real playtest shipped: a cohort lattice summing a
point-in-time ARR snapshot across 24 tenure months put $596,348,393 on a KPI card against a
real $36,384,217. **It is information, not a verdict** - two datasets can legitimately
disagree, MTD beside YTD being the obvious case - so read the scope fact and decide. You do
not need to hand-write a cross-dataset total check; this is that check. A tile that reads the
measure through a dimension is never reported, because a rollup nobody renders is harmless.

The metadata args `name`, `tags`, `chart`, `visibility` work as usual; `name` defaults to the
spec's `title`. Two read-only tools inspect a personal dashboard by slug afterwards:
`get_source_config({ slug })` (the compiled manifest) and `get_refresh_status({ slug })` (is
it refreshing, its schedule, next run, recent runs). Neither triggers a refresh.

---

## Step 7 - Edit a published dashboard

If the dashboard has no stored spec yet - it was published as raw HTML (`body` +
`source_config`), or predates specs - there is nothing for `get_dashboard_spec` to read back.
Call **`derive_dashboard_spec({ slug })`** first: a read-only migration aid that reconstructs a
DRAFT spec from the dashboard's stored refresh manifest plus its current published body, and
stores nothing. The draft defaults to a whole-look `look: {from: <slug>}` reference to the
CURRENT published body, rather than inlining it - so the tool response and the eventual stored
spec both stay small (a `look_digest` in the fidelity report gives you the referenced body's
byte size, data-island count, and a sha256, without shipping the bytes themselves). Republishing
resolves that body from storage and re-seeds every dataset live exactly like any refresh, so the
markup and layout stay byte-for-byte while the displayed numbers update if the source data moved
since you derived the draft. If the body has recognizable tiles it also returns a ready-to-paste
`tiles:` block as an optional, deliberate swap onto the managed template. Review the draft, then
publish it via
`publish_dashboard({ spec })` to convert the dashboard to spec-backed - from there the loop below
applies.

To change a published spec dashboard - a new tile, a renamed measure, a different chart -
edit the spec, never the served HTML:

1. **`get_dashboard_spec({ slug })`** returns the stored spec **verbatim** (comments,
   formatting, and its `spec_hash` intact). That is your starting point - do not reconstruct
   it from memory.
2. Change the one field the user asked for.
3. Republish to the **same `path`** with `base_spec_hash` set to the hash you just read:
   `publish_dashboard({ path: "<slug>", spec: "<edited>", base_spec_hash: "<hash>" })`. The
   `base_spec_hash` is a lost-update guard: if the stored spec changed since you read it (a
   concurrent edit), the publish is rejected with `spec_conflict` and the live dashboard is
   left untouched - re-fetch with `get_dashboard_spec` and re-apply.

Every edit re-seeds and re-validates, so an edit that would break a binding is a pointered
error, not a broken live dashboard. **Renaming the slug is `update_dashboard`'s job** (it
preserves the old URL with a 301), not a spec edit - never change `slug` to rename. Never
hand-edit the served HTML: the next refresh rewrites the island and your edit would be lost
or inconsistent.

---

## Guardrails recap

- **Refresh needs a connection.** No connection -> honest static dashboard (`body`, not
  `spec`), not a fake refreshable one.
- **On the spec path the server carries the data; on the `body` path you carry it.** This is
  the reason to stay on `spec` even when hand-authoring looks quicker. A spec sends SQL and
  declarations, and the server runs the query and seeds the rows, so **the data never enters
  your context at all**. A hand-authored `body` sends the finished HTML with the rows already
  baked into it, which means those bytes pass through your context twice - once when you read
  or build the file, once when you send it as the tool argument. So the binding limit on the
  `body` path is **your own context window, not `MAX_PUBLISH_BYTES`**: the advertised publish
  ceiling is 5 MB, but a real session hit the wall around 40KB of island and spent seven
  shrink cycles there, dropping a whole dataset, three dimensions, half the time window and 35
  of 60 detail rows to fit. If you find yourself deleting real content to make a payload fit,
  that is the signal you are on the wrong path - go back to `spec` rather than shrinking.
- **You write the SPEC; the server writes the dashboard.** No hand-rolled `data-dash` markup,
  no `#dashies-data` island, no runtime marker, no `source_config` manifest - the compiler
  emits and enforces all of them. A structural fault (a role-less tile, a binding to a column
  the SQL never returns, an unknown key) is a pointered publish error, not a rendering
  surprise. Always **dry-run first** and fix the pointered errors before publishing.
- **Additivity is correctness, not style - and it is enforced.** A `cube` dataset rejects SQL
  that computes `count(DISTINCT ...)`, `avg`, `median`, percentiles, `stddev`, `variance`, or
  `mode()`, and a `cube` measure declared with a non-additive `agg` is a schema error;
  `validate_cube_sql` (pass the dataset's `mode`) warns about the same SQL before you get
  there. In a `cube` only additive measures are stored and ratios are declared as a `ratio`
  measure (`{ num, den }`); a low-cardinality distinct count can ride as a dimension. The
  moment a metric is genuinely non-additive, leave `cube`: use **`lattice`** (the grain
  compiler) when your filter/chart/table dimensions are all low-cardinality, **`hybrid`** when
  those dimensions also need multi-select / range filters on a non-composable measure, else
  **`rows`** (`references/cube.md`).
- **Validate proves it RUNS; you must prove it is CORRECT.** `validate_cube_sql` and the
  publish gate catch the common non-additive SQL by inspecting the text, but a ratio or
  distinct hidden in a CTE / subquery, or a fan-out JOIN double-count, sails through and
  refreshes to a plausible wrong number. Before publishing, cross-check each
  additive-declared measure's summed cube total against an independent direct aggregate; if
  they differ it is non-additive or double-counting - fix it (a `ratio` measure, a
  `lattice`/`hybrid` dataset, or pre-aggregate the join). The publish report surfaces this as
  an **`obligation`** whenever a cube is built over MORE THAN ONE ROW SOURCE - a JOIN, a CTE,
  a comma join, or a derived table - however the measure is written. That is a PROMPT to run
  this cross-check, never a substitute for it. A required correctness gate, not a nicety.
  Read the converse carefully: an EMPTY `obligations` means the cube reads one row source, so
  it cannot fan out. It is NOT a statement that your numbers are right - a non-additive
  aggregate or a mis-declared measure on a single-source cube is still yours to check.
- **Every aggregate rides inline, so a `lattice`/`hybrid` must be bounded.** A
  `lattice`/`hybrid` dimension must declare its bound (`domains` for a category, `buckets` for
  a date); its cell count is about the product of each dimension's (cardinality + 1), so keep
  every dimension low-cardinality. If it grows past the inline cap, drop or bound a dimension
  (`references/cube.md`) - a lattice can never offload to Parquet.
- **Only a `rows` dataset offloads, and only on a warehouse.** `data: { mode: parquet }` is
  valid on `mode: rows` alone, needs a warehouse `source.connection` (`self` has no offload),
  and at most 2 per dashboard. Each of those is a pointered publish error, not a surprise:
  parquet on a `cube`/`lattice`/`hybrid`, parquet on `self`, a third parquet dataset, and
  `rows_window` alongside parquet (the window bounds the INLINE slice and does nothing to an
  extract) are all refused at publish. A parquet dataset publishes EMPTY on purpose and its
  tiles read "Updating" until the first refresh lands the object - the seed proves its SQL and
  types its columns, but the sample rows are never baked, because a truncated sample shown as
  the whole truth is the silent-wrong class this format exists to kill.
- **The cube is public, aggregated bytes.** No PII, no raw rows, no small-cell
  re-identification. (A `rows` dataset ships row-level bytes on purpose - which makes this
  rule stricter there, not looser: every shipped column is world-readable.)
- **The SQL runs forever.** One read-only SELECT per dataset, relative time windows, low grain.
- **Numeric honesty is automatic.** The runtime renders every value exactly or shows `-`;
  a past-precision value is never a rounded-wrong number. You do not manage this.
- **Style:** match Dashies' sober tone. Use plain ASCII hyphens, never em dashes or
  en dashes, in any dashboard copy or your prose. Do not give time estimates ("a few
  minutes", "quick") - describe scope, not duration. Do not invent features the data
  does not support.
- **Beauty and brand:** the default template is intentionally plain. To make a
  dashboard genuinely beautiful and tailored to the user's company (brand colors
  and type via the spec's `theme`, or deeper via the companion `dashies-design` skill),
  layer styling once the structure and data here are in place. It never changes the
  datasets, the compiled island, or how the dashboard refreshes.

---

## References

Load the one you need for the step you are on; do not front-load them all.

| Reference | Covers | Load for |
|---|---|---|
| `references/cube.md` | Introspection; cube grain, low-cardinality dimensions, timezone bucketing, sensitivity, additive-vs-non-additive measures; the read-only `SELECT`, `validate_cube_sql`, the PostgreSQL / GoogleSQL / Snowflake / Redshift / Databricks / SQL Server dialects, large-warehouse guidance, the v3 `GROUP BY CUBE` grain-compiler SQL, and the `hybrid` lattice-plus-`rows_sql` shape (and when multi-value filters need it) | Steps 1-3 |
| `references/spec.md` | The Dashies spec: the house YAML rules, the full field tables (top level, `source`, `datasets` + the four modes, `dimensions`, `measures` with agg/ratio + per-mode allowlists, `unit`, the eighteen `tiles` types incl. the `waterfall` / `funnel` sequence objects, the `scatter` / `treemap` objects, the `matrix` pivot, the `heatmap`, the `drilldown` breakdown, and the `stacked` / `combo` charts, `layout`, `theme`), the schema URL, and the two escape hatches (a `custom` tile; the whole-look `look` field) | Step 4 |
| `references/dashboard.md` | The escape hatches + the legacy hand-authored path (marked fallback): the self-contained HTML + `data-dash` bindings, the data island shape + serve-time runtime marker + sandbox CSP for a `custom` tile / custom renderer, and the single-manifest `source_config` (v1 / v3 / v2 incl. the placeholder + parquet flow) for the `body`+`source_config` publish you drop to only when the spec cannot express the dashboard | Escape hatches; legacy |

The references carry the condensed contract you need to author a dashboard; the full
source-of-truth, `web/dashboard-runtime/CONTRACT.md`, is maintainer depth for the monorepo,
not required reading here. The tool calls in this skill (`list_connections`,
`introspect_schema`, `validate_cube_sql`, `publish_dashboard` with `spec` + `dry_run` +
`base_spec_hash`, `get_dashboard_spec`, `derive_dashboard_spec`, `set_refresh_schedule`,
`get_source_config`, `get_refresh_status`) match the shipped MCP tools.
