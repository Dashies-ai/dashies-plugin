# Reference: the SQL you write

Part of the `dashies` skill (Steps 2-3). One read-only `SELECT` per dataset, written once and
re-run unattended on the schedule forever. Turning the validated statement into a dashboard is
Step 4, in `spec.md`.

## Read this before anything else in this file

**MOST OF THIS FILE ASSUMES A STATEMENT THAT GROUPS AND AGGREGATES, AND THAT IS THE SHAPE FOR THE
SAMPLE CONNECTION. A DASHBOARD READING A WAREHOUSE NEEDS THE OTHER SHAPE:** one row per underlying
record, carrying the columns the numbers are worked out from, with each number declared in the
spec rather than worked out in the SQL. `SKILL.md` Step 3 carries that rule, the test that goes
with it, and why a count is the number most likely to be got wrong.

**So wherever this file says to aggregate, to group to a grain, or to collapse something to the
grain you meant, read it as the sample-connection instruction.** On a warehouse the same move
hands Dashies a summary to summarize, and nothing refuses it.

**This is stated once, here, rather than beside each instruction.** Four rounds of qualifying
individual passages each found more of them, which is the evidence that per-site fencing does not
converge on a file whose default assumption is the thing being qualified.

**A SEPARATE AXIS, so the two are not confused: which SQL you WRITE differs by engine, and which
SHAPE you write is decided by the connection.** A statement can be right on one and wrong on the
other. **The engine difference most worth knowing about is timezone conversion**, because getting
it wrong buckets your dates into the wrong periods without failing. `### Time` covers it; for
per-engine syntax, go to `## Dialects`.

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

**This is the load-bearing decision, and WHICH grain is right depends on the connection.**

**Reading a warehouse, the statement returns one row per underlying record**, carrying the
columns the numbers are worked out from, and Dashies works them out when someone opens the page.
`SKILL.md` Step 3 carries that rule and the test that goes with it.

**Reading the sample connection, the statement returns one row per combination of the things you
group by, with the numbers already worked out**, and everything the dashboard can show is
computed from those rows.

**The two sections below are that second shape.** They are right for the sample connection and
wrong for a warehouse, where grouping to the grain the dashboard reports at hands Dashies a
summary to summarize. **Reading them as general advice is exactly how that happens.**

### Sample connection: every field somebody filters or charts on must be something you group by

If it is not in the `GROUP BY`, it does not exist as far as the dashboard is concerned. Decide
the filters and breakdowns first, then write the `GROUP BY` from that list.

### Sample connection: keep the set of values small wherever the question allows it

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

### Relative windows, anchored to the data

Never a hard-coded date range: a window that stops moving is a dashboard that quietly stops being
about the present. **And what the window is relative TO matters as much as that it is relative.**
Anchor it to the newest complete period the SOURCE holds, not to the wall clock:

```sql
-- Snowflake, a monthly mart carrying its own completeness flag. This shape was measured
-- right on a live dashboard: the newest bucket is complete, and the window holds the last
-- 24 of them whether or not the mart has moved this month.
where is_complete_month = true
  and month_start_on >= dateadd(month, -24,
        (select max(month_start_on) from your_db.analytics.fct_mrr_movements
         where is_complete_month = true))
```

On a raw fact table with no flag, the anchor is `max(<date>)` and the newest period is partial
unless the data happens to end on a period boundary, so exclude it in the same predicate: take
the periods strictly before the period that holds `max(<date>)`, and count the window back from
there.

**A `current_date()` anchor is right only when the source is genuinely live** - the sample
connection, whose dates are computed against today, or a table that is loaded every day. A mart's
data ends at its last complete period, behind the wall clock by up to a period while it is
maintained and permanently once it stops, so a wall-clock window is short by that gap on every
day, and on a source that has stopped moving the data left inside it shrinks by a day every day
while every number left on the page stays plausible, and nothing reports it. Measured on four
published dashboards: the two anchored to `current_date()` read a source that had stopped
moving; the two anchored to `max(month_start_on)` were the ones that were right.

---

## Aggregate away anything sensitive

