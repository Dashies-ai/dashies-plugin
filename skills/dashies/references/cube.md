# Reference: design the cube and write its SQL

Part of the `dashies` skill (Steps 1-3). The **cube** is the small, pre-aggregated
table your dashboard is built from - designing it well is what makes a refreshable
dashboard correct. Then you write one SQL query that produces it, and validate that
query. Turning the validated cube into a working dashboard - the spec's datasets and
tiles - is Step 4, in `spec.md`: the compiler generates the HTML, the data island, and
the refresh manifest from the spec, so you never hand-write them. (The legacy
hand-authored HTML + manifest path still exists as a fallback for what the spec
cannot express - see `dashboard.md`.)

## Introspect first

> **You should already have run the hierarchy in SKILL.md, "Before Step 0".** If the
> user has a semantic layer, the metric DEFINITIONS come from there and not from
> anything you infer off a column list here. If they have warehouse or dbt tooling,
> the exploring below belongs in THAT tooling - schema, cardinalities, domain values,
> lineage - and you come back to Dashies with a finished statement. If neither is
> reachable, you ASK before exploring through Dashies. Everything in this file assumes
> that question has already been answered.

Call `introspect_schema({ connection })` (defaults to `self`; pass a warehouse
connection `id` from `list_connections` for your own data) to see the tables,
columns, and types. It reports column names and types - and, for a warehouse
connection, an approximate row count per table - but not per-column cardinality or
the actual values a column holds, so judge those from what each column means and
confirm the real cube later with `validate_cube_sql`. Look for:

- **Candidate dimensions** - low-cardinality descriptive columns to filter or group
  by (region, plan, status, a date).
- **Candidate measures** - numeric columns worth aggregating, and row-grain facts
  you can `count(*)` or `sum(...)`.
- **Sensitive columns** - anything personal or secret, to aggregate away (the cube
  ships in public bytes; see below).

**On a real warehouse this is the largest result in the whole authoring flow, so
narrow it.** Pass `tables` to filter: `introspect_schema({ connection, tables:
["sales"] })`. One filter term matches any part of the fully-qualified name, so the
same argument serves as a database, schema, or table filter (`["analytics."]` scopes
to a schema, `["orders", "customers"]` picks two tables). Use it whenever you already
know roughly what you are building against; take the unfiltered listing only when you
genuinely need to discover what is there, and on a wide warehouse consider one broad
call to see the shape followed by filtered calls for the columns you actually need.

## Design the cube (the load-bearing step)

The cube is one row per combination of the dimensions, with the measures already
aggregated to that grain. The runtime never fetches more data - every KPI, chart,
table, and filtered view is computed from these rows in the browser. So the cube's
design *is* the dashboard's capability.

**Grain: every field you want to filter or chart on must be a grouped dimension.**
The runtime slices by matching dimension values on the cube rows, so a field that
is not in the grain cannot be filtered, grouped, or charted - full stop. List every
slice the dashboard should support, make each one a dimension, then stop: each extra
dimension multiplies the row count.

**Size the shape here, before you write any SQL.** The publish size check projects from
your declarations, not from the data, so the query's real row count will not save a wide
cube - a dataset returning 5,000 rows is refused just the same if its declarations
project past the ceiling. The remedy - split the breadth across several small datasets
rather than one wide one - is a design decision, not an edit, so make it now: see "Size
the dataset before you write the spec" below for the arithmetic.

**Keep dimensions low-cardinality.** The cube is shipped inside the HTML, and every
filter renders a `<select>` of a dimension's distinct values, so a high-cardinality
dimension both bloats the page and produces an unusable thousand-item dropdown. Aim
for a few hundred to a few thousand cube rows, not tens of thousands.

