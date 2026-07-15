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
  constraints, choosing a schedule, and the source_config manifest - both
  manifest v1 (additive cube; the additive-only rule is enforced at publish) and
  manifest v2 (row-level, for distinct counts / medians / percentiles /
  true averages that stay correct under viewer filters), plus warehouse scale
  rules for authoring against big tables. For a
  one-off static dashboard with no live data source behind it, you do not need
  this skill - just generate HTML and publish it.
---

# Building a refreshable Dashies dashboard

Dashies can refresh a published dashboard on a schedule **without re-running a
model**. You (the AI) author the dashboard once. Alongside the HTML you emit
three things that let Dashies keep it fresh on its own forever:

1. An embedded JSON **data cube** - the data, pre-aggregated to the dashboard's
   grain - inside a `<script type="application/json" id="dashies-data">` island.
2. An inlined client **runtime** (vanilla JS, no dependencies) that reads the
   cube, fills the marked-up slots, and re-slices the cube in the browser when a
   filter changes - with zero network calls and no browser storage.
3. A **manifest** (the cube SQL + the dimensions, measures, format,
   and schedule) stored in the dashboard's `source_config`.

Dashies then re-runs the manifest's SQL on the chosen cadence and rewrites **only**
the data island in the stored HTML. The runtime and your markup are never touched.
No model is in the refresh loop, so the dashboard stays correct and cheap.

This skill is how you produce that initial dashboard correctly. The hard parts are
not the HTML - they are **cube design** and **measure additivity**, because the
cube SQL you write here runs unattended forever and the runtime can only re-slice
data that is additive. Get those right and everything downstream is mechanical.

Two island/manifest contracts exist. **v1** (the baseline flow) ships a
pre-aggregated **additive cube** the runtime re-sums in JS - small, engine-free,
and correct only for additive measures. **v2** ships **row-level rows** and recomputes the metrics from those rows in the browser, so non-additive metrics (distinct counts,
medians, percentiles, true averages) stay correct under any viewer filter. Steps
0-6 apply to both; everything v2 changes is collected in `references/dashboard.md`.
The additive rule is **enforced at publish**, not advisory: a v1 manifest whose
`cube_sql` computes `count(DISTINCT ...)`, `avg`, `median`, `percentile_cont` /
`percentile_disc`, `stddev`, `variance`, or `mode()` is rejected with an error
naming each detected construct and pointing at manifest v2. So the choice is
mechanical: the moment any measure is non-additive, author v2; keep v1 as the light
path for purely-additive cubes (a ratio of two additive measures still fits v1 via
`derived`).

> The binding layer (the exact data-island JSON shape and every `data-dash`
> attribute) is specified in **`web/dashboard-runtime/CONTRACT.md`** (contracts
> v1 and v2 - its section 8 is the v2 row-level contract). That document is
> authoritative; this skill teaches you how to *use* it and condenses the parts
> you need into the references below. When in doubt, read CONTRACT.md.

## How this skill is organized

This file is the **orchestrator**: the gate, the workflow spine, the schedule and
publish steps, and the guardrails. The depth for each step lives in a **reference
file** you load when you reach that step - do not front-load them all. The map is at
the bottom under **References**.

---

## Step 0 - Gate: is there a connected data source?

**A dashboard can only refresh against a live data source. No connection means
nothing to re-run, so there is nothing to keep fresh.**

- **Connection present** -> build a refreshable dashboard with this skill (steps 1-6).
- **No connection** -> do NOT fake a refreshable dashboard. Build a normal,
  one-shot **static** dashboard instead (generate self-contained HTML and publish
  it the ordinary way), and tell the user it will not auto-refresh because no data
  source is connected. Attaching a manifest with no connection behind it produces a
  dashboard Dashies can never refresh, which is worse than an honest static one.

Two kinds of data source can back a refreshable dashboard:

- **`self`** - Dashies' own database, a built-in connection named `self` that is
  always available and needs no setup. It exposes a curated, no-PII metrics view.
  Pass `connection: "self"`, or omit `connection` entirely - it is the default.