**Everyone who can open the dashboard can read everything it carries.** What a tile shows and
what a filter hides do not narrow that. The audience is the dashboard's owner, or the workspace's
members, and never the public - dashboards are access-gated and there is no anonymous viewing.

But an audience is not a filter. **Aggregate to a grain coarse enough that no individual row,
person or secret is recoverable by anyone in that audience**, and watch small-cell counts that
could re-identify someone. A value nobody should see must not be in the statement's output at
all.

**Row-level security narrows the audience per ROW and does not change the paragraph above.** Where
`check_readiness` says it is available, a dataset can declare an `entitlement` block and each
viewer is served only the rows whose key value they were granted (`SKILL.md` Step 4). It filters by
one declared column: every other column of a row a viewer may see reaches them in full, and a
sensitive column is therefore still a statement-shaping problem rather than a grants problem.

---

## Write the statement, then validate it

**One read-only `SELECT` (or `WITH ... SELECT`) per dataset.** No DDL, no writes, no temp tables,
no multiple statements.

**The `WITH ... SELECT` half is engine-general and SQL Server is the exception.** There a statement
whose first token is `WITH` is refused at publish, because Dashies bounds it by wrapping it as a
derived table and T-SQL does not allow a common table expression inside one. Inline each one as a
derived table instead; the "Microsoft SQL Server" heading below carries the refusal and the rewrite.

**And no `;` ANYWHERE INSIDE the statement, comments and string literals included.** The executor
strips one TRAILING semicolon and then scans the rest of the statement for the raw character, so
it does not know a comment from code: `-- partial; see below` and `where region = 'a;b'` are both
refused as "more than one statement", and the message names neither the comment nor the literal.
A trailing `;` is the one position that is tolerated. Rephrase the comment; where a literal
semicolon is genuinely in your data, match it without typing one.

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
- **collapse the joined side to one row per underlying record**, then join. Reducing the many
  side to one row per join key is the move and it leaves the records intact. **Do not collapse to
  the grain the dashboard reports at**: that also stops the double-count, and on a warehouse
  dataset it is the shape Step 3 exists to prevent;
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

**NOT EVERY ENGINE HERE CAN BACK A DASHBOARD, AND THIS SECTION STILL COVERS ALL OF THEM ON
PURPOSE.** Which engines can hold a warehouse dashboard's data is read out of the database as each
publish is judged, so it is not a list this page can keep in step: **read on 2026-09-11 it was
BigQuery, Databricks, Postgres, SQL Server and Snowflake**, with Redshift refused at publish, at
`/source/connection`. Take the publish refusal over the date: it is built from the live set. The
PostgreSQL, Redshift, Databricks and SQL Server headings below repeat where their own engine stood
at that same reading, so those headings and this note go stale together rather than one at a time.
**What still
works on every engine is `introspect_schema`, `explore_data` and `validate_cube_sql`** - the gate
is on publishing a dashboard, not on using the warehouse. So this guidance is exactly what you
need to read one of those schemas, explore it and check a statement, and a statement you get right
today is still right on the day that engine can back a dashboard. Step 1 of the skill has what to
tell the user.

| Need | PostgreSQL | GoogleSQL (BigQuery) | Snowflake |
|---|---|---|---|
| Table reference | `from orders` | backtick `` `project.dataset.table` `` | database-qualified `from DB.SCHEMA.ORDERS` |
| Bucket a date (business zone) | `date_trunc('month', ts AT TIME ZONE 'America/Los_Angeles')::date` | `timestamp_trunc(ts, MONTH, 'America/Los_Angeles')` (zone is the 3rd argument) | `date_trunc('MONTH', convert_timezone('UTC','America/Los_Angeles', ts))` |
| Relative window, anchored to the data (`d` a DATE column; see "Relative windows, anchored to the data") | `d >= (select max(d) from t) - interval '12 months'` | `d >= date_sub((select max(d) from t), interval 12 month)` | `d >= dateadd('month', -12, (select max(d) from t))` |
| Relative window, wall clock (only when the source is genuinely live) | `now() - interval '12 months'` | `timestamp(date_sub(current_date('America/Los_Angeles'), interval 12 month))` | `dateadd('month', -12, current_timestamp())` |
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
  publishes and refreshes, and the numbers are simply wrong. Collapse back to one row per record
  of the thing you are counting - not to the grain the dashboard reports at.

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