- **Bucket dates** to the period the dashboard reports on (`day` / `week` / `month`),
  never a raw timestamp. Bucket in the dashboard's **business time zone, in the SQL** -
  a refresh runs with no session time zone, so a bare `date_trunc('month', ts)`
  buckets in UTC and shifts month/quarter boundaries (and an hour across DST).
  Declare that zone in the manifest's `timezone` field. A column that is already a
  `DATE` needs no conversion. The per-engine forms are in the dialect table below;
  in Postgres, mind the `AT TIME ZONE` operand trap:
  - a `timestamp with time zone` converts with the single form:
    `date_trunc('month', ts AT TIME ZONE 'America/Los_Angeles')::date`.
  - a naive `timestamp` storing UTC needs the double form (label UTC, then convert):
    `date_trunc('month', ts AT TIME ZONE 'UTC' AT TIME ZONE 'America/Los_Angeles')::date`.
    The single form on a naive timestamp silently mis-buckets, so check the column
    type first (`introspect_schema` reports it).

  Publish and `validate_cube_sql` now CHECK this, per dataset. The server cannot read the
  operand's type, so it flags what it can see, as a non-blocking warning: a single
  `AT TIME ZONE` is reported as ambiguous (right for `timestamptz`, wrong for a naive
  `timestamp`), and a cube that declares a `timezone` the SQL never names is reported as
  bucketing in some other zone. Use the double form (or `CONVERT_TIMEZONE` /
  `FROM_UTC_TIMESTAMP` / BigQuery's 3rd argument) and the warning goes away.
- **Top-N a high-cardinality category** - keep the top values by volume and fold the
  rest into an `"Other"` bucket in SQL, or drop it from the grain. Do not ship a
  5,000-row dimension.

**The cube is public - aggregate away anything sensitive.** Published dashboards are
world-readable and the cube is embedded verbatim in the HTML, so aggregate to a
grain coarse enough that no individual row, person, or secret is recoverable (watch
small-cell counts that could re-identify someone). In a v1 cube carry aggregates,
never raw or personal data. (A v2 dashboard ships row-level rows on purpose - there
the rule tightens per column: never select a column you would not publish.)

### Classify every measure: additive vs non-additive

This is the rule that makes or breaks correctness. When a filter changes, the v1
runtime re-aggregates by **summing** (or taking the min / max of) each measure across
the rows that remain. That is only correct for **additive** measures, so classify every
number before you write SQL.

**Additive - store these directly as measures** (they re-slice correctly under any
filter):

| What | Store as | `agg` |
|---|---|---|
| Sums of an amount (revenue, cost) | the summed column | `sum` |
| Counts of rows / events (orders, signups) | a `count(*)` column | `sum` |
| Smallest / largest in a cell | the value | `min` / `max` |

The `agg` column is the **re-aggregation** the runtime applies to the pre-aggregated cells
(and the exact value a hand-authored v1 island carries). When you author with a **spec**
(`spec.md`) you declare the measure's own aggregate instead, and the compiler maps it to
this re-aggregation: a count-of-rows is declared `agg: count`, and a `cube` rolls it up by
**summing** the per-cell `count(*)` values - so on a `count(*)` column `agg: count` and
`agg: sum` are equivalent and both total correctly. A cube count is always re-summed, never
"counting the cells" (that mistake is unwritable through the spec). On a hand-authored v1
island the value you write IS the re-aggregation, so a `count(*)` measure must be `sum`
there (see `dashboard.md`).

**A `sum` is additive only over a FLOW column, never a STOCK.** `sum` is safe only when the
underlying column is a **flow** - a quantity that accrues over the grain and is meaningful to
add up (revenue booked in the period, orders placed, a `count(*)` of events). It is **wrong**
for a **stock** - a point-in-time level read as-of each period (accounts open, headcount,
inventory on hand, an account balance, any gauge): summing a stock across periods
double-counts what merely persisted and yields a meaningless total. This is not a
hypothetical - a cohort lattice summing `ending_arr_usd` over 24 tenure months reported
$596M against a real $36M, a 16x overstatement that passed every gate.

**Declare it and the server checks it: put `stock: true` on the measure.** No static
analysis can infer this - `sum(ending_arr)` and `sum(new_arr)` are indistinguishable - so
the declaration is the only thing that makes the check possible, and an undeclared stock
stays exactly as invisible as it was. Once declared, a publish that sums it across the
grain returns a **warning** (never a block, since a latest-snapshot sum can be
intentional). Carry a stock as a `min` / `max` / period-end value, or model it on a
`lattice` / `rows` dataset that recomputes the as-of figure under filters. Unlike the
CTE/subquery-hidden non-additive measure and the fan-out JOIN double-count that **"Verify
the numbers"** below covers, this one the server WILL catch for you - but only if you
declare it.

`introspect_schema` on the `self` connection now surfaces this same classification directly:
each column comes back tagged with a `role` (`dimension` / `flow` / `stock`) plus a short
description, so you can see which columns are safe to `sum` instead of inferring it (warehouse
columns carry no role yet, so the check above still applies there).

**Non-additive - never store the finished number.** A stored average / rate /
distinct-count / median goes silently wrong the moment the user filters, because you
cannot recover it by summing partial results. This is **enforced at publish**: a v1
manifest is rejected when its `cube_sql` computes `count(DISTINCT ...)`, `avg`,
`median`, `percentile_cont` / `percentile_disc`, `stddev`, `variance`, or `mode()`,
naming each construct. Handle non-additive metrics one of these ways:

- **Averages, rates, ratios, percentages** -> store the **numerator and denominator
  as two additive measures** and let the runtime divide them at render time
  (`data-num` / `data-den`). `sum(num) / sum(den)` stays correct under every filter.
  Never store a pre-divided average - an average of averages is wrong. (A hand-built
  `sum(a)/nullif(count(*),0)` passes the publish check but is still wrong; keep the
  division out of the SQL and let the ratio binding do it.)
- **Distinct counts** are non-additive. If the thing you are counting is itself
  low-cardinality, carry it as a **dimension** so the runtime recovers the count by
  grouping. Otherwise it is a v3 or v2 `count_distinct` measure.
- **Medians, percentiles, true averages under filters** cannot be reconstructed from
  sums at all - they mean **v3** (precomputed exactly per filter state) or **v2**
  (recomputed from row-level rows), never a stored v1 measure. On a **warehouse**
  connection, read **"Exact medians and percentiles"** below before you write one: the
  percentile syntax is per-engine, and on BigQuery the obvious form is silently
  approximate.

**When any needed metric is non-additive, leave v1 - and prefer v3.** The additivity
rules here are what v1's re-summing runtime demands. The richer v4 dataset modes lift
them, and the dimensions and filters decide which:

- **`lattice` (v3, the grain compiler) is the default** when every dimension you
  filter, chart, or tabulate on is **low-cardinality** and every filter is
  **single-select**. It precomputes the exact aggregate for every single-select filter
  state with `GROUP BY CUBE`, so distinct counts, medians, percentiles, `stddev` /
  `variance` / `mode()` - any aggregate - stay exact, the artifact stays MB-scale, and
  no engine loads. Write it as in **"Write a v3 grain-compiler cube"** below.
- **`hybrid` extends the lattice** when the dashboard also needs **multi-value** filters
  (multi-select or a range) on a **non-composable** measure (distinct count, true average,
  median, percentile, `stddev` / `variance` / `mode`). A lattice precomputes only single-select
  states and cannot compose those measures across a multi-value selection; a hybrid
  ships an inline row-level slice (a `rows_sql`) alongside the lattice, so the runtime
  recomputes exactly that case with DuckDB while single-select and composable measures
  (`sum` / `count` / `min` / `max` / ratios) still resolve from the lattice with no
  engine. See **"The hybrid dataset"** in `dashboard.md`.
- **`rows` (v2, row-level + DuckDB)** is the fallback for **genuine row-level needs** - a
  dimension you cannot bound to low cardinality, or a need for row-level detail. It
  ships raw rows and recomputes metrics with real SQL in the browser (see
  `dashboard.md`).

**A windowed `rows_sql` must end in a top-level `ORDER BY` with a unique tiebreak.** When a
`hybrid` or `rows` dataset caps its inline row slice with `rows_window: N` (the aggregates stay
exact over full history, only the row-level detail and any drill are windowed), the window keeps
the FIRST N rows the query returns. So the `rows_sql` MUST end in an explicit order, and it
should carry a unique tiebreak: `order by <column> desc, <unique key> desc`. Order by TIME
descending - `order by created_at desc, id desc` - when you want the window to mean "the most
recent N"; order by anything else when you want a top-N by that measure. Without an
explicit order the window is whatever order the warehouse happened to return - untruthful,
and unstable run-to-run (the same window shows different rows across refreshes); the unique
tiebreak makes ties deterministic so the slice is reproducible. The full (non-windowed)
aggregate `sql` needs no such ORDER BY - only the windowed row slice does.

**This is SERVER-ENFORCED**: a dataset declaring `rows_window` whose windowed statement has no
top-level ORDER BY is REJECTED at publish, on both the spec path and the raw-manifest path. The
ordering must be the RESULT order - an ORDER BY inside a subquery, a CTE body, an `over (...)`
window, or a `within group (...)` clause does not order the result and does not satisfy the
gate. Order by whatever the window should mean: `order by created_at desc` for "the most recent
N", `order by revenue desc` for "the top N by revenue".

`validate_cube_sql` warns "requires manifest v2" the moment a plain `GROUP BY`
computes a non-additive aggregate - but once you write it as a v3 `GROUP BY CUBE`
(below) it recognizes the shape and returns a v3 note instead, so the version
decision arrives while you author.

## Write and validate the SQL

One query produces the cube. It runs unattended on every refresh, so:

- **A single read-only `SELECT`** - no DML, no DDL, no multiple statements.
- **`GROUP BY` exactly your dimension keys**, and `SELECT` those columns plus one
  aggregate per measure, each `AS` its manifest key. Output columns must equal
  `dimensions[].key` + `measures[].key`.
- **Relative time windows, never hardcoded dates** - `where created_at >= now() -
  interval '12 months'`, not a literal date, or the window silently freezes as it
  reruns for months.
- **Keep it small** (the grain rules above) - well under the 100,000-row / 8 MB
  refresh cap. Size the SHAPE before you write the query - see "Size the dataset
  before you write the spec" below.
- **End in an explicit `ORDER BY`.** Most tiles draw a dimension's members in the order
  your rows arrive, so without one the axis order, the pie's slice order, the filter
  menu's order and (for a matrix or heatmap) *which* members survive `limit` are all
  whatever the engine happened to produce, and can move between refreshes with nothing in
  the spec changing, and **nothing warns you** - there is no publish error for this, so a
  wrong order looks deliberate. Two guesses that would let you skip it are both wrong:
  a DATE dimension is not always sorted for you (some tiles treat it exactly like a
  category, a month `filter` menu among them), and changing dataset MODE does not excuse
  you either (on a `lattice`/`hybrid` only the filter menu moves off the SQL order, onto
  the declared `domains` array). Which tiles those are is the per-tile table under
  "Member order on an axis" in `spec.md`, and that table is the only place it is written
  down - deliberately, because a second copy here is a second thing to keep true.
  The rule that needs no table: **write the `ORDER BY` in every mode**, and on a
  `lattice`/`hybrid` also list `domains` in the order you want the menu.

```sql
-- shape only; column names come from your introspection
select
  date_trunc('month', created_at at time zone 'America/Los_Angeles')::date as month,
  region,
  plan,
  sum(amount)            as revenue,
  count(*)               as orders,
  count(*) filter (where is_signup) as signups
from orders
where created_at >= now() - interval '12 months'
group by 1, 2, 3
```

Validate before publishing with `validate_cube_sql({ sql, connection })`. It runs
the query under the same read-only limits a refresh enforces and returns the column
list, `row_count`, and rows. Confirm the columns match your dimension + measure keys
**exactly**, the row count is sane (low hundreds to low thousands), and the values
look right - then carry this SQL into the dataset's `sql` field in the spec
(`spec.md`, Step 4). The compiler re-runs it at publish time to seed the island
itself; you never hand-seed or hand-edit the island with the rows `validate_cube_sql`
returned.

When you are authoring a **v4 dataset**, pass that dataset's `mode` too -
`validate_cube_sql({ sql, connection, mode })` - so the advisory matches the mode you
chose: `mode: "cube"` warns on non-additive aggregates, `mode: "lattice"` checks the
`GROUP BY CUBE` shape (see "Write a v3 grain-compiler cube" below), `mode: "hybrid"`
checks that same `GROUP BY CUBE` shape for the dataset's lattice `sql` (validate its
separate `rows_sql` with `mode: "rows"`), and `mode: "rows"` blesses any aggregate
(DuckDB recomputes it from the rows). Omitting `mode` keeps the version-agnostic advisory
for a single-manifest v1/v2/v3 cube.

