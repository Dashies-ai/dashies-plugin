# Reference: design the cube and write its SQL

Part of the `dashies` skill (Steps 1-3). The **cube** is the small, pre-aggregated
table your dashboard is built from - designing it well is what makes a refreshable
dashboard correct. Then you write one SQL query that produces it, and validate that
query. The HTML that renders the cube, and the manifest that carries the SQL, are in
`dashboard.md`.

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
    type first.
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
runtime re-aggregates by **summing** (or min / max / count) each measure across the
rows that remain. That is only correct for **additive** measures, so classify every
number before you write SQL.

**Additive - store these directly as measures** (they re-slice correctly under any
filter):

| What | Store as | `agg` |
|---|---|---|
| Sums of an amount (revenue, cost) | the summed column | `sum` |
| Counts of rows / events (orders, signups) | a `count(*)` column | `sum` |
| Smallest / largest in a cell | the value | `min` / `max` |

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
  grouping. Otherwise it is a v2 `count_distinct` measure.
- **Medians, percentiles, true averages under filters** cannot be reconstructed from
  sums at all - they mean **manifest v2** (see `dashboard.md`), which ships row-level
  rows and recomputes them in the browser.

**When any needed metric is non-additive, author v2.** The additivity rules here are
what v1's re-summing runtime demands; v2 lifts them because real SQL recomputes every
metric from rows. `validate_cube_sql` warns ("requires manifest v2") the moment your
SQL computes one of these, so the version decision arrives while you author.

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
look right - then keep the returned rows to seed the data island (`dashboard.md`).

**Confirm categorical values before filtering on them.** Introspection does not
return the values a column holds, so a `where col = 'X'` with a wrong literal does
not error - it silently matches nothing and the measure reads zero. Read the real
values off a `select col, count(*) from t group by 1 order by 2 desc` first.

### Dialects (warehouse connections)

The cube SQL dialect follows the connection's engine (`list_connections` reports
it). Everything above is engine-independent; only the syntax changes. Author against
`validate_cube_sql` for that connection, not from memory.

| Need | PostgreSQL | GoogleSQL (BigQuery) | Snowflake |
|---|---|---|---|
| Table reference | `from orders` | backtick `` `project.dataset.table` `` | database-qualified `from DB.SCHEMA.ORDERS` |
| Bucket a date (business zone) | `date_trunc('month', ts AT TIME ZONE 'America/Los_Angeles')::date` | `timestamp_trunc(ts, MONTH, 'America/Los_Angeles')` (zone is the 3rd arg) | `date_trunc('MONTH', convert_timezone('UTC','America/Los_Angeles', ts))` |
| Relative window | `now() - interval '12 months'` | `timestamp_sub(current_timestamp(), interval 12 month)` | `dateadd('month', -12, current_timestamp())` |
| Conditional count | `count(*) filter (where c)` | `countif(c)` | `count_if(c)` |

**Snowflake gotcha:** an unquoted output alias folds to UPPERCASE (`as orders` ->
`ORDERS`), and the runtime binds keys case-sensitively, so the dashboard renders
blank on its first refresh. Quote every alias to the exact manifest key -
`sum(amount) as "revenue"` - or keep every manifest key uppercase.

**Redshift** is a PostgreSQL dialect, so the PostgreSQL column applies almost
verbatim. Like Postgres it folds an unquoted alias to **lowercase** (the opposite of
Snowflake), so keep manifest keys lowercase or quote the alias to the exact case; use
`to_char(ts, 'YYYY-MM-DD')` or `date_trunc('month', ts)::date` for a text/date
dimension.

### Large warehouse tables

Against a big table, keep the cube cheap and let it validate fast:

- **Check the table's approximate size** with `introspect_schema` before you design.
- **Keep the grain small and the time window tight.**
- **Group on real columns where you can.** If the warehouse can carry a
  pre-bucketed `day`/`week`/`month` column, group on it rather than truncating a
  raw timestamp in the cube.
- **For a star schema, aggregate the fact table first, then join the small
  dimension table** and re-aggregate (sums of sums stay exact).
- **A row-level cube too large to inline uses v2 + parquet** (see `dashboard.md`).

If `validate_cube_sql` is slow or times out, the cube is too big or too expensive
for the inline path - tighten the window, coarsen the grain, or move to v2 + parquet.