### PostgreSQL

**CAN back a dashboard, read on 2026-09-11 - see the note at the head of this section.** Everything
below was already true for reading, exploring and validating; what changed is that a Postgres
connection now also holds a dashboard's data.

The PostgreSQL column of the table above is the dialect, and the `AT TIME ZONE` operand trap under
"Time" is the one that catches most statements. The rest of this section is about the CONNECTION
rather than the statement, because on this engine that is where the surprises are. Tell the user
the parts that ask something of them: the replica, the timeout, the certificate, the allow-list.

**Each dataset is read as one snapshot.** The read runs inside a single `REPEATABLE READ`
transaction, and the type check that runs first shares it, so one dataset is one consistent picture
of the database rather than a set of reads taken at different moments. Datasets are read one at a
time, each in its own transaction, so that is a guarantee about a dataset and not across the
dashboard. Nothing is asked of you for it.

**A refresh that fails leaves the numbers alone.** New data is written and checked before anything
is published, so a failed refresh leaves the previous numbers serving. The dashboard shows older
figures rather than broken ones, and the run detail says what failed.

**Point us at a read replica if that database also serves the product.** A scheduled refresh reads
a whole dataset in one command, which is a heavier and more predictable load than an interactive
query, so a replica is the right target where one exists. Two things come with it, and both are
worth saying out loud. A replica is behind its primary by however far it lags, so the dashboard is
reading a slightly older world. And a replica cancels a query that holds up replay for longer than
its own standby delay, which ends the read partway. Measured on 2026-09-08 across four providers,
that delay was 30 seconds on Neon, Supabase and RDS, and 14 seconds on Aurora. Raising
`max_standby_streaming_delay`, or turning on `hot_standby_feedback`, is the database-side fix, and
a cancelled read is named as a replica conflict rather than reported as a lost connection.

**A `statement_timeout` on the role we connect as bounds the whole read.** The read is one command,
so the timeout applies to the entire stream rather than to a step inside it, and a short one stops
a long dataset partway. Our own session raises the bound inside its transaction, which is enough
where the role's limit can be raised that way and is not where it is enforced above the role.
Measured on 2026-09-08: Supabase's `postgres` role carried two minutes and the other three
providers carried none. A refresh stopped this way reports that the warehouse cancelled the
query, and it does not claim whose ceiling fired, because on these paths the ceiling is often
ours. So read the role's own setting before concluding the statement is too slow.

**A pooled connection string works, and the direct one is still what to ask for.** Measured on
2026-09-08 against Supabase's session and transaction poolers and Neon's pooled endpoint: each
carried the whole read, and every setting the extract applies inside its transaction was read back
as set. Neither is refused. The direct string remains the recommendation, because that reading was
taken on an idle endpoint and a pooler under load has more reason to move a connection than an idle
one does.

**Certificate verification is on by default, and turning it off has a stated cost.** The connection
form is where that choice is made and it says what it costs: the connection is still encrypted, but
Dashies will not check that the server it reaches is the one named in Host, so an attacker able to
redirect the connection could read the credentials and the data. It exists ONLY for a database whose
certificate is not signed by a public authority, such as a self-signed or internal-CA certificate,
and it is meant to be turned back on once the provider offers a publicly signed one. Measured on
2026-09-08 across four providers, only Neon's certificate chained to a public root. That is a
reading about those providers, not a recommendation to turn verification off.

**A database that accepts connections only from an allow-list of addresses cannot be reached yet.**
The address we connect from is not fixed, so there is nothing stable to give their network
administrator. Say that plainly rather than having somebody widen their firewall: the answer is a
database we can reach, and publishing a stable set of addresses is a thing we do not do today.

**Cloud SQL, Azure Database for PostgreSQL Flexible Server and Heroku are reasoned rather than
measured**, so say
which you are doing if you tell somebody what to expect. Cloud SQL's public address is an
allow-list and its server certificate authority is per instance, so it is reachable only by opening
it to all addresses with verification turned off, and Google's own answer to that is its Auth
Proxy, which is a separate thing Dashies does not run. Azure verifies normally against public roots
and its firewall is an allow-list. Heroku's standard tier connects only with verification turned
off. None of the three was measured, and any of them may behave differently for a reason the
reasoning did not name.