If the SQL sums a **stock** column (a level, not a flow - see the flow-vs-stock rule
above), pass it as `stock_columns` too: `validate_cube_sql({ sql, connection,
stock_columns: ["ending_arr_usd"] })`. Name the raw **column as it appears inside the
`sum()`**, not the output alias. You get the sum-over-stock advisory here, at the earliest
point in authoring, instead of discovering it at publish. This is the validate-surface
twin of the spec measure's `stock: true`; declare it in **both** places, because
`stock_columns` checks this one call while `stock: true` is stored in the manifest and
therefore re-checked on every future republish.

**Confirm categorical values before filtering on them.** Introspection does not
return the values a column holds, so a `where col = 'X'` with a wrong literal does
not error - it silently matches nothing and the measure reads zero. Read the real
values off a `select col, count(*) as n from t group by 1 order by 2 desc limit 50`
first - **in the user's own warehouse tooling if they have any** (SKILL.md rule 3);
only run it through `validate_cube_sql` when Dashies is the agreed path, and bound
it, per the next rule.

**The probe above gets a note too, and a quiet response is still not approval.**
`validate_cube_sql` flags both exploratory shapes: a statement with no `GROUP BY` (a bare
`count(*)`, a `select distinct`, a plain SELECT), and a **grouped count probe** exactly
like the one above - a column or two, only counting aggregates, and a small `LIMIT`. It
runs the SQL and returns the rows either way; the note only says where the question
belonged. It remains a heuristic over SQL text, so a probe it does not match is not a
probe it approves: silence means the shape did not match, never that the call was the
right place to ask. The judgement stays yours.

