# Reference: the SQL you write

Part of the `dashies` skill (Steps 2-3). One read-only `SELECT` per dataset, written once and
re-run unattended on the schedule forever. Turning the validated statement into a dashboard is
Step 4, in `spec.md`.

**Everything in the first four sections is engine-independent.** Only the syntax changes, and the
dialects are at the bottom.

---

## Introspect first

`introspect_schema({ connection })` reports what Dashies can see on that connection: tables,
columns and their types, plus - where the engine supplies one - an approximate row count. Names
and types only; it reads no data.

It also states, in its opening lines, **the real limits for that connection and which layer
enforces them.** They differ per connection and they move. Read them there rather than from any
page, including this one.

Two things worth doing before you design:

- **Check the column TYPE of anything you are going to bucket by time.** A naive timestamp and a
  timezone-aware one need different SQL, and getting it wrong mis-buckets silently rather than
  erroring. See "Time" below.
- **Check the approximate size of anything big.** Where the estimate is absent - a BigQuery
  connection came back with none on any of 40-plus tables - measure it yourself with
  `explore_data({ sql: 'select count(*) as n from <table>', connection })`. A bare full-table
  aggregate pushes down to the warehouse and is fast even at millions of rows.

---

## Choose the grain

**This is the load-bearing decision.** The statement returns one row per combination of the
things you group by, with the numbers already aggregated. Everything the dashboard can show is
computed from those rows.

### Every field somebody filters or charts on must be something you group by

If it is not in the `GROUP BY`, it does not exist as far as the dashboard is concerned. Decide
the filters and breakdowns first, then write the `GROUP BY` from that list.

### Keep the set of values small wherever the question allows it

A field with a handful of distinct values costs almost nothing. A field with thousands is
expensive on every axis at once: it makes the data bigger, it makes the filter menu unusable, and
it is the single most common reason a dashboard cannot be prepared cheaply.

**Asking for a narrower thing is almost always the better answer than asking for a wider one**,
and it is usually what the user actually wanted. Two moves:

- **Top-N a big category** in SQL: keep the values that carry the volume and fold the rest into
  an `Other` bucket. Do not ship a 5,000-value dropdown.
- **Shorten the window.** "The last 18 months" instead of all history, when the dashboard is
  about recent movement.

### Time

**Bucket to the period the dashboard reports on** - `day`, `week`, `month` - never a raw
timestamp. A raw instant is high-cardinality and useless as a filter.

**Bucket in the business's own timezone, in the SQL.** A refresh runs with no session timezone,
so a bare `date_trunc('month', ts)` buckets in UTC and shifts month and quarter boundaries, and
an hour across DST. Declare the same zone on the dataset so the two agree.

**On Postgres and Redshift, mind the `AT TIME ZONE` operand trap:**

- a `timestamp with time zone` converts with the SINGLE form:
  `date_trunc('month', ts AT TIME ZONE 'America/Los_Angeles')::date`
- a naive `timestamp` storing UTC needs the DOUBLE form - label UTC, then convert:
  `date_trunc('month', ts AT TIME ZONE 'UTC' AT TIME ZONE 'America/Los_Angeles')::date`

**The single form on a naive timestamp mis-buckets silently**, so check the column type with
`introspect_schema` first. Publish and `validate_cube_sql` check what they can see and warn:
a single `AT TIME ZONE` is reported as ambiguous, and a dataset declaring a timezone its SQL
never names is reported as bucketing in some other zone. Use the double form, or
`CONVERT_TIMEZONE` / `FROM_UTC_TIMESTAMP` / BigQuery's third argument, and the warning goes away.

**A column that is already a `DATE` needs no conversion.**

### Relative windows only

`now() - interval '18 months'`, never a hard-coded date range. A window that stops moving is a
dashboard that quietly stops being about the present.

---

## Aggregate away anything sensitive

**Everyone who can open the dashboard can read everything it carries.** What a tile shows and
what a filter hides do not narrow that. The audience is the dashboard's owner, or the workspace's
members, and never the public - dashboards are access-gated and there is no anonymous viewing.