**Two publish refusals are specific to this engine, and each names its own repair.**

A `numeric` column with no declared precision and scale is refused, because there is no exact
column to write it into:

```
the cube projects column "amount" (numeric), which cannot be carried into a published dashboard at all. A decimal with no declared precision and no declared scale is arbitrary-precision, so there is no exact column to write it into: it would be carried as a 64-bit float and lose digits that no later step can recover. It is refused here rather than after the dashboard is live. Declare the precision and the scale your data needs, in your own SQL - "amount"::numeric(18,2), or whatever width the values actually take - so the numbers are carried exactly and the choice of width is yours and visible rather than ours and silent.
```

Cast it in your own SQL to the width the values actually take. A decimal that DECLARES a precision
above 38 is refused too, through the same reader, and that sentence names 38 as the ceiling and
asks you to narrow the column deliberately rather than lose the digits silently.

**A refresh on this engine reads the whole statement every run.** A dataset that declares an
incremental descriptor is refused rather than accepted and quietly ignored:

```
dataset "orders" declares an incremental descriptor, and a refresh of a postgres connection reads the whole statement every run in this version: nothing resolves the window, so no partition is selected by it. It is refused here rather than accepted and silently ignored, because a schedule built on a descriptor that buys nothing costs the full read for ever with nobody told. Remove the incremental key to publish. A later slice adds incremental refresh for this engine and will honour the descriptor then.
```

So bound the window and anchor it to the data's own latest complete period, exactly as "Relative
windows, anchored to the data" above says.

The statement must be a single read-only `SELECT`, as on every engine.

### Redshift

**Could not back a dashboard when this was last read, on 2026-09-11 - see the note at the head of
this section.** Reading the schema, exploring it and validating a statement all still work.

A PostgreSQL dialect, so the PostgreSQL column applies almost verbatim. Use
`to_char(ts, 'YYYY-MM-DD')` or `date_trunc('month', ts)::date` for a text or date field. The
alias caveat above is the one thing that differs materially.

### Databricks

**CAN back a dashboard, read on 2026-09-11 - see the note at the head of this section.** Everything
below is dialect guidance that was already true for reading, exploring and validating; what changed
is that a Databricks connection now also holds a dashboard's data.

**Databricks SQL** (Spark SQL), a distinct dialect and not a PostgreSQL one. Table references are
backtick-quoted and three-level `` `catalog`.`schema`.`table` ``, and the catalog has to be one
this connection can actually read - `introspect_schema` is what says which - the built-in `samples`
catalog (`samples.nyctaxi.trips`, `samples.tpch.*`) is handy for a demo with no seed table. It
PRESERVES an unquoted alias. Bucket with `date_trunc('MONTH', ts)` or `date_format(ts, 'yyyy-MM')`;
a wall-clock relative window is `current_timestamp() - interval 12 months`; a conditional count is
`count_if(c)`. A `TIMESTAMP` arrives as an ISO-8601 UTC string, so bucket or format it in SQL
rather than parsing the text; big integers keep full precision as strings.

**Some column types are refused AT PUBLISH rather than at refresh, and the refusal names the
column.** `INTERVAL`, `VARIANT`, `USER_DEFINED_TYPE`, `NULL` (which Databricks itself spells `VOID`,
so the refusal prints both spellings when they differ), and a nested `ARRAY`, `MAP` or `STRUCT`
cannot be carried into a published dashboard at all. **Cast the column to a scalar - a number, a
string, a date or a timestamp - in your own SQL, or drop it from the projection.** Addressing into a
nested column is the move the section above describes, and it changes the grain, so collapse back
afterwards. **`INT`, `SMALLINT`, `TINYINT` and `FLOAT` are all carried and need no cast.**

**A Databricks refresh is a FULL RECOMPUTE.** Nothing incremental runs on this engine: every
scheduled refresh re-reads the whole window the statement asks for. So bound that window and anchor
it to the data's own latest complete period, exactly as "Relative windows, anchored to the data"
above says.