**Bound every probe, and turn the row echo OFF when you do not need it.** The rows
`validate_cube_sql` echoes back are by far the largest part of its result, and the
echo is capped at 200 rows OR about 8 KB of serialized JSON, **whichever binds
first**. So a wide probe returns FEWER rows than a narrow one for the same context
cost, and neither tells you anything the `row_count` field did not. Two habits:

- **Put a `LIMIT` (or `TOP`, on SQL Server) on an exploratory probe.** Anything you
  are running to *look* at - distinct values of a column, a sample of a table, a
  ranking - should be bounded at the source. A cardinality check does not need every
  row: `select count(distinct region) as n from t` answers it in one.
- **Pass `echo_rows: 0` whenever you only need the column shape, the exact
  `row_count` and the advisories.** You still get every warning and the size
  recommendation; you just do not get the sample. This is the DEFAULT for validating
  a **spec dataset**, because the server re-runs this same SQL at publish to seed the
  island - the rows are dead weight in your context, and you would never paste them
  anywhere. Use the sample only when you genuinely need to eyeball values: a first
  look at an unfamiliar table, a suspicious measure, a categorical spot-check.
  `echo_rows` can only make the result smaller (it is capped at the server row limit,
  and the byte budget still applies on top), so it is never a way to get MORE back.

### Verify the numbers - `validate_cube_sql` proves it RUNS, not that it is CORRECT

`validate_cube_sql` executes your SQL and its mode-aware advisory catches the *common*
non-additive forms by reading the SQL text - but it cannot see a non-additive measure **hidden in
a CTE or subquery** (a ratio or `count(distinct ...)` computed inside a derived table and then
selected as a plain column reads as additive), nor a **fan-out JOIN that double-counts** (a join
to a one-to-many table inflates every summed measure). Both publish clean and refresh to a
plausible WRONG number - the worst failure a dashboard can have. You wrote the SQL, so you have
the dialect context to catch them: **verify the numbers against an independent query before
publishing.**

- **Additivity, per additive-declared measure.** Sum the measure across the cube's cells and
  compare that to an **independent direct aggregate** computed a
  different way - `select sum(<measure_expr>) from <base_table>` over the **single un-joined base
  source** (the base table's own `sum` / `count`, NOT the cube's joined `FROM` - a join there
  reproduces the very double-count you are checking for), ungrouped or over one filter slice, and
  run that check through `validate_cube_sql` too. Neither leg needs the row echo: get the cube's
  total by wrapping it - `select sum(<measure>) as total from (<your cube sql>) c` - so both sides
  come back as one row and you can run the whole cross-check with `echo_rows: 0`. Summing the
  echoed cells by hand works too, but it makes you carry every cell to compute one number.
  If the two DIFFER, the measure is **not additive**
  (a hidden ratio / distinct / average): move it to a `num` / `den` ratio, or to a `lattice` /
  `hybrid` dataset that recomputes it exactly. Agreement across a couple of slices is strong
  evidence the re-summing a `cube` does is sound.
- **Fan-out.** The same cross-check catches a double-count: if an additive measure's cube total is
  a multiple of (or otherwise off from) the base table's own `sum` / `count`, a join is fanning
  rows out. Pre-aggregate the fan-out side to the grain first (or dedupe) so each base row counts
  once.

A wrong number caught here never ships; one that is not poisons trust in every number the
dashboard shows.

### Write a v3 grain-compiler cube (`GROUP BY CUBE`)

When the metrics are non-additive but every dimension is low-cardinality, write a
**v3** cube instead of a plain `GROUP BY`. `GROUP BY CUBE(dim1, ..., dimN)` computes
the full powerset of grouping sets in one query - one result row per single-select
filter state (each dimension either fixed to a value or rolled up) - so the browser
never re-aggregates: it looks up the cell matching the active filters. That is what
keeps distinct counts, medians, and percentiles exact under any filter.

**1. Declare your dimensions.** List every field the dashboard filters, charts, or
tabulates on - those are your CUBE dimensions. Keep each one low-cardinality and
bounded (bucket dates, top-N a big category), because the lattice has about
`prod(cardinality_i + 1)` cells and it ships inline.

**2. Write the exact shape.** Select the plain dimension columns, one
`GROUPING(<dim>) AS __g_<dim>` tag per dimension, and one aggregate per measure, then
`GROUP BY CUBE(<the plain dimension columns>)`. Bucket or derive any dimension in an
inner query so `CUBE()` sees plain columns:

```sql
select
  month, region, plan,
  grouping(month)  as __g_month,
  grouping(region) as __g_region,
  grouping(plan)   as __g_plan,
  count(*)                                             as orders,
  count(distinct customer_id)                          as customers,
  percentile_cont(0.5) within group (order by amount)  as median_order
from (
  select
    date_trunc('month', created_at at time zone 'America/Los_Angeles')::date as month,
    region, plan, customer_id, amount
  from orders
  where created_at >= now() - interval '12 months'
) src
group by cube(month, region, plan)
```

**That example is PostgreSQL, and its median is the one line in it that does not
travel.** `GROUP BY CUBE` and single-arg `GROUPING` ARE portable across every engine;
the aggregates you put inside are not. `percentile_cont(...) WITHIN GROUP (ORDER BY
...)` is PostgreSQL syntax, and **BigQuery rejects it outright** with `percentile_cont
aggregate function is not supported.` Before you put a median or a percentile in a
lattice on any non-PostgreSQL engine, read **"Exact medians and percentiles"** below:
the obvious BigQuery substitute is silently approximate, and nothing in the toolchain
warns you.

**3. Obey the constraints (a v3 publish rejects otherwise; `validate_cube_sql`
checks them too):**

- **CUBE arguments are the plain dimension-key columns.** Bucket or derive a
  dimension in an **inner query** (as `month` is above) so `CUBE()` operates over
  plain columns named exactly as the dimension keys. **No expression inside
  `cube()`** - `group by cube(date_trunc('month', ts), region)` is rejected.
- **Every dimension carries its tag.** Each declared dimension needs a single-arg
  `GROUPING(<dim>) AS __g_<dim>` in the SELECT (`0` = active in this cell, `1` =
  rolled up). The runtime keys on the flag, never on a NULL, so a rolled-up NULL is
  distinct from a real NULL value.
- **Portable constructs only.** Use single-arg `GROUPING(<dim>)` - it works on every
  engine. **No `GROUPING_ID(...)`** (not portable), **no `GROUPING SETS`**, **no
  quoted identifiers** in the CUBE list.
- **CUBE covers exactly the declared dimensions** - no declared dimension missing, no
  extra column.
- **Every dimension declares its BOUND** - `domains` (the value list) for a category
  dimension, `buckets` (the max bucket count) for a date dimension. The publish
  computes the lattice's size from those declarations and REJECTS a lattice over
  **50,000** cells, naming the count and the widest dimension; it also rejects a
  lattice that declares no bounds, because then the size cannot be computed at all.
  In the spec these are the dimension's own `domains` (its bounded value set) /
  `buckets` (an integer); hand-authored, they are the manifest's top-level `domains` /
  `buckets` maps, keyed by dimension (`dashboard.md`).

**4. Validate.** `validate_cube_sql({ sql, connection })` runs it and, because it
recognizes the `GROUP BY CUBE` + `__g_` shape, blesses the non-additive aggregates
with a v3 note (not the v2 warning). Confirm `row_count` is the lattice size you
expect (about `prod(cardinality_i + 1)`) and that it fits inline - v3 has no parquet
offload, so if the lattice is too big, drop or bound a dimension. `row_count` is also
the reality check on the bounds you are about to declare: it is what the source
actually returns today, while `domains`/`buckets` are what you promise it stays under,
and the publish budget believes the declaration. Then carry the SQL,
dimensions, and measures into a `lattice`-mode dataset in the spec (`spec.md`, Step 4) -
the compiler seeds the island from it, so you never hand-build it. (The same lattice
shape, as a hand-authored single-manifest v3, is documented in `dashboard.md` for
existing non-spec dashboards.)

Everything in "Write and validate the SQL" above still holds: a single read-only
`SELECT`, relative time windows, low grain. The dialect table below still governs
date bucketing and conditional counts - they now live in the inner query, and
`GROUP BY CUBE` / single-arg `GROUPING` are themselves portable across all engines.

### Dialects (warehouse connections)

The cube SQL dialect follows the connection's engine (`list_connections` reports
it). Everything above is engine-independent; only the syntax changes. Author against
`validate_cube_sql` for that connection, not from memory.

| Need | PostgreSQL | GoogleSQL (BigQuery) | Snowflake |
|---|---|---|---|
| Table reference | `from orders` | backtick `` `project.dataset.table` `` | database-qualified `from DB.SCHEMA.ORDERS` |
| Bucket a date (business zone) | `date_trunc('month', ts AT TIME ZONE 'America/Los_Angeles')::date` | `timestamp_trunc(ts, MONTH, 'America/Los_Angeles')` (zone is the 3rd arg) | `date_trunc('MONTH', convert_timezone('UTC','America/Los_Angeles', ts))` |
| Relative window | `now() - interval '12 months'` | `timestamp(date_sub(current_date('America/Los_Angeles'), interval 12 month))` | `dateadd('month', -12, current_timestamp())` |
| Conditional count | `count(*) filter (where c)` | `countif(c)` | `count_if(c)` |
| Exact median | `percentile_cont(0.5) within group (order by x)` | `array_agg(x ignore nulls order by x)[safe_offset(div(count(x), 2))]` - there is NO aggregate percentile; see "Exact medians and percentiles" | `percentile_cont(0.5) within group (order by x)` (not verified) |

**BigQuery gotchas.** Three, all of which cost real authoring time:

- **The obvious relative window does not run.** `timestamp_sub(current_timestamp(),
  interval 12 month)` fails with `TIMESTAMP_SUB does not support the MONTH date part
  when the argument is TIMESTAMP type` - `TIMESTAMP_SUB` accepts only MICROSECOND
  through DAY on a `TIMESTAMP`. Go through `DATE` as the table shows, or use
  `interval 365 day`.