But an audience is not a filter. **Aggregate to a grain coarse enough that no individual row,
person or secret is recoverable by anyone in that audience**, and watch small-cell counts that
could re-identify someone. A value nobody should see must not be in the statement's output at
all.

---

## Write the statement, then validate it

**One read-only `SELECT` (or `WITH ... SELECT`) per dataset.** No DDL, no writes, no temp tables,
no multiple statements.

Then `validate_cube_sql({ sql, connection })`. **It is the only place that can prove the
statement survives the confinement, the caps and the timeout of the executor that will run it on
the schedule.** No warehouse tool can check that, because no warehouse tool runs inside that
executor. Bring it the finished statement.

`explore_data` is the call for the questions that come BEFORE the statement exists - what values
this column holds, how many customers there are, how far back the data goes. It is not a
validator and proves nothing about a statement you are about to publish.

---

## Validate proves it RUNS. You must prove it is CORRECT.

`validate_cube_sql` and the publish gate inspect the text and catch the obvious faults. **Two
things they cannot catch, and both refresh to a plausible wrong number forever:**

1. **A fan-out JOIN.** Joining to a table with several matching rows multiplies the source rows
   before the aggregate sees them, so every total over a parent-row column is multiplied too.
2. **A ratio or a distinct count buried in a CTE or a subquery**, presented as a plain number
   that can be added up. It cannot; adding two averages does not give an average.

### The cross-check, and it is required

For each number the dashboard treats as addable, **sum it across the whole statement's output and
compare against an independent direct aggregate over the source.** If they differ, it is
double-counting or it is not addable. The fixes:

- state it as a **ratio of two numbers that ARE addable** (a sum over a sum, a sum over a count),
  so the division happens after the filtering rather than before;
- **pre-aggregate the joined side** to the grain you meant, then join and re-aggregate. Sums of
  sums stay exact;
- count the parent rather than the joined rows: `count(distinct <the parent key>)`.

**The publish report prompts this as an `obligation`** whenever the statement reads more than one
row source - a JOIN, a CTE, a comma join, a derived table - however the numbers are written.
**That is a prompt to run the check, never a substitute for running it.**

**Read the converse carefully.** An EMPTY `obligations` means the statement reads one row source
so it cannot fan out. It is **not** a statement that your numbers are right.

### A total that is right per row and wrong when summed

The trap with no error message: **a number is safe to add up only over a FLOW, never over a
STOCK.** Revenue in a month is a flow, and twelve months of it sum to a year. A balance, a
headcount, an ARR snapshot is a stock, and summing twelve monthly snapshots gives a number twelve
times too big that looks entirely plausible.

This is not hypothetical. A real dashboard summed a point-in-time ARR snapshot across 24 tenure
months and put **$596,348,393** on a card against a real **$36,384,217**. The publish report now
warns when two datasets compute the same measure the same way, their fully rolled-up values
disagree, and a tile actually shows the differing one - but the warning is information, not a
verdict, and the fix is yours: take the latest snapshot rather than the sum, or give the stock
its own dataset that recomputes it under filters.

---

## Dialects

**The dialect follows the connection's engine**, which `check_readiness` and `list_connections`
both report. Author against `validate_cube_sql` for that connection rather than from memory.

| Need | PostgreSQL | GoogleSQL (BigQuery) | Snowflake |
|---|---|---|---|
| Table reference | `from orders` | backtick `` `project.dataset.table` `` | database-qualified `from DB.SCHEMA.ORDERS` |
| Bucket a date (business zone) | `date_trunc('month', ts AT TIME ZONE 'America/Los_Angeles')::date` | `timestamp_trunc(ts, MONTH, 'America/Los_Angeles')` (zone is the 3rd argument) | `date_trunc('MONTH', convert_timezone('UTC','America/Los_Angeles', ts))` |
| Relative window | `now() - interval '12 months'` | `timestamp(date_sub(current_date('America/Los_Angeles'), interval 12 month))` | `dateadd('month', -12, current_timestamp())` |
| Conditional count | `count(*) filter (where c)` | `countif(c)` | `count_if(c)` |
| Exact median | `percentile_cont(0.5) within group (order by x)` | `array_agg(x ignore nulls order by x)[safe_offset(div(count(x), 2))]` - there is no aggregate percentile | `percentile_cont(0.5) within group (order by x)` (not verified) |