The statement must be a single read-only `SELECT`, and here the read-only guard is the only gate
- Databricks itself runs DML happily. The warehouse cold-starts a few seconds after an auto-stop,
so a small serverless warehouse with a short auto-stop keeps scheduled refreshes cheap.

### Microsoft SQL Server

**CAN back a dashboard, read on 2026-09-11 - see the note at the head of this section.** Everything
below is dialect guidance that was already true for reading, exploring and validating; what changed
is that a SQL Server connection now also holds a dashboard's data, and **three of the type traps
this page used to carry are gone with it**, listed under "What the older advice got right about a
path that is no longer the one your dashboard takes".

**T-SQL**, not a PostgreSQL dialect. Table references are `[bracket]`-quoted (`[dbo].[orders]`).
It PRESERVES an output alias as written, measured on a case-insensitive collation - collation
governs whether two names may coexist, not whether one gets rewritten.

Bucket with `cast(ts as date)` or `datefromparts(year(ts), month(ts), 1)`; a wall-clock relative
window is `dateadd(month, -12, sysutcdatetime())`.

#### Two statement shapes you can write are refused here

**Dashies bounds your statement by wrapping it as a derived table**, and T-SQL does not allow a
common table expression or an `ORDER BY` inside one. Every other engine's wrap is a `limit`
clause, which holds either shape fine; these two are T-SQL's. They are refused AT PUBLISH -
**and `validate_cube_sql` refuses NEITHER of them**, deliberately: it does not put that wrap around
your statement, so it validates a CTE-leading statement happily and the dry run is the first place
you can meet the refusal. Get these right before you write the statement.

- **Do not lead with `WITH`.** Refused, naming the dataset, with the exit beneath it:

  ```
  dataset `orders` starts with a WITH clause, and on SQL Server a dataset that keeps its rows outside the page cannot. Dashies bounds the statement by wrapping it as a derived table (`select top (n) * from (<your SQL>) as _dashies_seed_probe`), and T-SQL does not allow a common table expression inside one.

  inline each common table expression as a derived table in the FROM clause - `with r as (<body>) select ... from r` becomes `select ... from (<body>) as r` - and publish again. The restriction is on the wrap Dashies puts around your statement to bound it, not on the statement itself, so the query is unchanged apart from where the subquery is written.
  ```

  A leading `;WITH` is the same shape and is refused too: the detector skips a leading semicolon,
  and both comment forms, before it reads the first real token.

- **Do not end in `ORDER BY ... OFFSET ... FETCH`.** Refused:

  ```
  dataset `orders` ends in an ORDER BY carrying OFFSET or FETCH, and on SQL Server a dataset that keeps its rows outside the page cannot. Dashies bounds the statement by wrapping it as a derived table, T-SQL does not allow an ORDER BY inside one, and removing yours would move the window Dashies samples off the window the dashboard shows - so it is refused rather than rewritten.
  ```

  Its exit is to move the paging inside your own `FROM` clause: wrap the ordered, paged query as a
  derived table yourself and select from it. A plain trailing `ORDER BY` with no paging is fine -
  Dashies strips it, and a dataset's order is the dashboard's to decide anyway.

#### Four column types are REFUSED at publish, and the refusal names the accessor

`sql_variant`, `geography`, `geometry` and `hierarchyid` cannot be carried into a published
dashboard at all, and neither can a CLR user-defined type. The refusal names the column:

```
dataset `orders` projects column `shape` (geography), which Dashies cannot carry into a published dashboard at all. SQL Server hands that type back as bytes with no column type a dashboard can read, so it is refused here rather than after the dashboard is live.

select [shape].STAsText() in the cube instead, or drop the column from the projection, so the conversion is yours and is visible rather than ours and silent.
```

The accessor in that second sentence is chosen per type:

| Type | Select instead |
|---|---|
| `sql_variant` | `CAST(<column> AS <a concrete type>)` |
| `geography`, `geometry` | `<column>.STAsText()` |
| `hierarchyid` | `<column>.ToString()` |
| anything else it does not recognise | `CAST(<column> AS <a type this pipeline carries>)` |

One more is refused for a different reason: a `decimal` or `numeric` whose precision OR scale the
server does not report, because a width cannot be chosen for it. Both halves are checked, and an
absent scale is not the same as a scale of zero: `decimal(38,0)` is a legitimate reading.