- **A warehouse connection you own** - a paid user connects their own warehouse (a
  **Postgres** database, a **BigQuery** project, a **Snowflake** account, or an
  **Amazon Redshift** warehouse) in the Dashies web app, on the **Connections** page
  (`/app/connections`). Credentials are entered through that SPA form only; they never
  pass through the AI or the MCP, so you cannot connect a warehouse for the user - if
  they need one and have not connected it, they do that in the app first. Once
  connected, the tables they imported (Postgres) or the datasets/databases they
  allowlisted (BigQuery / Snowflake / Redshift) are readable for cube SQL. The cube
  SQL **dialect follows the engine**: a Postgres connection takes PostgreSQL (the
  examples throughout this skill); a BigQuery connection takes **GoogleSQL**; a
  Snowflake connection takes **Snowflake SQL**; a Redshift connection takes **Redshift
  SQL** (a PostgreSQL dialect) - see the dialect table in `references/cube.md`.
  `list_connections` returns each connection's `engine` (`postgres` / `bigquery` /
  `snowflake` / `redshift`), so you know which dialect to write - the connection is
  otherwise chosen, introspected, and validated exactly the same way.

Use **`list_connections`** to see the warehouse connections the user owns; it
returns each connection's `id`, label, engine, and status, and never returns
secrets. Pass that `id` to `introspect_schema` (Step 1) and `validate_cube_sql`
(Step 3) to design and check the cube against that warehouse, then set the
manifest's `connection` to the same `id` when you publish. `self` needs no lookup
and is not listed.

The gate, then: pick the data source the dashboard's numbers live in. For the
user's own business data, confirm a warehouse connection exists with
`list_connections` (if none, they connect one in the app first). For Dashies' own
metrics, use `self`. Either way, `introspect_schema` on the chosen connection
returning tables confirms you have a real schema to build a cube from.

---

## The workflow (Steps 1-6)

Steps 0-6 build the dashboard. Load the reference for each step when you reach it.

- **Steps 1-3 - Design the cube and write its SQL** -> **`references/cube.md`**.
  Look at the connected schema, then design the cube: its grain (every field you
  want to filter or chart on must be a grouped dimension), keeping dimensions
  low-cardinality (bucket dates in the business zone), aggregating away anything
  sensitive (the cube ships in public bytes), and the load-bearing classification
  of every measure as **additive vs non-additive**. Then write the single read-only
  `SELECT`, validate it with `validate_cube_sql`, and handle the per-engine dialects
  (PostgreSQL / GoogleSQL / Snowflake) and large warehouse tables. This is the step
  that makes or breaks a refreshable dashboard.
- **Step 4 - Build the HTML and attach the manifest** -> **`references/dashboard.md`**.
  Assemble the one self-contained HTML file - your markup with `data-dash` slots,
  the `#dashies-data` island, the inlined runtime, all under the sandbox CSP - then
  publish it with the `source_config` manifest (v1 additive, or v2 row-level for
  distinct counts / medians / percentiles / true averages).
- **Step 5 - Pick a schedule** (inline below).
- **Step 6 - Publish** (inline below); the manifest contract - v1 and v2 - is in
  **`references/dashboard.md`**.

---

## Step 5 - Pick a schedule

Choose one cadence: **`manual`**, **`hourly`**, **`daily`**, **`weekly`**, or
**`monthly`**. Match it to how fast the underlying data actually moves and the grain
you chose - a dashboard bucketed by `month` gains nothing from hourly refreshes.
`manual` means it only refreshes when someone triggers it (no automatic refresh). `daily` is a
sensible default for most reporting dashboards. This value goes in the manifest's
`schedule` and sets the dashboard's refresh frequency.

The manifest's `schedule` is only the coarse **cadence** - it stays that coarse
string, no manifest-shape change. To set the exact timing yourself, call the
**`set_refresh_schedule`** tool after publishing (personal dashboards): pass `slug`
and `frequency` plus an optional every-N interval (`every_n`) and an
`hour`/`dow`/`dom`/`timezone` anchor - e.g. `hourly` with `every_n: 6` for every 6
hours, or `daily` with `hour: 9` and `timezone: "America/New_York"` for 09:00 ET.
Per-cadence interval caps apply (hourly every 1/2/3/4/6/8/12 hours; daily up to 30;
weekly up to 4; monthly up to 12). The end-user can still change any of it in the
app on the **Schedules** page, where Dashies honors that wall-clock time in their
zone.

---

## Step 6 - Publish with the manifest

Produce the inlined HTML (Step 4) and publish it with the manifest attached as
`source_config`, the slug, and the schedule.

