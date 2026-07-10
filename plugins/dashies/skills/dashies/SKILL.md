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
  manifest v2 (row-level + DuckDB, for distinct counts / medians / percentiles /
  true averages that stay correct under viewer filters), plus warehouse scale
  rules for authoring against big tables. For a
  one-off static dashboard with no live data source behind it, you do not need
  this skill - just generate HTML and publish it.
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

Two island/manifest contracts exist. **v1** (the baseline flow below) ships a
pre-aggregated **additive cube** the runtime re-sums in JS - small, engine-free,
and correct only for additive measures. **v2** ships **row-level rows** and runs
real SQL in the browser via DuckDB-WASM, so non-additive metrics (distinct counts,
medians, percentiles, true averages) stay correct under any viewer filter. Steps
0-6 apply to both; everything v2 changes is collected in **Manifest v2** below.
The additive rule is **enforced at publish**, not advisory: a v1 manifest whose
`cube_sql` computes `count(DISTINCT ...)`, `avg`, `median`, `percentile_cont` /
`percentile_disc`, `stddev`, `variance`, or `mode()` is rejected with an error
naming each detected construct and pointing at manifest v2. So the choice is
mechanical: the moment any measure is non-additive, author v2 - its measures
carry the non-additive set that matters (`count_distinct`, `avg`, `median`,
`percentile_cont`); keep v1 as the light path for purely-additive cubes (a
ratio of two additive measures still fits v1 via `derived`).

> The binding layer (the exact data-island JSON shape and every `data-dash`
> attribute) is specified in **`web/dashboard-runtime/CONTRACT.md`** (contracts
> v1 and v2 - its section 8 is the v2 row-level contract). That document is
> authoritative; this skill teaches you how to *use* it and condenses the parts
> you need below. When in doubt, read CONTRACT.md.

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

Two kinds of data source can back a refreshable dashboard:

- **`self`** - Dashies' own database, a built-in connection named `self` that is
  always available and needs no setup. It exposes a curated, no-PII metrics view.
  Pass `connection: "self"`, or omit `connection` entirely - it is the default.
- **A warehouse connection you own** - a paid user connects their own warehouse (a
  **Postgres** database or a **BigQuery** project) in the Dashies web app, on the
  **Connections** page (`/app/connections`). Credentials are entered through that
  SPA form only; they never pass through the AI or the MCP, so you cannot connect a
  warehouse for the user - if they need one and have not connected it, they do that
  in the app first. Once connected, the tables they imported (Postgres) or the
  datasets they allowlisted (BigQuery) are readable for cube SQL. The cube SQL
  **dialect follows the engine**: a Postgres connection takes PostgreSQL (the
  examples throughout this skill); a BigQuery connection takes **GoogleSQL** (see
  "GoogleSQL dialect" in Step 3). `list_connections` returns each connection's
  `engine` (`postgres` / `bigquery`), so you know which dialect to write - the
  connection is otherwise chosen, introspected, and validated exactly the same way.

Use **`list_connections`** to see the warehouse connections the user owns; it
returns each connection's `id`, label, engine, and status, and never returns
secrets. Pass that `id` to `introspect_schema` (Step 1) and `validate_cube_sql`
(Step 3) to design and check the cube against that warehouse, then set the
manifest's `connection` to the same `id` when you publish (see Manifest v1).
`self` needs no lookup and is not listed.

The gate, then: pick the data source the dashboard's numbers live in. For the
user's own business data, confirm a warehouse connection exists with
`list_connections` (if none, they connect one in the app first). For Dashies' own
metrics, use `self`. Either way, `introspect_schema` on the chosen connection
returning tables confirms you have a real schema to build a cube from.

---

## Step 1 - Introspect the connected schema

Before designing anything, look at what is actually there. Call the introspection
tool to enumerate the tables, columns, and types of the connected source.