#### LETTER CASE: SQL Server and Dashies group text differently, and neither answer is wrong

**This is the one thing on this page that changes a NUMBER rather than failing a read**, and it is
a choice to make deliberately rather than a defect to avoid.

Every SQL Server measured defaults to the collation `SQL_Latin1_General_CP1_CI_AS`, under which
`acme` and `ACME` are THE SAME VALUE. Dashies compares text by its bytes, under which they are TWO.
So one source column gives two different answers depending on WHO does the grouping, and the
difference is a row count rather than an ordering:

| Where the grouping happens | `acme` and `ACME` |
|---|---|
| your own `GROUP BY`, run by SQL Server | ONE group |
| your own `GROUP BY` with a binary collation forced on the key | TWO groups |
| the records come back and Dashies groups them | TWO groups |

**Measured end to end on 2026-09-11 (PR 7's measurement), with its control**: two values differing
by more than their case give two groups on both sides of the split, in SQL Server and in Dashies
alike, so what the table shows is about letter case and about nothing else.

**SO MOVING AN EXISTING CUBE ONTO THIS ENGINE CAN CHANGE A COUNT, WITH NOTHING RAISING.** A
statement that does its own `GROUP BY` on a text key and one that returns the records for Dashies
to group answer differently over the SAME source - one group against two - and neither is an
error. If the user is porting a dashboard whose numbers they already know, say this before they
compare the two and conclude something is broken.

**The merge is IRREVERSIBLE and silent, which is why it is worth a decision.** It happens inside
the customer's server, before Dashies sees anything, so once two values have become one row nothing
downstream can recover them: the refresh succeeds, the dashboard is built without complaint, the row
count is simply smaller than the number of distinct values in their source, and **nothing anywhere
raises**. And two statements asking the same question over the same source can report different
counts, with nothing on the page saying which one a reader is looking at.

**So pick the semantics and write it into the statement.** `SKILL.md` Step 3 has you return the
records on a warehouse, so Dashies does the grouping and its byte comparison is what you get unless
you say otherwise.

- **To keep case apart where SQL SERVER does the grouping**, put the collation on the key - Dashies
  does not add it for you:

  ```sql
  select region collate Latin1_General_100_BIN2 as [region], sum(amount) as [revenue]
  from dbo.orders
  group by region collate Latin1_General_100_BIN2
  ```

  It changes no schema and stores nothing differently, and it can cost an index seek on a large
  keyed column, so write it where the distinction matters rather than everywhere.

- **To fold case together where DASHIES does the grouping**, normalise the key in the statement,
  which is one function on the projected column:

  ```sql
  select upper(region) as [region], amount from dbo.orders
  ```

  `lower()` does the same job; pick whichever the user should read on the page, because what you
  project is what they see.

The same split applies to an `ORDER BY` or a `TOP` you rely on: SQL Server's default ordering is not
by bytes and Dashies' is, so the two disagree on a text key unless you force the collation.

#### Full refresh only

**A refresh on this engine reads the whole statement every run.** A dataset that declares an
incremental descriptor is refused rather than accepted and quietly ignored:

```
dataset "orders" declares an incremental descriptor, and a refresh of a mssql connection reads the whole statement every run in this version: nothing resolves the window, so no partition is selected by it. It is refused here rather than accepted and silently ignored, because a schedule built on a descriptor that buys nothing costs the full read for ever with nobody told. Remove the incremental key to publish. A later slice adds incremental refresh for this engine and will honour the descriptor then.
```

That sentence names the engine by its connection key rather than by the label the roster uses, so
"a mssql connection" is what an author actually reads and is not a typo of ours.

So bound the window and anchor it to the data's own latest complete period, exactly as "Relative
windows, anchored to the data" above says.

#### Time and time zones

- **SQL Server takes WINDOWS zone names** (`Pacific Standard Time`), never IANA
  (`America/Los_Angeles`), **and that holds on a Linux-hosted server too** - an IANA name is
  rejected there with "The time zone parameter ... provided to AT TIME ZONE clause is invalid."
  Check `select name from sys.time_zone_info` for what THIS server takes. Where the dashboard can
  bucket it instead, prefer returning the UTC instant over converting in T-SQL.
- **`datetimeoffset` keeps its instant and loses its offset.** If the originating offset matters,
  select it as a column of its own: `datepart(tzoffset, ts) as [ts_offset_minutes]`.
- **A local wall-clock bucket still takes the double `AT TIME ZONE`:**
  `cast(ts at time zone 'UTC' at time zone 'Pacific Standard Time' as datetime2) as [ts_local]`.
- **`datetime` and `smalldatetime` carry the SERVER's own granularity**, `datetime` to increments
  of about 3.33 ms, baked into the stored value before Dashies reads it. That is the source's
  precision rather than anything the pipeline did.

#### What the older advice got right about a path that is no longer the one your dashboard takes

Until 2026-09-11 a SQL Server dashboard could not hold its data with Dashies at all, and this page
carried three casts to work around what that path lost. **All three are now unnecessary**, and
writing them costs precision rather than buying it:

- **`decimal`, `numeric`, `money` and `smallmoney` are exact.** Your server converts them to text
  inside a projection Dashies writes around your statement, so a `decimal(38,10)` arrives with all
  its digits. **Do not cast money to integer cents.**
- **`tinyint` is carried as a 64-bit integer**, 255 included, so it needs no widening cast.
- **`datetime2` keeps its sub-second digits.** A `datetime2(7)` loses only its SEVENTH fractional
  digit, and that loss is where the dashboard stores the value rather than how it was read; at
  scale 6 and below it is exact.

What has NOT changed is the security boundary. The statement must be a single read-only
`SELECT`, and here the guard is defense in depth only, because T-SQL statement terminators are
optional. **The real gate is that the connection must use a read-only login** - the connect test
refuses a login with any write or admin privilege, and every refresh re-checks it before reading
anything - so the user connects a `dash_ro`-style login, never an admin. A publish whose login
stopped being read-only is refused, naming the dataset, with the exit beneath it:

```
dataset `orders` could not be seeded: the login this connection uses is not read-only, and Dashies refuses to read a SQL Server database through a login that can write to it.

connect the SQL Server source again with a read-only login, then publish again.
```

The fix is the user's rather than yours. Only their allowlisted schemas, plus the `sys` and
`INFORMATION_SCHEMA` catalogs, are readable.

---

## Big tables

**ON A WAREHOUSE YOU CANNOT SHRINK A DATASET BY AGGREGATING IT**, which is what several of the
bullets below reach for. **Your levers there are the window and the columns**: shorten the period,
and return only the columns the numbers are worked out from and the fields people filter or chart
on. **The window is the stronger of the two, and that is measured rather than judged** - extract
cost is dominated by a per-ROW term, so removing rows beats removing bytes (`cube-caps.ts` carries
the coefficients and the experiment).

- **Keep the window tight.** This is the biggest single lever on both connection kinds.
- **Keep the grain small**, on the sample connection. This is where most of the rest of that
  connection's cost goes, and on a warehouse it is the shape the rule forbids.
- **Group on real columns where you can**, again on the sample connection. If the warehouse
  already carries a pre-bucketed `day` / `week` / `month` column, group on it rather than
  truncating a raw timestamp.
- **For a star schema, joining a fact table to a small dimension table does not fan out** - it
  matches many rows to one. What fans out is joining two fact tables, or any join whose right
  side can match more than once. **On the sample connection, aggregate the fact first, then join,
  then re-aggregate.** On a warehouse, keep the records and reduce the RIGHT side to one row per
  key BEFORE joining. **On neither shape do you collapse the fact to the grain you report at**,
  however exact the arithmetic looks.
- **If `validate_cube_sql` is slow or times out, the statement is too expensive** for something
  that has to run unattended forever. Tighten the window; on the sample connection you can also
  coarsen the grain. Do not hope the scheduled run will be luckier.

**If what the user asked for genuinely cannot fit, say so plainly and early, before you write
SQL.** The honest answer is to aggregate it, bound the window, or split the report. Do not
silently narrow their grain, do not drop a filter to make something fit without telling them, and
do not promise that a later refresh will fill in more than the statement returns.