- **A `TIMESTAMP` reads back as a raw epoch string.** `validate_cube_sql` returns it as
  seconds-since-epoch in scientific notation - `"1.721210317969462E9"` - not an ISO
  string, so you cannot eyeball a date range while authoring, and a raw timestamp is
  useless as a dimension label. Format it in SQL:
  `format_timestamp('%Y-%m', ts, 'America/Los_Angeles')` for a month bucket, or
  `date(ts, 'America/Los_Angeles')` for a date. (Databricks, by contrast, returns
  ISO-8601 UTC - see its note below.)
- **`introspect_schema` reports no row estimate.** See "Large warehouse tables" below
  for the count-it-yourself fallback.

**Alias letter-case, on every engine.** Engines disagree about what an *unquoted*
output alias comes back as: Snowflake folds it UPPER (`as orders` -> `ORDERS`),
Postgres and Redshift fold it lower, and BigQuery, Databricks and SQL Server preserve
it exactly as written. **A case-only difference between the alias and the declared key
is handled for you** - publish and refresh both canonicalize a result column back to
the declared key when the two match apart from letter case, and the runtime normalizes
island keys when it parses them. So `sum(amount) as revenue` against a measure declared
`revenue` is correct on all six engines; you do not need to quote the alias to defend
the case, and you should not keep a set of UPPERCASE manifest keys just to please
Snowflake.

What is NOT forgiven is **two output columns that differ only by case landing on one
declared key** (`revenue` and `REVENUE` in the same SELECT). That is refused loudly,
naming both, at publish and at refresh - alias exactly one of them to the declared key.
Quote an alias when the name itself needs it (a reserved word, a space, punctuation),
using the engine's quote character: `"..."` on Postgres / Snowflake / Redshift,
backticks on BigQuery / Databricks, `[...]` on SQL Server. One caveat if you are on
**Redshift**: what an alias comes back as depends on two cluster parameters, not on how
you write it. At the defaults, quoting preserves nothing (AWS folds *delimited*
identifiers to lowercase too), but `enable_case_sensitive_identifier = true` makes a
quoted identifier keep its case, and `describe_field_name_in_uppercase = on` returns
every column name UPPERCASE regardless of how it is stored. Neither is exotic - AWS
recommends the first for materialized-view autorefresh and row-level security. Rather
than guessing which way a given cluster is set, run
`validate_cube_sql({ sql: 'select 1 as MixedCase, 2 as "MixedQuoted"', connection })`
once and read the column names back; that answers both parameters in one call.

*(Historical: before PR #913 the refresh stored the engine's own casing verbatim, and a
Snowflake dashboard's first scheduled refresh could report success over a blank page.
That is fixed; the alias-quoting drill it used to require is no longer needed.)*

**Redshift** is a PostgreSQL dialect, so the PostgreSQL column applies almost
verbatim; use `to_char(ts, 'YYYY-MM-DD')` or `date_trunc('month', ts)::date` for a
text/date dimension.

**Databricks** takes **Databricks SQL** (Spark SQL) - a distinct dialect, not a
PostgreSQL one. Table references are backtick-quoted and three-level
`` `catalog`.`schema`.`table` `` (the built-in `samples` catalog -
`samples.nyctaxi.trips`, `samples.tpch.*` - is handy for a demo with no seed table).
Unlike Postgres/Redshift it does NOT fold an unquoted output alias - Databricks
PRESERVES the alias as written, so `sum(amount) as revenue` comes back `revenue`. Its
quote character is a **backtick**, needed only when the name itself is not a bare
identifier. Bucket a date with `date_trunc('MONTH', ts)` or
`date_format(ts, 'yyyy-MM')`; a relative window is `current_timestamp() - interval 12 months`;
a conditional count is `count_if(c)`. A `TIMESTAMP` value arrives in the data island as an
ISO-8601 UTC string (`2024-01-15T10:30:00.123Z`, `T`-separated with a trailing `Z`), so
bucket/format it in SQL rather than parsing the raw text; big integers keep full precision as
strings. The cube must be a single read-only `SELECT` (the JS read-only guard is the only
gate - Databricks itself runs DML happily). The warehouse cold-starts a few seconds on the
first query after an auto-stop, so a **2X-Small serverless warehouse with a short auto-stop**
keeps scheduled refresh cheap.

**Microsoft SQL Server** takes **T-SQL** (Transact-SQL) - not a PostgreSQL dialect, and it
is the one engine whose RESULT CEILING is different: its confined executor caps a cube at
**5,000 rows / 2,000,000 bytes**, where every other engine caps at 100,000 / 8,000,000.
That is 20x tighter and it applies to `cube`, `lattice`, `hybrid` and `rows` alike, so
design the grain against it from the start - an overrun is a hard `execute_ro: result
exceeds 5000 rows; aggregate further`, never a truncation. There is also **no Parquet
offload** on this engine (it has no extract module, and `data: { mode: parquet }` is
refused), so the only remedies are a coarser grain, a narrower window, or a
lower-cardinality dimension. `introspect_schema` prints the ceiling before you write any
SQL - that is the reliable place to read it - and `validate_cube_sql` repeats it in the
`Size:` line of a successful validate (not on a failure, and not on the `extreme` or
v3/v4-inline-only branches). Read it off `introspect_schema`.
Table references are `[bracket]`-quoted (`[dbo].[orders]`). SQL Server PRESERVES an
output alias as written - `sum(amount) as revenue` comes back `revenue`, measured on a
case-INSENSITIVE collation, because collation governs whether two names may coexist,
not whether one gets rewritten. Use brackets when the name itself needs them. A few
type traps the data-island reader forces:
- **Cast `GROUPING()` flags and any `tinyint` measure to a wider int.** A `GROUPING(x)`
  flag and a `tinyint` column are read as a 1-byte value that is NOT `int2`, and a
  `tinyint` above 127 fails the read outright - so write
  `cast(grouping(region) as smallint) as [__g_region]` and `cast(<tinyint measure> as int)`.