```
publish_dashboard({
  path: "<slug>/index.html",
  content_type: "text/html",
  body: "<inlined HTML>",
  source_config: { ...manifest, including its schedule... }
})
```
The manifest rides on `publish_dashboard`'s optional `source_config` argument - there
is **no separate `frequency` argument**. The cadence is the manifest's own `schedule`
field (Step 5); the server derives the dashboard's `frequency` and `status` from it.
A publish with no `source_config` is an ordinary static dashboard. (The metadata args
`name`, `tags`, `chart`, `visibility`, `workspace` work as usual.) The full manifest
contract - every field, the invariants, and manifest v2 - is in
**`references/dashboard.md`**.

The publish stores your HTML and manifest and returns the dashboard's URL - share
it. From then on Dashies refreshes the cube on the schedule with no model involved.

To verify after publishing, two read-only tools inspect a personal dashboard by its
slug: `get_source_config({ slug })` returns the stored manifest exactly as saved (so
you can confirm it stored correctly, or review it before republishing with an edit),
and `get_refresh_status({ slug })` returns whether it is refreshing, its schedule,
the next run time, and the recent run history (so you can confirm it is being kept fresh). Neither triggers a refresh or changes the schedule.

---

## Guardrails recap

- **Refresh needs a connection.** No connection -> honest static dashboard, not a
  fake refreshable one.
- **Additivity is correctness, not style - and it is enforced.** A v1 publish
  rejects cube SQL that computes `count(DISTINCT ...)`, `avg`, `median`,
  percentiles, `stddev`, `variance`, or `mode()`; `validate_cube_sql` warns about
  the same SQL before you get there. In a v1 cube only additive measures are
  stored and ratios are `num` / `den`; a low-cardinality distinct count can ride
  as a dimension; distinct counts, averages, medians, and continuous percentiles
  move the dashboard to manifest v2, which recomputes them from row-level data as
  v2 measures; the aggregates v2 cannot declare yet (`percentile_disc`, `stddev`
  / `variance`, `mode()`) stay out (`references/cube.md`).
- **The cube is public, aggregated bytes.** No PII, no raw rows, no small-cell
  re-identification. (A v2 island ships row-level bytes on purpose - which makes
  this rule stricter there, not looser: every shipped column is world-readable.)
- **The SQL runs forever.** One read-only SELECT, relative time windows, low grain.
- **At warehouse scale, keep the cube cheap.** Big tables want a small grain, a
  tight time window, and grouping on real columns; a row-level cube too large to
  inline moves to a v2 + parquet dashboard (`references/cube.md`).
- **The sandbox is strict.** No storage, no network, no wholesale `<body>` replace.
- **Style:** match Dashies' sober tone. Use plain ASCII hyphens, never em dashes or
  en dashes, in any dashboard copy or your prose. Do not give time estimates ("a few
  minutes", "quick") - describe scope, not duration. Do not invent features the data
  does not support.
- **Beauty and brand:** the default template is intentionally plain. To make a
  dashboard genuinely beautiful and tailored to the user's company (brand colors
  and type, a real header, hero-metric hierarchy, and the runtime charts retinted
  to the brand), use the companion `dashies-design` skill once the structure and
  data here are in place. It layers styling only; it never changes the cube, the
  data island, or how the dashboard refreshes.

---

## References

Load the one you need for the step you are on; do not front-load them all.

| Reference | Covers | Load for |
|---|---|---|
| `references/cube.md` | Introspection; cube grain, low-cardinality dimensions, timezone bucketing, sensitivity, additive-vs-non-additive measures; the read-only `SELECT`, `validate_cube_sql`, the PostgreSQL / GoogleSQL / Snowflake dialects, and large-warehouse guidance | Steps 1-3 |
| `references/dashboard.md` | The self-contained HTML (`data-dash` bindings, the data island, inlining the runtime, sandbox CSP) and the `source_config` manifest - v1 (additive) and v2 (row-level, the placeholder flow, caps, parquet mode) | Steps 4 + 6 |

For the exhaustive binding reference read `web/dashboard-runtime/CONTRACT.md`. The
tool calls in Steps 1, 3, and 6 (`introspect_schema`, `validate_cube_sql`, and
`publish_dashboard` with `source_config`) match the shipped MCP tools.