```
introspect_schema({ connection: "self" })
```
`connection` is optional and defaults to `"self"`; pass a warehouse connection `id`
(from `list_connections`) to introspect one of your own warehouses instead.
The response is a per-table column list, then a `BEGIN_JSON ... END_JSON` block:
`{ connection, tables: [{ name, columns: [{ name, type }], row_estimate? }] }`. For a
warehouse connection each table also carries an approximate row count (shown as
`Table: orders (~1,000,000 rows)`, from the connection's stored planner estimate) so
you can tell a small table from a huge one before the first timeout; `self` and
never-analyzed tables have none. It does not report per-column cardinality, so judge
that from what each column means (below) and confirm the real cube size later with
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
  reports the actual cube row count, which is the real check. It also does not
  report which values a categorical column holds, so confirm enum literals with a
  `validate_cube_sql` GROUP BY before you filter on them (Step 3).
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
is recoverable (watch small-cell counts that could re-identify someone). In a v1
cube, carry aggregates, never raw row-level or personal data. (A manifest v2
dashboard ships row-level rows on purpose - there this rule tightens to
per-column: never select a column you would not publish. See Manifest v2.) This
is why the Phase 1 `self` connection targets a no-PII view.

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
goes silently wrong the moment the user filters. And this is **enforced at
publish**: a v1 manifest is rejected outright when its `cube_sql` computes
`count(DISTINCT ...)`, `avg(...)`, `median(...)`, `percentile_cont(...)` /
`percentile_disc(...)`, `stddev(...)` (or `stddev_pop` / `stddev_samp`),
`variance(...)` (or `var_pop` / `var_samp`), or `mode()` - the error names each
detected construct and points at manifest v2. **The primary path for a
non-additive metric is manifest v2** (below): ship row-level rows and let real SQL
recompute it under every filter. Two v1-shaped workarounds remain, valid exactly
because their SQL avoids the banned constructs:

- **Averages, rates, ratios, "per" metrics, percentages** -> store the
  **numerator and denominator as two additive measures** and let the runtime divide
  them at render time with a `data-num` / `data-den` ratio binding. `sum(num) /
  sum(den)` stays correct under every filter because both parts are additive.
  Example: store `revenue` and `orders`; render "revenue per order" as the ratio.
  Store `conversions` and `visits`; render "conversion rate" as the ratio (the
  `percent` format expects a 0..1 ratio, which this produces - do not pre-multiply
  by 100). Never store a pre-divided average: an average of averages is wrong.
  (The publish gate cannot see a hand-built division - `sum(amount) /
  nullif(count(*), 0)` names no banned function - so this rule stays on you: keep
  the division out of the SQL and let the ratio binding divide.)
- **Distinct counts** (distinct active users, distinct accounts) are non-additive:
  distinct counts of disjoint slices do not add up. If the thing you are counting
  is itself low-cardinality, carry it as a **dimension** so the runtime recovers
  the count by grouping - the SQL never computes a distinct count, so v1 takes it.
  Every other shape - `count(DISTINCT ...)` per slice or at the full grain - is
  now rejected at v1 publish (and a spelling the sniff cannot see would still
  re-sum wrong). Author it as a v2 `count_distinct` measure instead.
- **Medians and percentiles** cannot be reconstructed from sums at all, and the
  old per-slice precompute (`median(...)` or `percentile_cont(...)` in the SELECT)
  is now **rejected at v1 publish**. A median or percentile metric means manifest
  v2 (`agg: "median"` / `"percentile_cont"`) - or leaving it out. There is no
  ratio trick for a median.
- **Spread and mode metrics** (`stddev` / `variance` and their `_pop` / `_samp`
  variants, `mode()`, `percentile_disc`) are rejected at v1 publish like the
  rest, but v2 has **no measure for them yet** - its non-additive aggs are
  `avg`, `count_distinct`, `median`, and `percentile_cont`. Leave these metrics
  out, or redesign them onto a supported aggregate; do not try to precompute
  them in v2 SQL either (a precomputed spread column re-aggregates wrong the
  same way).

**When in doubt, author v2.** A dashboard whose point is distinct counts, medians,
percentiles, or true averages under viewer filters should ship row-level data and
recompute in the browser instead of contorting the grain - that is exactly what
**Manifest v2** (below) is for. The additivity rules in this step are what v1's
re-summing runtime demands; v2 lifts them because real SQL recomputes every metric
from rows. You will meet the same signal while authoring: `validate_cube_sql`
appends an advisory warning ("requires manifest v2") whenever the SQL computes one
of the constructs above. The advisory never blocks validation - but a v1 publish
of that SQL will fail, so treat it as the version decision arriving early.

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
- **Bound the result** by keeping the grain low-cardinality (Step 2). The hard
  refresh caps are 100,000 rows / 8 MB, but a v1 cube should stay orders of
  magnitude below them (Step 2b's few hundred to a few thousand rows).
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
If the SQL computes a non-additive aggregate (the Step 2d list: `count(DISTINCT
...)`, `avg`, `median`, percentiles, `stddev`, `variance`, `mode()`), the response
also carries an advisory `Warning:` that the SQL requires manifest v2. The advisory
never fails validation - but it is the publish gate speaking early: a v1 publish of
that SQL will be rejected, so settle the manifest version here, before you build
the island.

Check it: confirm `columns` match your planned dimension and measure keys exactly,
`row_count` is sane (low hundreds to low thousands), and the values look right.
**Keep the returned `rows` - that is your initial cube, pasted verbatim into the
data island (Step 4).** If the grain is wrong or a column is missing, fix the SQL
here, not after publishing.

**Confirm categorical values before you filter on them.** `introspect_schema`
returns column names and types only, not the set of values a column actually holds.
So before you write a `countif(...)` or `count(*) filter (where col = 'X')`
predicate against a categorical column, confirm its real values with a one-line
`validate_cube_sql` GROUP BY - `select col, count(*) from t group by 1 order by 2
desc` - and read the literals off the result. Never guess an enum literal: a wrong
one does not error, it silently matches nothing and the measure reads zero.

### GoogleSQL dialect (BigQuery connections)

Everything above is engine-independent - the single read-only SELECT, grain ==
`dimensions[].key`, relative time windows, the additive-vs-non-additive split, the
v1/v2 choice. Only the **SQL dialect** changes: a BigQuery connection runs
**GoogleSQL** on BigQuery itself (not PostgreSQL through an FDW), so the Postgres
idioms in the examples above must be written the BigQuery way. `validate_cube_sql`
against the BigQuery connection is the contract, exactly as for Postgres - author
against it, not from memory.

| Need | PostgreSQL (the examples above) | GoogleSQL (a BigQuery connection) |
|---|---|---|
| Table reference | unqualified `from orders` | backtick-qualified `` from `project.dataset.table` `` (the datasets `introspect_schema` lists) |
| Bucket a date | `date_trunc('month', created_at)::date` | `date_trunc(created_at, MONTH)` (a `DATE`) / `timestamp_trunc(created_at, MONTH)` (a `TIMESTAMP`) - arg order `(expr, part)`, the part a bareword, no cast |
| Current time | `now()` | `current_timestamp()` / `current_date()` |
| Relative window | `where created_at >= now() - interval '12 months'` | `where created_at >= timestamp_sub(current_timestamp(), interval 12 month)` (or `date_sub(current_date(), interval 90 day)`) - unquoted `interval N unit`, singular unit |
| Conditional count | `count(*) filter (where is_signup)` | `countif(is_signup)` |
| Distinct count | `count(distinct customer_id)` | `count(distinct customer_id)` (same) |

The additivity gate is dialect-independent: a v1 publish still rejects
`count(distinct ...)`, `avg`, `median`, percentiles, `stddev`, `variance`, and
`mode()` in `cube_sql` whatever the engine, so a non-additive BigQuery metric is a
v2 measure over row-level rows just as on Postgres. Keep windows relative -
GoogleSQL's `current_*` functions evaluate per run, so the window slides without a
hardcoded date.

### Warehouse scale rules (read before authoring against a big table)

**These pushdown rules are specific to a Postgres connection** (its cube reads
remote tables through `postgres_fdw`). A **BigQuery** connection does not use the
FDW at all: its cube runs as GoogleSQL directly on BigQuery through the REST query
API, so the aggregation always happens on BigQuery natively and there is no pushdown
cliff - a `date_trunc(...)` group-by or a join is evaluated server-side, not
streamed. Design a BigQuery cube against bytes scanned and the island/parquet caps
(below), not FDW pushdown; a BigQuery cube too large to inline uses the same **v2 +
parquet** path, extracted by paging the query result and encoding Parquet in-Worker
(no FDW, no `COPY`). The rest of this subsection applies to Postgres connections.

On a Postgres connection the cube SQL reads remote tables through `postgres_fdw`,
and at scale **pushdown decides everything**: either the aggregation runs ON the
warehouse, or the raw rows stream over the wire into the authoring path's 8 s
statement budget. Measured on a 1M-row fact table over a cross-region connection:

- **These push down and are fast even at 1M rows (~1-2 s):** a plain `GROUP BY` on
  real columns, `count(distinct ...)`, and `percentile_cont(...) within group
  (...)`. Whole-table breakdown KPI cubes over a big table are genuinely fine.
  (Speed is not permission: `count(distinct ...)` and `percentile_cont(...)` are
  non-additive, so a v1 publish rejects them in `cube_sql` - and a v2 manifest
  does not write them in the SQL either: its `cube_sql` returns the underlying
  rows and the metric is a v2 **measure** (`count_distinct` / `percentile_cont`)
  the engine recomputes.)
- **These do NOT push down:** a `GROUP BY` on an expression (`date_trunc('month',
  ts)`) and any aggregate over a `JOIN`. The remote then ships the raw window and
  the aggregation happens locally. The streaming budget is roughly **80-90k rows
  inside the 8 s authoring window** (cross-region), so a date-bucketed trend
  cube on a big table needs a tight time window (days at day grain, not
  months) - or a shape that avoids the local aggregation entirely.
- **Pre-bucket the date in the warehouse instead of `date_trunc()` in the cube.**
  A `date_trunc(...)` in the `GROUP BY` is the single most common scale timeout: it
  cannot push down, so the whole window streams back before it is bucketed. If the
  warehouse can carry a pre-truncated `day`/`week`/`month` column (a stored or
  generated column, or one materialized by the user's own ETL), `GROUP BY` that
  real column - a plain-column grouping pushes down, so only the bucketed rows
  cross the wire. Where you cannot add a column, keep the window tight (above) or
  move the dashboard to parquet (below).
- **Star schemas need the two-step join rewrite.** A naive aggregate over a join
  times out at scale; aggregate the fact table REMOTELY first, keyed by the join
  key, then join the small dimension table and re-aggregate:

  ```sql
  -- TIMES OUT at 1M rows: aggregate-over-join never pushes down,
  -- so every fact row streams before grouping
  select p.category, o.region, count(*) as orders, sum(o.amount) as revenue
  from orders_big o
  join products p on p.product_id = o.product_id
  group by 1, 2
  ```

  ```sql
  -- FAST: step 1 aggregates the fact table remotely (pushes down, keyed by
  -- the join key); step 2 joins the small dimension result and re-aggregates
  with fact as (
    select product_id, region, count(*) as orders, sum(amount) as revenue
    from orders_big
    group by 1, 2
  )
  select p.category, f.region,
         sum(f.orders) as orders, sum(f.revenue) as revenue
  from fact f
  join products p on p.product_id = f.product_id
  group by 1, 2
  ```

  Both measures stay additive through the second aggregation (sums of sums), so
  the rewrite is exact - verified to the cent at 1M rows.
- **Keep writing relative time windows.** `where ts >= now() - interval '30
  days'` is spliced to a literal timestamp per run at execution time, so the
  remote sees a pushable constant AND the window keeps sliding. Hardcoded dates
  still freeze forever - the rule above stands.
- **Check table size before you design, and let it pick inline vs parquet.** For a
  warehouse connection `introspect_schema` now shows an approximate row count per
  table (`Table: orders (~1,000,000 rows)`, from the connection's stored planner
  estimate), so a 1,000-row table and a 1,000,000-row one are distinguishable before
  anything times out. For an exact count, or a table with no stored estimate,
  measure: `validate_cube_sql({ sql: "select count(*) as n from <table>",
  connection })` - a bare full-table aggregate pushes down and returns fast even on
  millions of rows. Use the size to choose the shape AND the data mode: an aggregated
  cube that fits the 100,000-row / 8 MB island stays inline; a row-level v2 cube too
  large to inline goes to parquet (below).
- **The caps:** a refresh writes at most **100,000 rows / 8 MB** into the island
  (self and warehouse connections alike). The 8 s statement budget binds the
  authoring path (`validate_cube_sql`); a scheduled refresh runs with slightly
  more headroom, but do not design a cube that needs it - a cube that validates
  near 8 s warm can still flake on a cold warehouse start. Full cap details and
  the publish-size asymmetry are under Manifest v2.
- **Parquet is the scale answer - it moves the work off the FDW.** The workarounds
  above (pre-bucketing, the two-step join rewrite, tight windows) keep the INLINE
  aggregated path within the FDW pushdown limits. A warehouse **v2 + parquet**
  dashboard avoids those limits at the source: its refresh extracts the cube with a
  direct streamed `COPY` that runs NATIVELY on the warehouse, not through
  `postgres_fdw`. A v2 cube returns row-level rows, so there is no remote `GROUP BY`
  to push down at all - DuckDB does the aggregation in the browser - and any
  dimension join the cube needs runs at the source at native speed instead of
  streaming through the FDW. This is an extract-time win: `validate_cube_sql` and
  inline refresh still go through the FDW, so validate a parquet cube against a
  narrow window, or publish it pending and let the first refresh fill it. For heavy
  warehouse analytics - date-bucketed trends, star-schema joins, non-additive
  metrics over a big table - reach for parquet; treat the pushdown workarounds above
  as what keeps a deliberately-small aggregated inline cube fast. See "Parquet mode"
  under Manifest v2.
- **Reference imported tables exactly as `validate_cube_sql` accepts them (defense in
  depth).** Your warehouse tables are read **unqualified** in cube SQL (`from
  orders`): the connection exposes them on its read-only executor's schema search
  path, which is an internal per-connection schema, not the schema name you imported -
  so `from orders` resolves but a remote `from analytics.orders` qualifier does not
  validate. `validate_cube_sql` is the contract: a reference it accepts is one a
  refresh resolves. A warehouse v2 + parquet cube runs that same SQL directly on your
  warehouse at extract time, and that session is now pointed at your imported
  schema(s) so the unqualified name resolves identically there too. Keep table
  references unqualified and let `validate_cube_sql` confirm the cube before you
  publish - do not hand-qualify with a remote schema to "fix" an extract, since that
  passes on the warehouse but fails validate.

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

- `version` is `1` (the island contract version; a v2 island says `2` - see
  Manifest v2).
- `updated_at` is when you computed this cube (ISO 8601); the cron overwrites it.
- Each `cube` row is one `GROUP BY` result: a flat object whose keys are exactly the
  dimension keys + measure keys. Paste in the rows `validate_cube_sql` returned.
- `dimensions` / `measures` / `format` mirror the manifest (Manifest v1 below) - keep
  them identical, since the cron rebuilds this island from `manifest + fresh rows`.

### 4c. Inline the runtime

The runtime is the canonical `web/dashboard-runtime/runtime.js` (it implements
contracts v1 and v2; the island's `version` picks the render path). There
is **no server-side baking** - `publish_dashboard` stores the HTML byte-for-byte, so
you must produce fully inlined HTML. Replace the `<script src="runtime.js"></script>`
placeholder with `<script>` + the file's contents + `</script>`. It injects its own
CSS at boot, so nothing else needs inlining. The runtime is small (well under the
size cap), so the cube data has essentially the whole publish budget.

Get the bytes from `web/dashboard-runtime/runtime.js` in this repo - the one source
of truth, kept in lockstep with the binding contract. There is no runtime-supplying
tool; the publish path stores whatever HTML you send. The committed dogfood (see the
worked example) is a full inlined reference you can copy the assembly from.

**The canonical runtime is the zero-effort default, not a requirement.** Instead of
inlining `runtime.js` you may hand-roll a custom vanilla-JS renderer that reads the
`#dashies-data` island's `cube` directly - reach for one when you need UI the
runtime's `data-dash` bindings do not cover (multi-select filters, date-range
pickers, tabs, bespoke charts). A custom renderer stays refreshable because the
refresh cron rewrites ONLY the `#dashies-data` island; your markup and scripts are
left untouched. Keep the island shape and the manifest contract intact (same
`dimensions` / `measures` / `cube` keys), and stay within the sandbox CSP (4d). See
`web/dashboard-runtime/CONTRACT.md` for the island shape and binding contract.

Freshness-stamp caveat: render the island's `updated_at` from the full ISO timestamp
(`new Date(updated_at)` / `Date.parse`), never a date-only slice, or the "refreshed N
ago" stamp anchors to midnight and reads stale; the simplest path is to keep the
`data-dash="updated-at"` binding for the stamp.

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

**Preview over `http://`, not `file://`.** To check a built template before
publishing, serve it from a local `http://` server rather than opening it as a
`file://` URL - some tooling blocks `file://` and relative-path behavior differs
from how the dashboard is actually served. And a `private` dashboard does not render
for an unauthenticated viewer at its published URL (the serve layer auth-gates it),
so verify a private one while signed in as its owner.

---

## Step 5 - Pick a schedule

Choose one cadence: **`manual`**, **`hourly`**, **`daily`**, **`weekly`**, or
**`monthly`**. Match it to how fast the underlying data actually moves and the grain
you chose - a dashboard bucketed by `month` gains nothing from hourly refreshes.
`manual` means it only refreshes when someone triggers it (no cron). `daily` is a
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
app on the **Schedules** page, where the cron honors that wall-clock time in their
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

To verify after publishing, two read-only tools inspect a personal dashboard by its
slug: `get_source_config({ slug })` returns the stored manifest exactly as saved (so
you can confirm it stored correctly, or review it before republishing with an edit),
and `get_refresh_status({ slug })` returns whether it is refreshing, its schedule,
the next run time, and the recent run history (so you can confirm the cron is keeping
it fresh). Neither triggers a refresh or changes the schedule.

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
| `connection` | yes | Which data source to run `cube_sql` against, as a string. Either `"self"` (Dashies' own no-PII metrics view, the built-in default) or the `id` of a warehouse connection you own (from `list_connections`; requires a paid plan and is validated server-side). Only the connection reference lives here - never credentials. |
| `schedule` | yes | One of `manual` / `hourly` / `daily` / `weekly` / `monthly`. Sets the refresh cadence. |
| `cube_sql` | yes | The single read-only `SELECT` from Step 3. Its `GROUP BY` columns must equal `dimensions[].key`; its output columns must equal `dimensions[].key` + `measures[].key`. |
| `dimensions` | yes | The grain. Same shape as the data island's dimension specs (`key`, optional `label`, `type` of `category` (default) or `date`). |
| `measures` | yes | The stored aggregate columns. Same shape as the island's measure specs (`key`, `label`, `agg`, `format`) plus `additive`. |
| `measures[].agg` | yes | Roll-up the runtime applies: `sum` / `count` / `min` / `max`. |
| `measures[].additive` | yes | Must be `true`. Records that this measure re-slices correctly. Non-additive metrics are not stored as measures - they appear in `derived` (ratios) or as a dimension (distinct counts). The flag forces the classification from Step 2d, and the declaration is no longer trusted alone: the publish validator also sniffs `cube_sql` and rejects v1 SQL that computes a non-additive aggregate (invariant 4). |
| `format` | no | Global format defaults keyed by format name (e.g. `currency`), copied verbatim into the data island. |
| `derived` | no | Documents non-additive metrics rendered at display time as a ratio of two additive measures: `{ label, kind: "ratio", num, den, format }`. Auditing + validation metadata; the runtime renders these from the `data-num` / `data-den` bindings in your HTML, not from this field. |

**Invariants the manifest must satisfy:**

1. `dimensions[].key` == the cube SQL's `GROUP BY` columns == the cube grain.
2. Every `measures[].key` is an aggregate column in `cube_sql`, additive, rolled up
   by its `agg`.
3. `dimensions[].key` + `measures[].key` == every column the SELECT returns ==
   every key on each cube row.
4. No non-additive measure is stored, and `cube_sql` computes none - **enforced**:
   publish rejects a v1 manifest whose SQL contains `count(DISTINCT ...)`,
   `avg(...)`, `median(...)`, `percentile_cont(...)` / `percentile_disc(...)`,
   `stddev(...)`, `variance(...)`, or `mode()`, naming each construct and pointing
   at manifest v2. Ratios live in `derived` (and in `data-num` / `data-den`
   bindings); low-cardinality distinct counts become dimensions; anything else
   non-additive is a v2 dashboard, declared as a v2 measure over rows (Step 2d
   lists the few aggregates v2 cannot declare yet).
5. `dimensions`, `measures`, and `format` are byte-identical to what you put in the
   data island, so the cron can rebuild the island from `manifest + fresh rows`.

---

## Manifest v2 - row-level + DuckDB (when additivity cannot hold)

v1's cube + re-sum model is correct ONLY for additive measures (Step 2d). When the
dashboard's point is a metric additivity cannot express - **distinct counts,
medians, percentiles, true averages** - author it as **manifest v2**: the island
ships **row-level data** and the page runs **real SQL in the browser**
(DuckDB-WASM), recomputing every metric from the rows on each filter change.
Correct under any slice, by construction.

**Choosing:** the split is enforced, not stylistic. The moment any needed metric
is non-additive, v2 is the choice - a v1 publish whose `cube_sql` computes
`count(DISTINCT ...)`, `avg`, `median`, `percentile_cont` / `percentile_disc`,
`stddev`, `variance`, or `mode()` is rejected with an error naming the constructs
and pointing here (`validate_cube_sql` warns about the same SQL first). In v2
those metrics become **measures over row-level rows** (`count_distinct`, `avg`,
`median`, `percentile_cont`), never aggregates written into `cube_sql`; the few
with no v2 measure yet (`percentile_disc`, the `stddev` / `variance` family,
`mode()`) stay out of the dashboard (Step 2d). Keep v1
for purely-additive cubes (sums, row counts, min/max, ratios of those via
`derived`): it is the lighter artifact - smaller page, no engine download, and
aggregated bytes are the privacy-safest shape. Two v2 costs to price in: the
first view fetches the DuckDB-WASM engine (~35 MB from a pinned cross-origin
host, then cached immutably) - fine on broadband, heavy on mobile; and the island
carries raw rows, so the Step 2c privacy rule tightens - every column of every
row you ship is world-readable. Select only the columns you need and
pre-aggregate anything sensitive.

### The v2 manifest (source_config)

Same envelope as v1 (`connection`, `schedule`, `cube_sql`, `dimensions`,
`measures`, `format`, `derived`), with these changes:

```json
{
  "manifest_version": 2,
  "connection": "<warehouse connection id, or self>",
  "schedule": "daily",
  "cube_sql": "select order_date, region, plan, amount, customer_id from orders where order_date >= now() - interval '60 days'",
  "schema": [
    { "name": "order_date",  "type": "DATE" },
    { "name": "region",      "type": "VARCHAR" },
    { "name": "plan",        "type": "VARCHAR" },
    { "name": "amount",      "type": "DOUBLE" },
    { "name": "customer_id", "type": "BIGINT" }
  ],
  "dimensions": [
    { "key": "region", "label": "Region", "type": "category" },
    { "key": "plan",   "label": "Plan",   "type": "category" }
  ],
  "measures": [
    { "key": "revenue",   "label": "Revenue",   "agg": "sum",             "column": "amount",      "format": "currency" },
    { "key": "orders",    "label": "Orders",    "agg": "count",           "format": "integer" },
    { "key": "customers", "label": "Customers", "agg": "count_distinct",  "column": "customer_id", "format": "integer" },
    { "key": "aov",       "label": "AOV",       "agg": "avg",             "column": "amount",      "format": "currency" },
    { "key": "p95",       "label": "p95 order", "agg": "percentile_cont", "column": "amount",      "percentile": 0.95, "format": "currency" }
  ],
  "format": { "currency": { "code": "USD", "decimals": 0 } },
  "data": { "mode": "inline" }
}
```

| Field | v2 rule |
|---|---|
| `schema` | **Required.** `[{ name, type }]`, one entry per column `cube_sql` returns, with **exact DuckDB types** (`DATE`, `VARCHAR`, `DOUBLE`, `BIGINT`, ...). The runtime registers the rows as table `t` with these types. |
| `data` | **Required.** `{ "mode": "inline" }` for `self` and for warehouse cubes that fit the island, OR `{ "mode": "parquet" }` (warehouse only, no `rows`) for a cube too large to inline - see "Parquet mode" below. The manifest does NOT carry rows (the island does); omitting `data` fails validation with "source_config.data must be an object". |
| `cube_sql` | Selects **row-level data** (or a fine-grained pre-aggregation), not a GROUP BY cube. Every Step 3 rule still applies: single read-only SELECT, relative time windows, allowlisted objects, the caps. |
| `measures[].agg` | Any of `sum` / `count` / `min` / `max` / `avg` / `count_distinct` / `median` / `percentile_cont`. |
| `measures[].column` | Optional. The raw column the aggregate reads when it differs from the measure key (`aov` reads `amount`). Defaults to the key; `count` counts rows and needs no column. |
| `measures[].percentile` | Optional, 0..1, for `percentile_cont` (default 0.5 = the median). |
| `measures[].additive` | Dropped - v2 has no additivity requirement (the flag is ignored if present). |
| `dimensions` | Unchanged in shape, but each key must be a **real column** of the rows (in `schema`) - viewers filter and group by these. |

### The v2 island

Same single `<script type="application/json" id="dashies-data">` element; the spec
carries `"version": 2`, the `schema`, and `data.rows` in place of v1's `cube`:

```json
{
  "version": 2,
  "updated_at": "2026-07-03T09:15:00Z",
  "schema": [ { "name": "order_date", "type": "DATE" }, { "name": "region", "type": "VARCHAR" }, { "name": "plan", "type": "VARCHAR" }, { "name": "amount", "type": "DOUBLE" }, { "name": "customer_id", "type": "BIGINT" } ],
  "dimensions": [ { "key": "region", "label": "Region", "type": "category" }, { "key": "plan", "label": "Plan", "type": "category" } ],
  "measures": [ { "key": "revenue", "label": "Revenue", "agg": "sum", "column": "amount", "format": "currency" }, { "key": "customers", "label": "Customers", "agg": "count_distinct", "column": "customer_id", "format": "integer" } ],
  "format": { "currency": { "code": "USD", "decimals": 0 } },
  "data": { "mode": "inline", "rows": [
    { "order_date": "2026-06-01", "region": "eu", "plan": "pro", "amount": 74.10, "customer_id": 8123 }
  ] }
}
```

Your `data-dash` markup is **unchanged** - same attributes, same bindings; only the
number source changes (SQL over `t` instead of a JS re-sum). Keep `schema` /
`dimensions` / `measures` / `format` byte-identical between the manifest and the
island, exactly as in v1, so the cron can rebuild the island. The runtime branches
on the island's `version`, and the cron writes back whichever version the dashboard
already is - a v1 dashboard never silently becomes v2.

### Columnar inline islands (denser rows, same data)

An inline v2 island MAY carry its rows as a **columnar object-of-arrays** in
`data.cols` instead of the array-of-objects `data.rows` - the same rows, the same
table `t`, the same results, just **~2-3x fewer bytes** because a column layout does
not repeat every key on every row:

```json
"data": { "mode": "inline", "cols": {
  "order_date":  ["2026-06-01", "2026-06-01", "2026-06-02"],
  "region":      ["eu", "us", "eu"],
  "amount":      [74.10, 12.00, 9.99],
  "customer_id": [8123, 4550, 8123]
} }
```

Rules (validated at publish): `cols` is valid **only** when `data.mode` is
`"inline"` (a parquet island carries a pointer, never `rows` or `cols`); an island
carries **either `rows` or `cols`, never both**; every column name must be declared
in `schema`; and all column arrays must be the **same length** (they zip back into
position-aligned rows). Reach for `cols` when an inline cube is large enough that the
row form crowds the 8 MB island cap - it buys headroom without moving to parquet, and
`self` and warehouse inline cubes can both use it. The encoding is chosen **once, at
publish**, exactly like the manifest version and mode: the refresh cron **preserves**
whichever encoding the island already uses (a `cols` island is rewritten columnar; a
`rows` island stays row form), because the runtime is baked into the HTML at publish
and a pre-columnar frozen runtime can only read `rows`.

### Publish with a placeholder island (the intended v2 flow)

`validate_cube_sql` echoes at most **200 rows** back (alongside the exact
`row_count`, with `rows_truncated: true`), so for any real row-level cube you
cannot bake the full result into the island at publish time. That is by design.
The flow:

1. **Validate** the cube SQL; check `row_count` fits the caps below and the
   columns match `schema` exactly.
2. **Publish with a tiny placeholder `data.rows`** - the echoed sample rows work
   (or a handful of hand-shaped rows covering each dimension value). They must be
   real-shaped rows so the page renders and every binding is exercised.
3. **The first refresh fills the island** with the full row set. Pick a real
   cadence (`hourly` / `daily` / ...) so that happens on its own; with `manual`
   the island stays placeholder until someone triggers a refresh in the app.
4. **Until that first refresh succeeds, the live page renders the placeholder
   data.** Say so when you hand over the URL, and verify with
   `get_refresh_status({ slug })` after the first run instead of assuming - if
   the cube keeps timing out, the page shows placeholder data indefinitely (see
   the warehouse scale rules in Step 3).

### Caps (v2 lives against these)

- A refresh writes at most **100,000 rows / 8 MB** into the island - self and
  warehouse connections alike.
- The **publish body cap stays ~5 MB** of total HTML. The asymmetry is deliberate:
  a refreshed island may legally grow beyond what publish would accept, so a
  dashboard whose full row set weighs 5-8 MB can ONLY exist via the placeholder
  flow, and its refreshed body could not be republished byte-for-byte.
  Republishing the markup with a placeholder island is fine - the next refresh
  refills it.
- Inline rows are JSON objects that repeat every key per row (roughly 2-3x the
  bytes of a columnar layout), so budget by bytes, not just rows: 100k narrow rows
  fit in 8 MB; 100k wide rows do not.
- The 8 s SQL budget binds the authoring path (`validate_cube_sql`); a scheduled
  refresh gets slightly more headroom - do not design a cube that needs it (see
  the warehouse scale rules in Step 3).
- **Beyond 100,000 rows / 8 MB (warehouse only):** switch `data.mode` to
  `"parquet"` (below). The rows then live in a separate file instead of the
  island, up to a much larger ceiling. `self` cannot use parquet.

### Parquet mode - warehouse cubes too large to inline

When a warehouse v2 cube is larger than the 8 MB inline island can hold, ship the
rows as a separate **parquet file** instead of inlining them. The island carries a
POINTER, not rows; everything else about v2 (the `schema`, the `data-dash`
bindings, the DuckDB SQL) is unchanged.

- **Author it:** `source_config.data = { "mode": "parquet" }` with **no `rows`**,
  on a **warehouse** connection (`self` must stay `"inline"` - its no-PII view is
  small by construction). Keep `schema` / `dimensions` / `measures` exactly as for
  inline v2.
- **It publishes PENDING.** There is no data yet, so the island's `data.url` is
  `null` and the live page shows a quiet "Data is being prepared" state (not an
  error). The **first refresh** runs the extract, writes the parquet file to
  Dashies storage, and fills the pointer (`url`, `row_count`, `byte_size`,
  `content_hash`). Pick a real cadence, or trigger a manual "Refresh now" right
  after publishing so the data appears; verify with `get_refresh_status({ slug })`.
- **Size ceiling (~128 MiB), desktop-first.** The browser query engine downloads
  the whole parquet and decodes it in memory (it does not fetch only part of the
  file today), so a very large object can exceed a low-memory device's budget. An
  extract over ~128 MiB is refused at refresh time; under it, a large file still
  shows a "this data (~X MB) may be too large to load on this device" state with a
  "Load anyway" control on phones/tablets. **Check the connection's approximate
  table size with `introspect_schema` before choosing parquet**, and aggregate to
  the grain you actually chart so the extract stays as small as the dashboard needs.
- **Private dashboards** are served through a short-lived signed link that the
  page requests automatically; nothing in authoring changes, and a stale link
  simply shows a "data link expired, reload the page" state.

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

> **PR3's authoring tools and PR4's refresh cron are merged and live; the dogfood's
> first publish is a coordinated follow-up by the team lead.** The artifact is
> committed and verified to render standalone, and the remaining gate is only that
> the live publish is sequenced by the lead, not a missing deploy. When publishing,
> re-inline the current runtime, `validate_cube_sql` the manifest's `cube_sql`, paste
> the fresh rows, and publish - then confirm it refreshes daily, slices client-side
> under `sandbox allow-scripts`, and uses no `localStorage`.

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
  / `variance`, `mode()`) stay out (Step 2d).
- **The cube is public, aggregated bytes.** No PII, no raw rows, no small-cell
  re-identification. (A v2 island ships row-level bytes on purpose - which makes
  this rule stricter there, not looser: every shipped column is world-readable.)
- **The SQL runs forever.** One read-only SELECT, relative time windows, low grain.
- **At warehouse scale, pushdown decides - or use parquet.** Plain GROUP BY on real
  columns is fast at 1M rows; `date_trunc` buckets and naive joins stream and time
  out - pre-bucket the date in the warehouse, keep windows tight, and use the
  two-step join rewrite for the inline path, or move heavy analytics to a v2 +
  parquet dashboard, which extracts rows and aggregates them in the browser with no
  remote GROUP BY (Step 3's warehouse scale rules).
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

For the exhaustive binding reference read `web/dashboard-runtime/CONTRACT.md`. The
tool calls in Steps 1, 3, and 6 (`introspect_schema`, `validate_cube_sql`, and
`publish_dashboard` with `source_config`) match the shipped MCP tools.