- **Time zones need the DOUBLE `AT TIME ZONE`, cast back to `datetime2`.**
  `datetimeoffset` is unsupported by the reader, and `AT TIME ZONE` RETURNS a
  `datetimeoffset`, so convert a UTC column and cast:
  `cast(ts at time zone 'UTC' at time zone 'Pacific Standard Time' as datetime2) as [ts_local]`.
  SQL Server uses **Windows** zone names (`Pacific Standard Time`), not IANA
  (`America/Los_Angeles`) - though a Linux-hosted server may accept IANA; check
  `select name from sys.time_zone_info` for what THIS server takes.
- **Precision limits.** `decimal`/`numeric`/`money` are read through an f64 hop (~15-16
  significant digits - cast money to bigint-cents if you need exactness), and
  `datetime`/`datetime2` truncate to **whole seconds** in the island - bucket/format in SQL,
  don't rely on sub-second precision.
Bucket a date with `cast(ts as date)` or `datefromparts(year(ts), month(ts), 1)`; a relative
window is `dateadd(month, -12, sysutcdatetime())`. The cube must be a single read-only
`SELECT`, but on SQL Server the JS guard is **defense-in-depth only** (T-SQL statement
terminators are optional) - the real gate is that the connection MUST use a **read-only
login** (the connect test refuses a login with any write/admin privilege), so the user
connects a `dash_ro`-style login, never an admin. Only your allowlisted schemas (plus the
`sys`/`INFORMATION_SCHEMA` catalogs) are readable.

### Exact medians and percentiles

A lattice cell promises the **exact** aggregate for that filter state. A median or a
percentile is the easiest place to break that promise without noticing, because the
substitute that looks right on every engine is not exact on all of them.

**`percentile_cont(...) WITHIN GROUP (ORDER BY ...)` is not portable.** It is what the
v3 example above uses and it is correct for PostgreSQL. **BigQuery rejects it** -
`percentile_cont aggregate function is not supported.` GoogleSQL's `PERCENTILE_CONT`
is an analytic (`OVER ()`) function only, so **there is no exact aggregate percentile
in GoogleSQL at all**.

**Never back a declared `median` / `percentile_cont` measure with `APPROX_QUANTILES`.**
It is the obvious BigQuery substitute and it is wrong twice over:

- It is **approximate**. A lattice cell is supposed to be the exact answer; this is not.
- Its answer **changes with the CUBE's dimension count**. Measured on a live 300k-row
  table: the identical `region = 'eu'` population returned **22518** from a
  two-dimension `GROUP BY CUBE` and **22164** from a three-dimension one, against a
  true median of **22785**. Two cells of one lattice can disagree about the same rows.

`validate_cube_sql` does not warn about this. It runs clean, it publishes clean, and
the dashboard ships a plausible wrong number that no later step re-derives.

**The exact GoogleSQL form** (verified cell for cell against an independent rank-based
median on a 300k-row table):

```sql
array_agg(x ignore nulls order by x)[safe_offset(div(count(x), 2))] as median_x
```

Three details in it are load-bearing, and the middle one is a trap the correct form
still leaves open:

- **`ignore nulls`** - `ARRAY_AGG` otherwise keeps NULLs and sorts them FIRST.
- **`count(x)`, never `count(*)`.** `count(*)` counts the NULL rows too, so it indexes
  past the midpoint of a NULL-free array. On a column with 8917 NULLs in 296104 rows
  that returned **21409** where the true median was **22767** - about 6 percent low,
  validating and publishing clean. Only an independent cross-check caught it. On a
  column with no NULLs the two forms agree exactly, which is precisely why this
  survives casual testing and reaches production.
- **`safe_offset`, not `offset`.** A cell whose values are all NULL yields an empty
  array, and bare `offset` THROWS. This query re-runs unattended forever, so it must
  not fail on a cell that the data happens to empty out later.

Per engine, and marked honestly:

| Engine | Exact median | Status |
|---|---|---|
| PostgreSQL | `percentile_cont(0.5) within group (order by x)` | The dialect the examples above are written in |
| BigQuery | `array_agg(x ignore nulls order by x)[safe_offset(div(count(x), 2))]` | **Verified** on a live connection |
| Redshift | `percentile_cont(0.5) within group (order by x)` | Not verified - confirm before relying on it |
| Snowflake | `percentile_cont(0.5) within group (order by x)` | Not verified - confirm before relying on it |
| Databricks | `percentile(x, 0.5)` | Not verified - confirm before relying on it |
| SQL Server | Unknown - no aggregate form confirmed | Not verified - confirm before relying on it |

**Whatever engine you are on, prove the median before you publish.** Run the cube
through `validate_cube_sql`, then compute the same median a second, independent way -
a rank-based `row_number()` query, or the engine's analytic `percentile_cont` over the
same rows - and compare the two numbers. This is the same cross-check **"Verify the
numbers"** above demands of every additive measure, and a non-additive measure needs it
MORE, not less: nothing downstream re-derives a median, so a wrong one is invisible
forever.

### Large warehouse tables

Against a big table, keep the cube cheap and let it validate fast:

- **Check the table's approximate size** with `introspect_schema` before you design -
  where it reports one. The estimate is not available on every engine: a **BigQuery**
  connection came back with no `row_estimate`, `size_band` or `recommended_mode` on any
  of 40+ tables, so there is simply nothing to read. When it is absent, measure it
  yourself with
  `validate_cube_sql({ sql: 'select count(*) as n from <table>', connection })` - a bare
  full-table aggregate pushes down to the remote and is fast even at millions of rows.
