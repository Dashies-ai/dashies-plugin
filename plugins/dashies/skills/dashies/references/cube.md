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
double-counts what merely persisted and yields a meaningless total. Like the
CTE/subquery-hidden non-additive measure and the fan-out JOIN double-count that
**"Verify the numbers"** below covers, this is an additivity error the publish gate
**cannot** catch - `sum(active_accounts)` passes every check and still ships a
silently-wrong number - so confirm a column is a flow before declaring it a `sum` measure. Carry a stock as a `min` / `max` / period-end value, or model
it on a `lattice` / `rows` dataset that recomputes the as-of figure under filters.

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
  refresh cap.

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

**Confirm categorical values before filtering on them.** Introspection does not
return the values a column holds, so a `where col = 'X'` with a wrong literal does
not error - it silently matches nothing and the measure reads zero. Read the real
values off a `select col, count(*) from t group by 1 order by 2 desc` first.

### Verify the numbers - `validate_cube_sql` proves it RUNS, not that it is CORRECT

`validate_cube_sql` executes your SQL and its mode-aware advisory catches the *common*
non-additive forms by reading the SQL text - but it cannot see a non-additive measure **hidden in
a CTE or subquery** (a ratio or `count(distinct ...)` computed inside a derived table and then
selected as a plain column reads as additive), nor a **fan-out JOIN that double-counts** (a join
to a one-to-many table inflates every summed measure). Both publish clean and refresh to a
plausible WRONG number - the worst failure a dashboard can have. You wrote the SQL, so you have
the dialect context to catch them: **verify the numbers against an independent query before
publishing.**

- **Additivity, per additive-declared measure.** Sum the measure across the cells
  `validate_cube_sql` returned, and compare that to an **independent direct aggregate** computed a
  different way - `select sum(<measure_expr>) from <base_table>` over the **single un-joined base
  source** (the base table's own `sum` / `count`, NOT the cube's joined `FROM` - a join there
  reproduces the very double-count you are checking for), ungrouped or over one filter slice, and
  run that check through `validate_cube_sql` too. If the two DIFFER, the measure is **not additive**
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

**4. Validate.** `validate_cube_sql({ sql, connection })` runs it and, because it
recognizes the `GROUP BY CUBE` + `__g_` shape, blesses the non-additive aggregates
with a v3 note (not the v2 warning). Confirm `row_count` is the lattice size you
expect (about `prod(cardinality_i + 1)`) and that it fits inline - v3 has no parquet
offload, so if the lattice is too big, drop or bound a dimension. Then carry the SQL,
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

**Snowflake gotcha:** an unquoted output alias folds to UPPERCASE (`as orders` ->
`ORDERS`), and the runtime binds keys case-sensitively, so the dashboard renders
blank on its first refresh. Quote every alias to the exact manifest key -
`sum(amount) as "revenue"` - or keep every manifest key uppercase.

**Redshift** is a PostgreSQL dialect, so the PostgreSQL column applies almost
verbatim. Like Postgres it folds an unquoted alias to **lowercase** (the opposite of
Snowflake), so keep manifest keys lowercase or quote the alias to the exact case; use
`to_char(ts, 'YYYY-MM-DD')` or `date_trunc('month', ts)::date` for a text/date
dimension.

**Databricks** takes **Databricks SQL** (Spark SQL) - a distinct dialect, not a
PostgreSQL one. Table references are backtick-quoted and three-level
`` `catalog`.`schema`.`table` `` (the built-in `samples` catalog -
`samples.nyctaxi.trips`, `samples.tpch.*` - is handy for a demo with no seed table).
Like Postgres/Redshift it folds an **unquoted** output alias to **lowercase**, but the
quote character is a **backtick**: quote every alias to the exact manifest key -
`` sum(amount) as `revenue` `` - or keep every manifest key lowercase, or the dashboard
renders blank on its first refresh. Bucket a date with `date_trunc('MONTH', ts)` or
`date_format(ts, 'yyyy-MM')`; a relative window is `current_timestamp() - interval 12 months`;
a conditional count is `count_if(c)`. A `TIMESTAMP` value arrives in the data island as an
ISO-8601 UTC string (`2024-01-15T10:30:00.123Z`, `T`-separated with a trailing `Z`), so
bucket/format it in SQL rather than parsing the raw text; big integers keep full precision as
strings. The cube must be a single read-only `SELECT` (the JS read-only guard is the only
gate - Databricks itself runs DML happily). The warehouse cold-starts a few seconds on the
first query after an auto-stop, so a **2X-Small serverless warehouse with a short auto-stop**
keeps scheduled refresh cheap.

**Microsoft SQL Server** takes **T-SQL** (Transact-SQL) - not a PostgreSQL dialect.
Table references are `[bracket]`-quoted (`[dbo].[orders]`). SQL Server is
**collation-sensitive** on identifier case, so the safe rule is to **keep every manifest
key lowercase AND quote each output alias with brackets to that exact key** -
`sum(amount) as [revenue]` - or the dashboard renders blank on its first refresh. A few
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
- **A row-level cube too large to inline uses v2 + parquet** (see `dashboard.md`).

If `validate_cube_sql` is slow or times out, the cube is too big or too expensive
for the inline path - tighten the window, coarsen the grain, or move to v2 + parquet.

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