### Alias letter-case, on every engine

Engines disagree about what an *unquoted* output alias comes back as: **Snowflake** folds it
UPPER (`as orders` -> `ORDERS`), **Postgres** and **Redshift** fold it lower, and **BigQuery**,
**Databricks** and **SQL Server** preserve it exactly as written.

**A case-only difference between the alias and the declared key is handled for you.** Publish and
refresh both fold a result column back onto the declared key when the two match apart from
letter case. So `sum(amount) as revenue` against a measure declared `revenue` is correct
whatever `check_readiness` reports as this connection's engine, including one added after this
page was written. Do not quote an alias to defend its case, and do not keep a set of UPPERCASE
keys to please Snowflake.

**What is NOT forgiven is two output columns differing only by case landing on one declared key**
(`revenue` and `REVENUE` in one `SELECT`). That is refused loudly, naming both, at publish and at
refresh - alias exactly one of them to the declared key.

Quote an alias when the name itself needs it - a reserved word, a space, punctuation - with the
engine's quote character: `"..."` on Postgres, Snowflake and Redshift; backticks on BigQuery and
Databricks; `[...]` on SQL Server.

**One caveat on Redshift:** what an alias comes back as depends on two cluster parameters, not on
how you write it. At the defaults, quoting preserves nothing, but
`enable_case_sensitive_identifier = true` makes a quoted identifier keep its case and
`describe_field_name_in_uppercase = on` returns every column name UPPERCASE regardless. Neither
is exotic. Rather than guessing, run
`validate_cube_sql({ sql: 'select 1 as MixedCase, 2 as "MixedQuoted"', connection })` once and
read the column names back; that answers both parameters in one call.

### A nested column is not a scalar, and reading one changes the grain

BigQuery `ARRAY` / `STRUCT` (the GA4 `event_params` shape, an `ARRAY<STRUCT<key, value>>`, is the
one you are most likely to meet), Snowflake `VARIANT` / `OBJECT` / `ARRAY`, and Databricks
`ARRAY` / `MAP` / `STRUCT` all have to be addressed into before they are usable.

- **Reading a field means naming it.** `rec.field` for a struct; a repeated column takes a join -
  `cross join unnest(event_params) as p` on BigQuery, `lateral flatten` on Snowflake, `explode`
  on Databricks.
- **That join MULTIPLIES rows**, which is the fan-out above arriving by a different door. After
  unnesting an array of three, one source row has become three, so `count(*)` counts 3 and any
  total over a parent-row column triple-counts it. **Nothing rejects this**: the statement runs,
  publishes and refreshes, and the numbers are simply wrong. Aggregate back to the grain you
  meant.

A nested column selected WHOLE arrives as JSON, which is usable neither as something to group by
(its values are objects, not labels) nor as a number.

### BigQuery

- **The obvious relative window does not run.** `timestamp_sub(current_timestamp(), interval 12
  month)` fails with `TIMESTAMP_SUB does not support the MONTH date part when the argument is
  TIMESTAMP type` - it accepts only MICROSECOND through DAY on a `TIMESTAMP`. Go through `DATE`
  as the table shows, or use `interval 365 day`.
- **Temporal types read back as ISO-8601, and only `TIMESTAMP` loses anything.** A `TIMESTAMP`
  arrives as an ISO-8601 UTC string (`2026-08-02T19:37:57.965Z`). `DATE` (`2026-08-02`),
  `DATETIME` (`2026-08-02T19:37:57.965165`) and `TIME` (`19:37:57.965165`) come back verbatim -
  those keep MICROseconds while `TIMESTAMP` is rounded to milliseconds, so on the rare occasion
  sub-millisecond precision matters, select the column as `DATETIME` or as a string.
- **`introspect_schema` reports no row estimate**, so count it yourself as described above.

### Redshift