- **Keep the grain small and the time window tight.**
- **Group on real columns where you can.** If the warehouse can carry a
  pre-bucketed `day`/`week`/`month` column, group on it rather than truncating a
  raw timestamp in the cube.
- **For a star schema, aggregate the fact table first, then join the small
  dimension table** and re-aggregate (sums of sums stay exact).
- **A row-level dataset too large to inline declares `data: { mode: parquet }`**
  (warehouse only, `rows` mode only; see `spec.md`). Its rows leave the island
  budget and its ceiling becomes 256 MiB / 50M rows.

If `validate_cube_sql` is slow or times out, the cube is too big or too expensive
for the inline path - tighten the window, coarsen the grain, or (for a `rows`
dataset on a warehouse) move it to `data: { mode: parquet }`.

**The inline island has a hard ceiling, and a `hybrid` is the dataset most likely to
reach it.** A `hybrid` ships its `GROUP BY CUBE` lattice AND a row-level slice inline,
so its projected size grows on both axes at once - adding one dimension or one
`rows_sql` column can push it over. Publish warns as the projection approaches the
8388608-byte island ceiling, and crossing it fails the publish. The remedy is
**`rows_window: N`** on the dataset, which bounds the row slice (its `rows_sql` must
then end in a top-level ORDER BY - see above). That remedy is often free: a
`rows_window` set at or above the current row count keeps **every** row and still
bounds the projection.

Read that projection as a **conservative upper bound, not a measurement.** It
extrapolates future growth and can run an order of magnitude above the bytes actually
emitted - 7204320 projected against a 213196-byte island, roughly 34x, in one measured
case. Check the `bytes` a dry run actually reports before you bound or coarsen a cube
that would have fit comfortably.

### Size the dataset before you write the spec

The publish size check **projects from your DECLARATIONS and never looks at a row**, so
the refusal has nothing to do with how much data the query actually returns. On the spec
path the datasets are SEEDED first and the size check runs afterwards, during the compile
- so the rows really were fetched, and the estimator simply never consults them.

The smallest single cube that gets refused, to calibrate against: one dimension whose
declared `domains` reach the row cap, plus three measures. That is
`100,000 x 4 x 24 = 9,600,000` bytes against the 8,388,608 ceiling. Drop one measure and
`100,000 x 3 x 24 = 7,200,000` is accepted. The same cube is refused whether its query
returns five thousand rows or five million, because neither number is an input. The
arithmetic is small enough to do on paper, and doing it first is cheaper than three
rejected publishes.

Per dataset, the projection is **rows x fields x 24 bytes**, where each mode reads
"rows" and "fields" differently:

| mode | projected rows | fields per row |
|---|---|---|
| `cube`, **every** dimension bounded | `min(product of every dimension's declared domains/buckets, 100000)` | dimensions + measures |
| `cube`, **any** dimension unbounded | a flat 2000 | dimensions + measures |
| `lattice` | `product of (each dimension's bound + 1)` - its cells | **2 x** dimensions + measures |
| `rows`, with `rows_window: N` | `min(N, 100000)` | the `sql`'s output columns |
| `rows`, **no** `rows_window` | a flat 100000, the worst case the caps allow | the `sql`'s output columns |
| `hybrid` | its lattice **plus** its rows slice, both of the above | |

Sum every dataset; the total must be under **8388608** bytes. Separately, a
`lattice`/`hybrid` is refused above **50000** cells on its own. (The compiled body is
also capped at 5242880 bytes and, being a measurement of real bytes, is usually what
binds first in practice.)

Four things follow, and they are the ones authors get wrong:

- **Width costs as much as depth.** The multiplier is dimensions **plus measures**, so a
  ninth measure costs exactly what a ninth dimension would on every projected row. **Split
  a wide cube**: put the many measures on one narrow dataset, and give each extra breakdown
  dimension its own small dataset. Up to eight datasets share the one budget, and that is
  the whole reason splitting works - it turns the PRODUCT of the dimensions into a SUM over
  the datasets, and a sum of small products is far smaller than one big one.
- **A `lattice` dominates a budget.** It multiplies `(cardinality + 1)` rather than
  `cardinality`, and it charges **two** fields per dimension (the value plus its rolled-up
  flag). Six dimensions at 10 members each is 11^6 = 1,771,561 cells before the field
  multiplier - already 35x over the 50000 cell cap on its own.
- **Declaring `domains` on a `cube` dimension changes what you are charged, in either
  direction.** Bound every dimension and you are charged the exact product (which can be
  far more, or far less, than the rows the query returns). Leave even one dimension
  unbounded and the WHOLE dataset drops to the flat 2000 - partial declaration buys you
  nothing. On a `cube` the runtime does not read `domains` for its filter menus either (it
  reads the shipped rows), so declare them for the hard gate they buy at publish (see
  "What a publish WARNING means" in `spec.md`), knowing the projection moves with them.
  On a `lattice`/`hybrid` they are REQUIRED - that is what makes the cell count computable.
- **A `rows` dataset with no `rows_window` is charged 100000 rows** whatever it returns, so
  a five-column row slice alone projects at 12,000,000 bytes and cannot pass. Declaring
  `rows_window` is not a limit you are conceding, it is the number the projector was
  missing.

Worth stating plainly, because the direction is not obvious: this projection can also be
**far too small**. Since it never sees a row, an unbounded `cube` charged its flat 2000
rows has reported `ok` on a report whose compiled body was 235% of the publish cap (#896).
The exact gate is the compiled body, reported as `bytes` by every dry run - so dry-run
early and read that number rather than reasoning only from this model.