A PostgreSQL dialect, so the PostgreSQL column applies almost verbatim. Use
`to_char(ts, 'YYYY-MM-DD')` or `date_trunc('month', ts)::date` for a text or date field. The
alias caveat above is the one thing that differs materially.

### Databricks

**Databricks SQL** (Spark SQL), a distinct dialect and not a PostgreSQL one. Table references are
backtick-quoted and three-level `` `catalog`.`schema`.`table` `` - the built-in `samples` catalog
(`samples.nyctaxi.trips`, `samples.tpch.*`) is handy for a demo with no seed table. It PRESERVES
an unquoted alias. Bucket with `date_trunc('MONTH', ts)` or `date_format(ts, 'yyyy-MM')`; a
relative window is `current_timestamp() - interval 12 months`; a conditional count is
`count_if(c)`. A `TIMESTAMP` arrives as an ISO-8601 UTC string, so bucket or format it in SQL
rather than parsing the text; big integers keep full precision as strings.

The statement must be a single read-only `SELECT`, and here the read-only guard is the only gate
- Databricks itself runs DML happily. The warehouse cold-starts a few seconds after an auto-stop,
so a small serverless warehouse with a short auto-stop keeps scheduled refreshes cheap.

### Microsoft SQL Server

**T-SQL**, not a PostgreSQL dialect. Table references are `[bracket]`-quoted (`[dbo].[orders]`).
It PRESERVES an output alias as written, measured on a case-insensitive collation - collation
governs whether two names may coexist, not whether one gets rewritten.

Type traps, all of which produce a failed read rather than a wrong number:

- **Cast `GROUPING()` flags and any `tinyint` to a wider int.** Both are read as a 1-byte value
  Dashies cannot carry, and a `tinyint` above 127 fails outright. Write
  `cast(<tinyint column> as int)`.
- **Timezones need the DOUBLE `AT TIME ZONE`, cast back to `datetime2`.** `datetimeoffset` is
  unsupported and `AT TIME ZONE` returns one, so:
  `cast(ts at time zone 'UTC' at time zone 'Pacific Standard Time' as datetime2) as [ts_local]`.
  **SQL Server uses WINDOWS zone names** (`Pacific Standard Time`), not IANA
  (`America/Los_Angeles`) - though a Linux-hosted server may accept IANA. Check
  `select name from sys.time_zone_info` for what THIS server takes.
- **Precision.** `decimal` / `numeric` / `money` are read through a float hop of about 15 to 16
  significant digits, so cast money to integer cents if you need exactness; `datetime` and
  `datetime2` truncate to whole seconds, so bucket or format in SQL rather than relying on
  sub-second precision.

Bucket with `cast(ts as date)` or `datefromparts(year(ts), month(ts), 1)`; a relative window is
`dateadd(month, -12, sysutcdatetime())`.

The statement must be a single read-only `SELECT`, and here the guard is defense in depth only,
because T-SQL statement terminators are optional. **The real gate is that the connection must use
a read-only login** - the connect test refuses a login with any write or admin privilege - so the
user connects a `dash_ro`-style login, never an admin. Only their allowlisted schemas, plus the
`sys` and `INFORMATION_SCHEMA` catalogs, are readable.

---

## Big tables

- **Keep the grain small and the window tight.** This does more than everything else combined.
- **Group on real columns where you can.** If the warehouse already carries a pre-bucketed
  `day` / `week` / `month` column, group on it rather than truncating a raw timestamp.
- **For a star schema, aggregate the fact table first, then join the small dimension table and
  re-aggregate.** Sums of sums stay exact, and the join then has nothing to fan out.
- **If `validate_cube_sql` is slow or times out, the statement is too expensive** for something
  that has to run unattended forever. Tighten the window or coarsen the grain; do not hope the
  scheduled run will be luckier.

**If what the user asked for genuinely cannot fit, say so plainly and early, before you write
SQL.** The honest answer is to aggregate it, bound the window, or split the report. Do not
silently narrow their grain, do not drop a filter to make something fit without telling them, and
do not promise that a later refresh will fill in more than the statement returns.
