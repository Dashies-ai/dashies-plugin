# Filling the Dashies spec (Step 4)

You author a dashboard by writing a **spec** - one small YAML document - and passing it to
`publish_dashboard`'s `spec` argument. The server does the rest: it builds the dashboard from the
spec, checks the whole thing, and runs each dataset's `sql` once, live, so the published page
carries real numbers. **The spec carries the page too**: `look: { html }` is the page body you
write - your markup and CSS, the widgets the runtime draws (`references/widgets.md`) and your own
page code - on every connection; see **The page: `look`**. A widget naming a dimension or a measure
that neither the spec nor the SQL has is a **pointed publish error naming the exact field**, not a
blank chart or a silently wrong number that ships and rots. Name a measure by its own key, never by
the column it reads: on a warehouse a column the SQL returns passes that check too
(`references/widgets.md`, "What publish checks").

So the YAML is mechanical: turn the statements you wrote in Step 3 into datasets, and put the page in
`look`. The hard part - the grain and the correctness of the SQL - is already done, and how the page
looks is the style question's (`SKILL.md` Step 4).

The full field contract is the JSON Schema at `https://dashies.ai/schema/dash/v1.json` (`$id`,
draft 2020-12) and it is the exhaustive source of truth. This reference is its readable form: the
fields you author with and their load-bearing bounds. `additionalProperties` is `false`
everywhere, so an unknown or misspelled key is an `[L2]` error naming the key, never silently
ignored.

## House rules (read once)

- **YAML 1.2 core** (the server parses with `version: "1.2"`). Only `true` / `false` are
  booleans, only `null` / `~` / empty is null, and a bare number is a number - so quote a STRING
  value that would otherwise read as one of those (a numeric-looking code like a zip, a literal
  `true` you want as text, a bare `null`). Unlike YAML 1.1 there is NO "Norway problem" here:
  `no` / `off` / `yes` / `NO` and a date-like `2026-07-01` all already parse as plain strings, so
  `domain_values: [NO, SE]` is fine (quoting a string is always safe too). JSON is also accepted
  (a spec is valid JSON-as-YAML) if you prefer no ambiguity.
- **The `slug`, when present, must equal the publish `path` slug**
  (`publish_dashboard({ path: "<slug>", spec })`). Omit it and the path slug is used. A mismatch
  is an `[identity]` error at `/slug`.
- **Every publish runs the SQL live.** The server executes each dataset's `sql` through the same
  confined read-only path `validate_cube_sql` uses, then checks the declared dimensions and measures
  against the ACTUAL result columns. A dataset whose SQL fails, returns zero rows, or whose
  declarations do not match the columns it returned, cannot publish - so a spec that would render
  fake zeros never reaches the URL.
- **Numeric honesty is automatic.** Every value renders exactly or shows `-` (unavailable), never
  a rounded-wrong number. You do not manage precision.
- **Declare what the page draws.** A declared dimension or measure can be handed to any viewer's
  browser whether or not your page shows it, and publish cannot tell which ones your page code
  reads, so it does not warn about one nothing reads. It warns once if the page has no way to read
  its data at all - no `dashies.data` call and no widget. A warning never blocks: the advisory
  arrives on the SUCCESS report prefixed `warning:`, and a FAILED publish lists only real errors, so
  its count is the number of things you actually have to fix.
- **No em or en dashes** in any spec string - titles, labels, and the text of your page. Plain ASCII
  hyphens only.

## Top level

Required: `dashies`, `title`, `source`, `datasets` and `look`.

| Key | Type | Notes |
|---|---|---|
| `dashies` | `1` | Format version. Always `1`. |
| `title` | string (1-120) | The dashboard name (also the default display name). |
| `slug` | kebab-case, `^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$` (1-64 chars, alphanumeric first and last) | Optional; must equal the publish path slug when set. |
| `description` | string (<=4000) | Optional prose about the dashboard. Your page shows only what its own markup writes. |
| `intent` | string (<=2000) | Optional semantic hint (what this dashboard is for) - guidance for tooling, not shown to viewers. The same optional `intent` is accepted on a dataset (<=2000) and on a dimension and a measure (**<=1000 each** - the tighter limit, so budget a measure's against 1000). It is the field that carries a measure's **provenance** - see **Provenance** below. |
| `source` | object | The one connection and schedule the whole dashboard refreshes on (below). |
| `datasets` | map, 1-8 | Named datasets; each key `^[a-z][a-z0-9_]{0,31}$`. First declared is the default. |
| `assets` | map, 1-8 | Optional. Images the SERVER fetches, checks and inlines for you: each key `^[a-z][a-z0-9_]{0,31}$` names an `{ url }` (https only), referenced from your page as `asset:<name>`. Never type image bytes into a spec. See **Assets** under **The page: `look`**. |
| `look` | object | The page body, yours: your markup and CSS, the runtime's widgets and your page code, on every connection. See **The page: `look`**. |
| `entitlement` | object | Optional, and only alongside a dataset that declares one: `admins: "filtered" \| "unfiltered"`. Absent means `filtered`, and `unfiltered` exempts admins of the dashboard's own workspace from the filter once the dashboard is published carrying it. Declaring it with no dataset-level `entitlement` is refused. See **Row-level security**. |
| `row_level_security_removed` | boolean | Optional, and written by hand or not at all: `true` says a per-viewer filter this dashboard used to carry is gone on purpose. A republish that drops the `entitlement` block is refused without it, and declaring it beside an `entitlement` block is refused too. See **Row-level security**. |

`source` (required `connection` plus `schedule`):

| Key | Type | Notes |
|---|---|---|
| `connection` | `"self"` or a connection UUID | The built-in connection, or a connection id from `check_readiness` / `list_connections`. Required, with no default. |
| `schedule` | `manual` / `hourly` / `daily` / `weekly` / `monthly` | The coarse cadence (Step 5). Refine the timing afterwards with `set_refresh_schedule`. |
| `timezone` | string (1-64 chars) | Optional business zone for date bucketing; use an IANA zone name (e.g. `America/New_York`). The schema checks length only, not that the value is a real zone. |
| `upload` | UUID | Which uploaded CSV or Excel file this dashboard reads. **Required when `connection` is the workspace's uploaded-file source, and refused on any other connection**, `self` included. No default; the newest upload is never assumed. See below. |

**`source.upload`, and why it is written by hand.** A dashboard built from a spreadsheet names the
workspace's uploaded-file source in `connection` and ONE upload in `upload`. Both halves of that
rule are refused at `/source/upload` and both name the fix: a file source carrying no `upload`, and
an `upload` beside a warehouse connection or beside `connection: self`. **Nothing resolves an absent
`upload` to the newest one**, because then republishing an unchanged document would change the
numbers on the page with nothing in the document saying so.

**New data is a new upload plus a republish**, so `upload` is the field that moves - and
`replace_file_upload` is what moves it, on every dashboard reading that file at once, after checking
each of them against the new one. The previous upload is left as it was and a dashboard still naming
it keeps reading it. **`schedule: manual` is
the honest default on this source**: a refresh re-runs the same SQL over the same file, so it only
changes the numbers if that SQL is time-relative. A cadence is accepted with an advisory saying so
rather than refused. `SKILL.md`, "A spreadsheet instead of a warehouse", carries the upload loop and
the rule about not casting around a declared type.

## datasets

Required: `sql`, `dimensions`, `measures`. **Nothing else is yours to decide** - how the data is
prepared and where it is kept is chosen by the server from exactly these three plus the source,
and the publish report tells you what it chose for each dataset and why. **Row-level security is
the one exception**, and it is an exception in both directions: a dataset that filters its rows per
viewer declares an `entitlement` block, and then it must also declare `mode: resolved`, which is
the only `mode` this document ever asks you to write. See **Row-level security**.

| Key | Type | Notes |
|---|---|---|
| `sql` | string (8-100000) | The single read-only `SELECT` from Step 3, already validated. |
| `entitlement` | object | Optional. Which column decides who may see a row, and who is granted which values. Requires `mode: resolved` on the same dataset. See **Row-level security**. |
| `dimensions` | map, 1-12 | Each key `^[a-z][a-z0-9_]{0,63}$` is an output column of `sql`. Value: `{ type?, label?, domains?, buckets?, intent? }`. |
| `measures` | map, 1-24 | Each key `^[a-z][a-z0-9_]{0,63}$` is a measure. Value: an **agg measure** or a **ratio measure** (below). |
| `intent` | string (<=2000) | Optional semantic hint for this dataset. |

**dimension** - `type` is OPTIONAL and, when set, is `category` or `date` ONLY (a `type: string`
is an `[L2]` error). It describes the FILTER or AXIS role, not the SQL column type. Omit it and
the dimension is treated as `category`; set `type: date` for a date dimension so it buckets as
one. An optional `label` (<=80 chars) sets the display name.

**A `type: date` dimension must hold DAYS**: a DATE column, or text in `YYYY`, `YYYY-MM` or
`YYYY-MM-DD` form. Two column shapes are REFUSED at publish, because the page keys a date dimension
by its day and would draw them wrong. **A timestamp** (`date_dim_timestamp`) splits each day by
time and filters a day down to its midnight rows, so cast it to a date in the SQL: `CAST(col AS
DATE)`, `TRUNC(col)` on Oracle, and on BigQuery `DATE(col)`, or `DATE(col, '<zone>')` for a TIMESTAMP
you truncated in a time zone, since a bare `DATE` reads its day in UTC. That includes `date_trunc('day', col)`,
which returns a timestamp, so cast it too - and on an uploaded file, Postgres and Databricks
`date_trunc` returns a timestamp even over a DATE column, so a month bucket needs the cast as well:
`CAST(date_trunc('month', d) AS DATE)`. **A number** (`date_dim_numeric`), such as an integer
year, reads as milliseconds since 1970 and shows as 1970-01-01, so drop `type: date` (it then groups
and filters by its own value) or build a date in the SQL. The refusal names the cast for your
engine. **A timestamp with times of day is refused under ANY declaration**
(`timestamp_dim_has_time` when it is not a `date`): the page keys every timestamp dimension by its
day, so for hours, format the timestamp as text in the SQL. **The publish can only refuse what it
can see is a timestamp. On SQL Server, and on Snowflake for `TIMESTAMP_LTZ` and `TIMESTAMP_TZ`, a
timestamp reaches it as text**, so only a `type: date` dimension over one is checked, and only by
its values: one whose rows carry a time of day is still refused, and a category over one is not
checked at all. Cast or format such a column in the SQL yourself before you use it as a dimension.

**Declare the dimension's bound wherever you know it, and prefer to know it.** A `category`
dimension declares `domains` - its value list, 1 to 200 unique entries, each a string, number or
boolean. A `date` dimension declares `buckets` - the maximum bucket count, 1 to 1000. **On a
dashboard reading the sample connection this is the single most useful thing you can tell the
server**: a dimension with a known, small set of values is what lets a dashboard be prepared
cheaply and answer exactly under every filter, and a dimension you cannot bound is a signal to go
back to Step 3 and ask a narrower question.

**On a dashboard that reads a warehouse, a bound buys nothing and narrowing is not the remedy for
anything the page shows.** Dashies works those numbers out when someone opens the page rather than
ahead of time, so there is no set of states to keep small. Declare `domains` there for the ORDER of
the members, which is the other thing they do: every widget draws the members in that order, and page
code is handed each grain's rows in it, with one exception, which the `rows` entry under "The shape
your script is handed" names (`references/widgets.md`, "Member order on an axis").
**The one exception is a dataset your page code draws at its declared grain**: it is handed every
declared dimension at once, so bound them, and if the page reports that the grain is too wide,
declare fewer of them on that dataset - see **The page: `look`**.

On every connection `domains` also fixes the ORDER every widget draws the members in, and page code
is handed them in - see `references/widgets.md`, "Member order on an axis".

**measure** - exactly one of:

- **agg measure** (`agg` required): `agg` is one of `sum` `count` `min` `max` `avg`
  `count_distinct` `median` `percentile_cont` `percentile_disc` `stddev` `variance` `mode`.

  **FOUR OF THOSE TWELVE CANNOT BE USED ON A DASHBOARD THAT READS A WAREHOUSE:**
  `percentile_disc`, `stddev`, `variance` and `mode`. Dashies works a warehouse dashboard's
  numbers out when someone opens the page, and those four are not ones it can work out that way.
  Asking for one is refused at `/datasets/<name>/measures`, and the refusal names the MEASURES
  rather than the aggregate, so read the names it gives you. **The other eight are available
  everywhere, and they include `sum`, `count`, `min` and `max`** - the refusal is a narrow one,
  not a retreat to only the simplest numbers.

  **All twelve remain available on the sample connection**, whose numbers travel inside the page.
  Optional `column` (the raw column the aggregate reads; defaults to the measure key),
  `percentile` (0 < p < 1, for `percentile_cont` / `percentile_disc`), `label` (<=80), `unit`,
  `intent`.

  **`min` and `max` over a DATE or TIMESTAMP column - a "last order date" - are available where
  Dashies keeps the dataset's data** (a warehouse connection or an uploaded file). A widget prints the
  value as its day; page code receives it as TEXT, a DATE as `YYYY-MM-DD` and a TIMESTAMP as its
  ISO 8601 UTC instant, `YYYY-MM-DDTHH:MM:SS.sssZ` - and on Oracle Database a DATE arrives as that
  instant, because Oracle's DATE carries a time. On the sample connection it is refused. **On SQL
  Server it is refused too**: the publish there cannot read a column's type, so it cannot tell a date
  from text. **On Snowflake a `TIMESTAMP_LTZ` or `TIMESTAMP_TZ` column is refused for the same
  reason** until you cast it in the SQL, to a DATE or to
  `TO_TIMESTAMP_NTZ(CONVERT_TIMEZONE('UTC', col))`. An aggregate that needs a number, such as `sum`
  or `avg`, is refused over a date everywhere; `count` and `count_distinct` count dates as they count
  anything else.

  **Declare the aggregate the number actually is.** Do not reach for `sum` because it seems
  safer - a median declared as a sum is a wrong number, and the server can prepare a median
  correctly if you say that is what it is. Some combinations of aggregate and dimension cannot be
  prepared at all; those are refused at publish, in words that tell you what to change about the
  question.

  Optional **`stock: true`** declares that this measure reads a **point-in-time STOCK** - a level
  measured at an instant (ARR, headcount, a balance, open tickets, inventory on hand) - rather
  than a per-period **FLOW** that accumulates (new ARR, hires, deposits, tickets opened). Nothing
  else changes: it does not affect the SQL, the refresh, or the render. It is the ONE input the
  server's sum-over-a-stock check needs, and nothing can infer it - `sum(ending_arr)` and
  `sum(new_arr)` are identical to any static analysis, so an undeclared stock is invisible.
  Declare it whenever a measure is a level, and the publish report warns (never blocks) if the
  dashboard sums it across the grain. **This is a real shipped wrong number, not a hypothetical:**
  summing `ending_arr_usd` over 24 tenure months reported $596M against a real $36M, because
  summing a snapshot recounts the same customers in every period. If you want the level, read the
  latest period or use `max`; if you want a trend, use a per-period `avg` / `min` / `max`; if the
  sum really is intentional because the rows do not overlap, ignore the warning.

- **ratio measure** (`ratio` required): `{ num: <measure key>, den: <measure key> }` - a ratio of
  two other declared measures, worked out by the runtime under every filter state and delivered
  on each row under its key (never a stored pre-divided average, and never something your markup
  recomputes). Each side may optionally set `num_scope` / `den_scope: all` to take that operand
  from the unfiltered total instead of the filtered one. Optional `label` (<=80), `unit`, `intent`.

  **This is how you carry a rate or a percentage, and it is the exact way to carry an AVERAGE**:
  `num` is the sum measure, `den` is a `count(*)` measure, which makes the figure exactly sum
  divided by count - the true weighted mean over the source rows, correct under every filter. It
  is strictly better than a stored average, because a stored average cannot be re-derived once a
  viewer filters.

**unit** (optional, on any measure) - controls display, never the stored value:
`{ kind: currency|percent|count|number, ... }`. `currency` REQUIRES `scale` (`cents` or `units`)
and takes an optional uppercase three-letter `currency` code (`^[A-Z]{3}$`, e.g. `USD`);
`percent` REQUIRES `scale` (`fraction` for 0..1, `points` for 0..100); `count` and `number` take
no `scale`. Optional `decimals` (0-6), `compact`. **Pick `scale` to match what your SQL emits.**
The wrong scale is a 100x display error nothing can catch for you, because it is a display choice
rather than a structural fault.

**`cents` and `points` depend on WHO DRAWS the figure, and the schema accepts them either way, so
the refusal comes at publish rather than at validation.**

- **Page code is handed the divisor, so there they are ACCEPTED.** On a `cube`, `rows` or
  `resolved` dataset, a measure you read through `dashies.data` arrives UNDIVIDED with
  `scale: 100` beside its `format`, and `dashies.format(value, measure)` divides and formats it
  where you draw it; your own division is refused at publish.
- **A widget is handed the raw value with no divisor, so a measure a widget draws is REFUSED**,
  naming the widget, because the figure would render 100x. A `table` widget that names no
  `data-columns` draws every measure of its dataset, and so does any widget carrying `data-group`
  without `data-columns`, and so does a `data-drill` for every measure of the dataset it names; a
  table that names columns draws the measures it names, grouped or not. For a measure a widget
  draws, divide in SQL and declare what the column then holds: an integer-cents column becomes
  `amount_cents / 100.0` and `scale: units`, a 0-to-100 percent becomes `pct / 100.0` and
  `scale: fraction`.
- **A dataset in any OTHER mode refuses them too**, because its data block carries no format and
  no divisor, so your callback would get the 100x value with nothing beside it saying so. You do
  not choose the mode and you do not have to work out which one you got, with one exception: a
  dataset that declares an `entitlement` declares `mode: resolved` itself (see **Row-level
  security**), and `resolved` is one of the three modes named above. Otherwise the publish report
  says what the server chose for each dataset, and the refusal names it.

**A worked line, because the rule "the browser draws, it never computes" is easy to over-read
here.** A `percent` measure declared `scale: fraction` arrives as `0.42`; drawing it as `42%` is
presentation, and it is Dashies' to do: `dashies.format(value, measure)` formats it the way the
runtime's own widgets do, and divides a `scale: 100` value on the way. Your page code does neither
step itself, because publish cannot tell a unit conversion from a number worked out, and refuses
both. What the rule is about is a number worked out of two values: `r.discount / r.revenue` is a
`ratio` you declare, `r.a + r.b` a measure you declare, and a rollup is `by`. A value that arrived
as its exact digits in a string is one the runtime could not hand over as a Number, and
`dashies.format` draws those digits as they came, moving the decimal point for a declared
`scale` rather than dividing, which would round it.

**A unit's `kind` reaches most widgets; its `currency` and `decimals` reach page code alone.**
`dashies.format(value, measure)` applies each measure's own format, currency code and decimal places.
A widget drawing one measure draws the kind the `unit` declares wherever Dashies carries the format
with the data, but a ratio a widget draws is a percent and a chart of several measures draws plain
numbers, whatever their units say, until the widget's `data-format` says otherwise. Every widget prints
currency in one page-wide currency and precision taken from the first currency measure the spec
declares, so declare that measure first. `references/widgets.md`, under Display, says which widgets
`data-format`, `data-currency` and `data-decimals` override that on.

## Provenance - say where each definition came from

**Dashies keeps a dashboard fresh, versioned and shareable; it does not decide what a
metric means** (SKILL.md, "Before Step 0"). That claim is only worth something if a later
reader can CHECK it - open the spec and see that the number traces back to the company's
own definition rather than to something an AI invented one afternoon. So record where each
measure's definition came from, in the spec.

**Use `intent`. There is no separate provenance key and you should not want one.** The
spec's schema is `additionalProperties: false` everywhere, so an invented key is an `[L2]`
publish error, and `intent` is exactly the sanctioned slot: free text, "guidance for
tooling, not shown to viewers", already accepted on the dashboard root, every dataset,
every dimension and every measure. It is stored **verbatim** as part of the
spec bytes, so `get_dashboard_spec` hands it back unchanged and an editor sees it before
touching the measure. Nothing renders it to a viewer, so it costs the dashboard nothing.

**Limits, which differ by level:** root and dataset `intent` are **<=2000** chars; a
**dimension and a measure are <=1000 each**. Provenance goes on the measure, so
budget against 1000 - a citation and a sentence, not a pasted model file.

Three cases, and write the one that is true:

```yaml
measures:
  # 1. It came from a semantic layer -> name the layer, the metric, and how to re-derive it.
  mrr:
    agg: sum
    intent: >-
      dbt semantic layer, metric `mrr` (models/marts/metrics.yml). Definition taken from
      dbt, not re-derived: active paid subscriptions only, excludes internal accounts,
      monthly grain on subscription_start. Re-derive with `dbt ls --resource-type metric`.
  # 2. Derived from warehouse tables with no semantic layer to defer to -> say that plainly.
  refund_amount:
    agg: sum
    intent: >-
      Derived from analytics.fct_refunds; no semantic-layer definition exists for refunds.
      Authored for this dashboard, so it is NOT a company-agreed definition - if one is
      added later it wins over this.
  # 3. No tooling was reachable and the user chose the Dashies connection -> record the ask.
  active_users:
    agg: count_distinct
    intent: >-
      No dbt or warehouse tooling reachable in the authoring session (Snowflake MCP was
      access-denied); user asked and confirmed to proceed against the Dashies connection.
      Defined here as distinct user_id with an event in the period. Unverified against any
      company definition.
```

The dashboard-level `intent` is the right place for the one-line summary of the same fact
("metric definitions taken from the dbt semantic layer; no measure re-derived from raw
tables"), so a reader gets the posture without reading every measure.

Case 3's wording is the load-bearing one. **A measure you defined yourself must say so.**
The failure this whole convention exists to prevent is a hand-rolled definition that later
reads, to someone who did not author it, as though it were the company's - so an honest
"authored here, unverified" is more valuable than a confident sentence, and it is what
tells the next reader which measures to check first.

## Worked example

```yaml
dashies: 1
title: Orders overview
intent: >-
  Metric definitions taken from the dbt semantic layer; no measure re-derived from raw tables.
source:
  connection: 7a1e0b2c-0000-4000-8000-000000000000   # from check_readiness
  schedule: daily
  timezone: America/New_York
datasets:
  main:
    sql: |
      select
        -- One row per order. No GROUP BY: the numbers are declared below and
        -- Dashies works them out. Bucketing the date is a per-row projection,
        -- not an aggregation, so it stays here. These comments sit INSIDE the
        -- statement rather than above it, because the first token has to be
        -- `select` or `with`: a leading comment is refused.
        date_trunc('month', o.placed_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/New_York')::date as month,
        o.region                                                                                  as region,
        -- Money divided here: the page's widgets draw revenue, and a widget is
        -- handed the raw value, so `scale: cents` is refused for a measure one draws.
        o.amount_cents / 100.0                                                                    as amount
      from analytics.fct_orders o
      -- Anchored to the data's own newest COMPLETE month, never to the wall clock. A
      -- mart ends behind today, so now() would shrink what the window holds every day,
      -- and the newest month is partial unless the data ends on a month boundary, so
      -- the second clause drops it and the chart below never shows a short final month.
      where o.placed_at >= date_trunc('month',
              (select max(o2.placed_at) from analytics.fct_orders o2)) - interval '18 months'
        and o.placed_at < date_trunc('month',
              (select max(o3.placed_at) from analytics.fct_orders o3))
    dimensions:
      month:  { type: date, label: Month }
      region: { type: category, domains: [AMER, EMEA, APAC], label: Region }
    measures:
      revenue:
        agg: sum
        column: amount
        unit: { kind: currency, scale: units, currency: USD, decimals: 0 }
        intent: >-
          dbt semantic layer, metric `revenue` (models/marts/metrics.yml). Definition taken from
          dbt, not re-derived.
      orders:
        agg: count
        unit: { kind: count }
      aov:
        ratio: { num: revenue, den: orders }
        label: Average order value
        unit: { kind: currency, scale: units, currency: USD }
look:
  html: |
    <!doctype html>
    <html lang="en">
    <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Orders overview</title>
    <style>
    /* The full token block (references/style.md), every value set to this page's style. */
    :root {
      --drt-blue: #0f766e;
      --drt-blue-700: #115e59;
      --drt-blue-soft: #f0fdfa;
      --drt-accent: #0f766e;
      --drt-on-blue: #fff;
      --drt-ink: #1c1917;
      --drt-muted: #57534e;
      --drt-subtle: #78716c;
      --drt-faint: #a8a29e;
      --drt-surface: #fff;
      --drt-sunken: #fafaf9;
      --drt-line: #e7e5e4;
      --drt-line-strong: #d6d3d1;
      --drt-grid: #f5f5f4;
      --drt-shadow: #1c1917;
      --drt-sans: system-ui, -apple-system, 'Segoe UI', sans-serif;
      --drt-mono: ui-monospace, 'SF Mono', Menlo, monospace;
      --drt-ease: ease;
      --drt-chevron: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 16 16' fill='none' stroke='%2378716c' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'><path d='M4 6l4 4 4-4'/></svg>");
      --drt-series0: #0f766e;
      --drt-series1: #b45309;
      --drt-series2: #4338ca;
      --drt-series3: #be185d;
      --drt-series4: #4d7c0f;
      --drt-warn-ink: #7c2d12;
      --drt-warn-soft: #fff7ed;
      --drt-warn-line: #fed7aa;
      --drt-error-ink: #991b1b;
      --drt-error-soft: #fef2f2;
      --drt-error-line: #fecaca;
      --drt-heat-1: #ccfbf1;
      --drt-heat-2: #99f6e4;
      --drt-heat-3: #5eead4;
      --drt-heat-4: #2dd4bf;
      --drt-heat-5: #14b8a6;
      --drt-heat-6: #0f766e;
      --drt-diverging-1: #b91c1c;
      --drt-diverging-2: #fca5a5;
      --drt-diverging-3: #fee2e2;
      --drt-diverging-4: #f5f5f4;
      --drt-diverging-5: #ccfbf1;
      --drt-diverging-6: #5eead4;
      --drt-diverging-7: #0f766e;
      --drt-status-ink: #44403c;
      --drt-status-soft: #f5f5f4;
      --drt-status-line: #d6d3d1;
      --drt-status-font: system-ui, -apple-system, 'Segoe UI', sans-serif;
    }
    body { margin: 0; background: #fafaf9; color: var(--drt-ink); font: 14px/1.45 var(--drt-sans); }
    .top { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 12px 24px; padding: 24px 24px 8px; }
    .top h1 { margin: 0; font-size: 24px; }
    .top .sub { margin: 0; flex: 1; color: var(--drt-subtle); }
    .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; padding: 16px 24px; }
    .card, .panel { background: var(--drt-surface); border: 1px solid var(--drt-line); border-radius: 8px; padding: 16px; }
    .card .label { display: block; font-size: 12px; color: var(--drt-subtle); }
    .card .value { display: block; margin-top: 4px; font: 600 28px/1.2 var(--drt-mono); font-variant-numeric: tabular-nums; }
    .panel { margin: 0 24px 16px; }
    .panel h2 { margin: 0 0 12px; font-size: 13px; font-weight: 600; color: var(--drt-subtle); }
    </style>
    </head>
    <body>
    <script type="application/json" id="dashies-data">{}</script>
    <header class="top">
      <h1>Orders overview</h1>
      <p class="sub">Updated <span data-dash="updated-at"></span></p>
      <div data-dash="filter" data-dim="region" data-label="Region"></div>
    </header>
    <section class="cards">
      <div class="card" data-dash="metric" data-measure="revenue">
        <span class="label">Revenue</span><span class="value" data-dash-value></span>
      </div>
      <div class="card" data-dash="metric" data-measure="orders">
        <span class="label">Orders</span><span class="value" data-dash-value></span>
      </div>
      <div class="card" data-dash="metric" data-num="revenue" data-den="orders" data-format="currency"
           data-decimals="2">
        <span class="label">Average order value</span><span class="value" data-dash-value></span>
      </div>
    </section>
    <section class="panel">
      <h2>Revenue by month</h2>
      <div data-dash="chart" data-type="line" data-x="month" data-measure="revenue"></div>
    </section>
    <section class="panel">
      <h2>By region</h2>
      <div data-dash="table" data-group="region" data-columns="revenue,orders" data-sort="revenue:desc"></div>
    </section>
    <script data-dashies-runtime></script>
    </body>
    </html>
```

**This example reads a WAREHOUSE, so its statement returns one row per order and declares how
each number is worked out.** `SKILL.md` Step 3 carries that rule. Two details are the rule in
practice: `revenue` names its `column` rather than relying on the key, and **`orders` is
declared `agg: count` and is exact, because the rows ARE the orders.** Written the other way -
grouped to `(month, region)` with `count(*) as orders` - that same measure would count the month
and region pairs.

**Two things in that statement are there to get past a guard, and both are worth copying.**

- **The money is divided in SQL and declared `scale: units`, because widgets draw it.** A widget
  is handed the raw value with no display divisor, so `scale: cents` is refused for a measure a
  widget draws. Dividing at the row, as here, is the move; the percent equivalent is
  `pct / 100.0` declared `scale: fraction`. **Do not reach for `kind: number` instead**: that
  publishes and throws the currency away, so the figure renders as a bare number rather than money.
  A measure only your page code draws may keep `scale: cents` - see the scale rules under the field
  table.
- **The comments sit inside the statement, under `select`.** The first token has to be `select`
  or `with`, so a statement that OPENS with `--` is refused before anything else is read.
  Comments anywhere after that first token are fine.

**A dataset on the sample connection groups to the grain it reports at instead**, and then every
field somebody filters on has to be in the `GROUP BY`. Same spec vocabulary, different statement.

**The page is one `look` body, and it is the same shape on every connection.** The `<style>` opens
with the full token block from `references/style.md`, every value set to this page's style, so every
widget takes it; the page's own rules come after it and are scoped to its own classes. The data block
comes first in the body and the runtime marker after the markup. Then the widgets
(`references/widgets.md`): a `filter` on `region`, whose menu lists the regions the data holds; three
`metric` cards, each putting its figure in a `data-dash-value` child so the card's label is yours, the
third dividing `revenue` by `orders` under every filter with `data-num` and `data-den`, since no widget
reads a `ratio` by its own key; a `line` chart over `month`; and a `table` rolled up by `region`,
largest revenue first. Each figure's format comes from its measure's `unit`, and the page's currency
and precision from `revenue`, the first currency measure declared: US dollars, no cents. So the widgets
carry no format attributes but one card's: a metric showing a ratio draws a percent unless told
otherwise, so the average-order card writes `data-format="currency"`, and `data-decimals="2"` gives
it cents. Nothing on the page is a number the page worked out, and a
picture no widget draws would be page code reading the same dataset, as in the example under **The
shape your script is handed**.

Note what is NOT in it: nothing about how the data will be prepared or where it will be kept.
The publish report says what the server chose for `main` and why.

## Row-level security

**Each viewer is served only the rows they were granted.** It is available on a workspace dashboard
on an Enterprise plan, reading a warehouse, and `check_readiness`'s `row_level_security` field is
what answers whether this space has it. **Ask the user about it once when that field says available,
and never raise it when it does not** - `SKILL.md` Step 1 carries that rule and it is the load
bearing half.

The filter is applied where the data is queried rather than in the page, on every widget and on every
number your page code asks for. So a dataset that declares an entitlement declares `mode:
resolved` beside it, and the page is handed the viewer's own rows, by its widgets and through
`dashies.data` alike, with nothing further to do.

A dataset-level `entitlement`:

| Field | Type | Required | Bounds and notes |
|---|---|---|---|
| `key` | string | yes | An output column of THIS dataset's `sql`, matching `^[a-z][a-z0-9_]{0,63}$`. Its value decides who may see the row. |
| `grants` | object | yes | Exactly one of `sql` or `list`. |
| `grants.sql` | string | one of | 8 to 100,000 characters. A read-only `SELECT` run on the same connection as this dataset's own SQL, returning EXACTLY TWO columns, identity first and key value second, read by POSITION rather than by name. One row per pair. A third column is refused at refresh; the two in the wrong order are not, and leave every viewer unmapped. |
| `grants.list` | array | one of | 1 to 500 entries of `{ identity, values }`. `identity` is 1 to 320 characters; `values` is 1 to 200 unique key values (string, number or boolean). |
| `hidden_values` | array | no | 1 to 200 unique key values hidden from everyone, the author included. **Write them as strings**: the schema admits numbers and booleans here and the refresh reader accepts only strings and `null`, so a number is a valid publish that stops the next refresh. `null` is how you say a NULL key is deliberate. |
| `grain` | string | no | `partition` or `row`. **Leave it out** and the server picks the layout from the key's measured cardinality and records what it chose. A declared `partition` is narrowed to `row`, and recorded as narrowed, wherever one folder per value would disclose those values through the object path. |

**An identity is one of exactly two forms, and the set is closed:**

| Form | Written as | Matched against |
|---|---|---|
| A person | an email address | the viewer's own signed-in email, case-insensitively |
| A Dashies team | `team:<team name>` | the teams that viewer belongs to, case-insensitively |

Both are matched as whole strings, there is no wildcard, and a viewer's value set is the UNION over
every grant that names them. **An empty union is not an error**: that viewer gets a designed page
saying they have no access to this dashboard's data, rather than an empty dashboard or an error. **An
admin the dashboard has exempted is never in this state**, because "granted nothing" is not a true
sentence about somebody the dashboard has exempted; they are served every row.

**A second designed page covers the state where the dashboard's own record says it filters and the
page being served carries no filter for any dataset**, and unlike the one above EVERY viewer gets
it: it says the dashboard is being set up to show each person their own rows, nothing is served
rather than everything, and it is cleared by publishing the dashboard again. A refresh does not
clear it, because a refresh does not rewrite that part of what is served. Its code is
`entitlement_awaiting_publish`, and it is a viewer state rather than a publish refusal, so it has no
row in the refusals table that closes this section.

The dashboard-level `entitlement` carries one field, `admins`, which is `filtered` or `unfiltered`.
**Absent means `filtered`**: row-level security applies to everyone including workspace admins, so
forgetting to write it cannot widen what anybody sees. **`unfiltered` is honoured, and it exempts
admins of the dashboard's own workspace and nobody else**: a creator who is not an admin, and every
ordinary member, stay filtered. The role is resolved from the workspace membership rather than from
anything the page can say, and what the document declares reaches a viewer only once the dashboard
has been published carrying it, because a refresh does not rewrite that part of what is served. A
workspace admin can also turn the exemption on or off for one dashboard from the app, which takes
effect without a publish and wins over what the document says. A dashboard-level block with no
dataset-level block is refused; it opts out of a filter that does not exist.

**A republish cannot stop the filtering by accident.** The block is read off the document being
published, so a full `spec` republish that omits it would leave every row served to every viewer,
and it is refused before anything is written, at the path `row_level_security_removed`. Stopping on
purpose is that key, written by hand at the top level as `row_level_security_removed: true`;
`derive_dashboard_spec` never emits it, so it is in a document only because an author put it there.
**Say what it does before writing it and let the user decide**: it stops the filter for EVERY
viewer, where the `admins: unfiltered` opt-out stops it only for workspace admins, so it is a change
to who can see the data rather than a way past a refusal. Declaring it beside an `entitlement`
block is refused, which keeps one declaration to one removal rather than letting it sit in the
document authorising the next. **The same refusal covers the case
where Dashies could not read whether the dashboard filters**, and both wordings name the removal
key, so the sentence is what tells them apart: on that one, publish again rather than declaring a
removal nobody has established is a removal. `spec_edits` meets none of this, because it leaves what
it does not name alone.

**Every key value in the extracted data must be granted to somebody or named in `hidden_values`.**
A refresh that finds one that is neither HOLDS BACK the dataset it is in: it publishes nothing for
that dataset, which keeps what it showed before, and Dashies emails the dashboard's author and every
admin of its workspace at once, naming the first few values plus a count of the rest, and how many rows
they account for; the complete list is on the run detail. There is no
override and no margin. Grant them or hide them, then refresh. A key whose values appear on their
own is an argument for `grants.sql` over an inline `list`.

**Cardinality is an advisory, never a refusal.** Pass `entitlement_key` to `validate_cube_sql` and
it reports when that column already holds more distinct values than the threshold at which Dashies
stops storing one folder per value and stores the rows sorted by the key instead. Both are correct;
the second is slower for one viewer's query. The count it reports is a lower bound over the sample,
and the real one is measured on the first refresh. **No number is written here**: the advisory
names the threshold when it fires, and a second copy of a constant is a copy that goes stale.

The refusals this block can raise, each returned with a `path` (`SKILL.md` Step 6). Where a path
appears on more than one row, read the sentence as well as the path:

| `path` | What it means |
|---|---|
| `/datasets/<name>/entitlement` | Row-level security is an Enterprise capability and this workspace is not on the Enterprise plan. |
| `/datasets/<name>/entitlement` | The dataset declares another `mode`, or none. Write `mode: resolved`. |
| `entitlement` | The same Enterprise refusal, where the only block is the dashboard-level one. It is checked first, so it is what a root-only block on a space without the capability reports. |
| `entitlement` | A dashboard-level block with no dataset-level one. |
| `row_level_security_removed` | This dashboard filters its rows per viewer today and the document declares no `entitlement` block. Restoring the block keeps the filter and needs nobody's permission; declaring the removal stops it for EVERY viewer, so say what it does and let the user decide. |
| `row_level_security_removed` | Dashies could not read whether the dashboard filters, so the publish is refused rather than admitted. Publish again; do not declare the removal to get past it. |
| `row_level_security_removed` | The document declares an `entitlement` block AND the removal, which cannot both be true of one dashboard. Delete one of them. |

## The page: `look`

**Every dashboard's page is one body you write, and it is part of the spec**: the pointed refusals,
the seeding, the correctness checks and the schedule all still apply, and the data still never enters
your context. **`SKILL.md` Step 4 carries the decisions - the style question, and the two rules that
govern every script on the page. This section is the mechanics.** Three kinds of thing go in it: your
markup and CSS (`references/style.md` restyles what the runtime draws), the widgets the runtime draws
(`references/widgets.md`), and your page code.

**Your page code is handed its numbers; it never reads them out of the page and never asks a server
for them.** Two calls, on every connection: `dashies.data` subscribes, and `dashies.filter` sets a
page filter. The shape and the example are
under **The shape your script is handed** below, and the two calls' full surface under **Filters
and a coarser grain**. The publish report's `Datasets:` sentence and its one-per-dataset
"publishes with NO data" note say whether a dataset publishes empty and fills in after a refresh -
which your script sees as `status: "pending"` - and they no longer decide whether your page can work.
A republish whose `First data:` line says `unchanged` has no such wait and prints no such note.

### `look` - the page body

A top-level key, and every spec carries it. Exactly one of:

| Key | Notes |
|---|---|
| `html` | Your page body, emitted byte for byte. **Three ceilings, and they are NOT one rule** - see "How big your body may be" below. |
| `from` | A slug, which must EQUAL the slug you are publishing to. Means "keep the body this dashboard already has": the server reads it from storage and re-seeds it, so zero pixels change. To reuse a DIFFERENT dashboard's body, `get_dashboard` it and inline `html`. |

#### How big your body may be

Three separate ceilings, each driven by a different thing, so no single condition covers them.
**Two of them you can work out; the third you cannot on the sample connection, and that is the one
to plan around.**

| Ceiling | What it bounds | What pushes you into it |
|---|---|---|
| 4,194,304 CHARACTERS | your `html` alone | the markup you wrote |
| 5 MiB | the whole spec DOCUMENT you send, in BYTES, refused before it is even parsed | **how your body is written down, not how long it is.** Two things inflate the document past your character count: the indentation YAML puts on every line of a block scalar, and any character that is more than one byte. It leads whenever your document runs over **1.25 bytes per body character**, which is `5,242,880 / 4,194,304` |
| 5 MiB | the COMPILED page: your body PLUS the data block seeded into it | **your DATA, not your markup.** It rises with the rows your statements return, and it can bring the total over the line while your body is comfortably under its own cap. On a dashboard that reads a warehouse the block carries no rows, so this ceiling is your body alone |

**Measured, so the third row is not a theoretical worry:** one ordinary dataset of 20,000 rows
seeded a data block of 958,688 bytes, and the compiled page is your body plus that block. A body
near its character cap plus a block that size lands about 89,890 bytes under the compiled ceiling,
and a slightly larger dataset crosses it - **while the body is still inside its own cap**, which
is why these are three ceilings and not one.

**And the second row's overhead is per LINE, which is easy to underestimate.** Written as a YAML
block scalar, every line of your body carries four extra bytes into the document, so SHORT lines
cost proportionally more. Measured, in bytes of document per character of body: **1.049** at 80
characters a line, **1.098** at 40, **1.235** at 16, **1.308** at 12.

**The last one is over the 1.25 crossover, and that has a concrete consequence:** a body sitting
exactly ON its 4,194,304-character cap, entirely legal by row 1, compiles into a document of about
5,485,000 bytes and is refused before it is ever parsed. Deeply indented markup gets there on line
length alone, and multibyte content gets there sooner.

**On the sample connection you cannot compute the third one in advance, and you do not have
to.** The publish report carries a `Bytes:` line giving the page and the data separately, so
dry-run and read it. If the page is over, the two levers are a smaller body or a coarser grain,
and the grain is usually the one with room in it. On a warehouse dashboard the block carries no
rows, so the body is the only lever there and the ceiling is one you can work out after all.

**Do not stop reading at that line.** It sits after the per-dataset block and BEFORE the
`warning:` lines, so an author who treats it as the end of the report misses the warning that says
the page publishes empty until its first refresh, and the one that says the runtime marker is
missing.

**The contract between your page and refresh is two elements.** The first is the data block, and
a `look` body is refused unless it satisfies it:

```html
<script type="application/json" id="dashies-data">{ ... }</script>
```

- **Exactly one.** Zero is refused, because there is nothing to refresh into. Two or more is
  refused, because every reader takes the FIRST match, so the second would silently shadow the
  real one.
- It must be a complete element; an opening tag with no `</script>` is refused.
- **Put it above any script that calls `dashies.data`.** A script that runs before the block runs
  before `dashies` exists, and a page like that renders its static markup and nothing else.
- Publish seeds it, and every refresh rewrites only what sits between the tags. **Every other
  byte of your page is left alone** - your `<head>`, your CSS, your own scripts, your markup, all
  emitted exactly as you sent them. That is why your design survives a refresh, and it is also why
  nothing is added to your page that you did not write: **a `look` body gains no runtime marker of
  its own**, which is why the second element below is yours to place.
- **`dashies-data` is a RESERVED id.** Do not put it on anything else anywhere in your page. It is
  refused, because a decoy is either read instead of the real block or rewritten by the refresh
  instead of it, and the second one freezes the numbers silently.

**The second element is the runtime marker, and every `look` body carries it:**

```html
<script data-dashies-runtime></script>
```

It is what calls the function you hand `dashies.data`, and what draws every widget; without it
neither happens, on any connection. On a warehouse dashboard a `look` body without it gets a warning
on the report whatever the body calls, because nothing else can put numbers on it; on the sample
connection the warning comes only when the body calls `dashies.data`. (A page that read the data
block directly used to work there without it; publish now refuses a script that looks the data block
up, under **Reading the data block directly** below.) A body that carries widgets without it is
refused on either, since those would ship frozen.

**Two ways to get numbers onto the page, and a page uses either or both:**

- **Widgets** - elements carrying `data-dash`, which the runtime draws (`references/widgets.md`).
  Every name a widget uses must resolve against your declared datasets, checked at publish, and a
  page with widgets and no marker is refused rather than shipped with frozen numbers. Reach for one
  first wherever one draws what you need.
- **Page code** - a `<script>` that hands `dashies.data` a function and draws what it is called with,
  for a picture no widget draws. The recipes in `references/charts.md` are a starting point.

### Assets - images the server fetches for you

A logo or a mark never reaches the page as bytes you typed. Declare it once, at the top level of
the spec, by URL, and reference it by name from your page:

```yaml
assets:
  logo:
    url: https://www.example.com/brand/logo.svg
  mark_dark:
    url: https://www.example.com/brand/mark-dark.png
```

| Key | Type | Notes |
|---|---|---|
| `url` | https URL (<=2048) | Required. Fetched by the server on every dry run and publish: https only, port 443, no credentials in the URL, at most 5 redirects, and every hop checked against the same outbound host policy a warehouse connection passes (no private or reserved address, none of Dashies' own hosts). |
| `sha256` | 64 hex chars | **Written by the server, never by you.** The pin of what was fetched, recorded into the stored spec on publish and read back on the next one. Delete the line to take a file the URL has since changed. |
| `intent` | string (<=1000) | Optional note, as elsewhere. |

**Reference syntax:** `src="asset:logo"` on any element of your page, and `url(asset:logo)` in its
CSS. Both are rewritten to the fetched bytes when the page is built, so the stored page is
self-contained and nothing loads from outside at view time. A reference to a name you did not declare
is refused, naming the byte; a declared asset nothing references is a warning.

**What is checked, per asset:** the bytes are an SVG, PNG, JPEG, WebP or GIF by their content -
not the URL's extension nor the origin's header, so a `.svg` URL serving a PNG is inlined as a
PNG and reported as one; an SVG is read through and refused if it carries a `<script>`, a
`<foreignObject>`, an event attribute, or any external reference (`href`, `xlink:href`, a `url()`
or `@import` in its styles), because the page must stay self-contained; one asset is at most
512 KiB and all of them together at most 2 MiB - a mark, not a banner - and a spec declares at
most 8.

**The report's `Assets:` block** carries one line per asset: the URL that answered, the content
type, the byte size, the sha256, and whether it was pinned, unchanged, kept or re-pinned. On a
later publish, if the URL stops answering, the stored copy of the pinned bytes carries the page
and the report says so - only when that copy is the recorded file; a copy that is not is refused
rather than used; if the URL now serves different bytes, the pinned ones are kept and the report
says how to take the new file. A scheduled refresh never touches an asset: it rewrites the data
block and nothing else.

**A `look: { from }` republish keeps the stored page byte for byte**, so an asset whose bytes
would change - a URL that now serves a different file, a `sha256` line deleted to take one, an
asset declared for the first time - is refused at `/assets/<name>`: the new bytes could reach
nothing on a page that was built without them. Send the body with `look: { html }` to change a
logo; an asset whose bytes are unchanged, or whose stored copy carries the page while its URL is
down, is fine under `from`.

**A light and a dark mark are two assets**, each referenced under its own `prefers-color-scheme`
rule.

**A hand-typed `data:image/...;base64,` URI still publishes, and every one is decoded and
checked**: base64 that does not decode, bytes that are not the declared type, or an SVG that does
not parse is a warning naming the byte offset and pointing here. A URI that passes is not thereby
correct - the corruption that was measured decoded cleanly into well-formed markup with an
invented path - which is why the rule is to declare rather than to type.

### The shape your script is handed

`dashies.data` takes a function, and an optional options object, and calls the function with the
datasets THIS CALL ASKED FOR, keyed by name. Your page may read every dataset the spec declares,
and the options object is how a call asks for less: name any dataset and you are handed those and no
others. It calls it again whenever any of the state it asked for changes, so a filter change
reaches your page as `ready`, then `loading`, then `ready` - whether a filter widget, a shared
link or your own `dashies.filter` call caused it. On a warehouse dashboard the numbers are worked
out by Dashies when someone opens the page; on the sample connection they travel inside it; your
function is handed the same shape either way.

```js
dashies.data(function (datasets, page) { /* draw */ }, { main: { by: ['month'] } });
```

The options object is keyed by dataset name, and each entry carries up to six keys: `by`, a
subset of that dataset's declared dimension keys, and `unfiltered`, declared dimensions whose page
filter that subscription is answered without (see "Filters and a coarser grain"); and `sort`,
`limit`, `having` and `other`, which ask for the members in an order, cut, restricted by a
condition, with the rest as one row (see "An order, a top N and a threshold"). **Naming a dataset is how you ask for it.** With no
options, or `{}`, you are handed every dataset your markup may read, each at its declared grain;
name any dataset and the call asks for exactly the datasets it names, each at its `by` or, where
that entry has no `by`, at its declared grain. **A dataset you leave out of an options object that
names others is not fetched at all, and reading it in that callback throws a `TypeError` naming the
dataset and the fix** - never a quietly different answer. The function's own second argument,
`page`, carries one field, `filters`: the page's whole filter state, over every dimension any
dataset on the page declares.

Each dataset is an object carrying these twelve fields and no others:

| Key | Value |
|---|---|
| `status` | `"pending"`, `"loading"`, `"ready"` or `"error"` (below). |
| `rows` | When `ready`, an array of row objects, one per combination of the dimensions in `grain`, each carrying every declared measure, worked out under the filters in `filters`. **`null` in the other three states, never an empty array.** A measure is a number when a float64 holds it exactly and otherwise its exact digits as a string, `null` where the cell has no value; draw it as text, see the example's closing note. A `min` or `max` over a date is TEXT: `YYYY-MM-DD` for a DATE, `YYYY-MM-DDTHH:MM:SS.sssZ` (ISO 8601, UTC) for a TIMESTAMP. **Their order:** every grain arrives sorted over the dimensions in `grain` order - on each, the members a `domains` declaration lists come first, in your order, then every other value ascending (a number column by value, text character by character), then `null` - so draw the rows in the order they arrive. One exception: on a dataset whose rows are kept outside the page, a grain over a column whose type Dashies could not tell at publish (every value it sampled there was empty) arrives in the order Dashies answered it, ascending over its dimensions in alphabetical order and without your `domains` order. **Asked with `sort`, the rows arrive in that order instead, cut to any `limit`, and each carries `__rank_pos`, its place from 1.** |
| `truncated` | `true` when `rows` is not the whole answer. |
| `dimensions` | `[{ key, label?, type?, domains? }]` - every DECLARED dimension: `label` where you set one, `type` present only when it is `date`, and `domains` exactly as you declared it on a category dimension that has one. |
| `measures` | `[{ key, agg, format?, scale?, currency?, decimals? }]` for an agg measure, then `{ key, ratio: { num, den, num_scope?, den_scope? }, label?, format?, scale?, currency?, decimals? }` for each `ratio` measure - `format` rides on an agg entry when a `unit` was declared, and on a ratio entry it is always present (the declared unit's format, else `percent`); `scale` rides beside it where the declared scale divides for display, and `currency` and `decimals` where the unit declares them. An entry is what you hand `dashies.format(value, measure)`, which applies all four. A ratio's value is on each row under its key, worked out by the runtime; see "How your script gets its numbers" in `SKILL.md`. |
| `as_of` | When this dataset was last computed. |
| `error` | `null` unless `status` is `"error"`, and then the reason, in words. |
| `error_kind` | `null` unless `status` is `"error"`, and then `"refused"` - the service declined this question, so change the question - or `"failed"` - everything else, including the service accepting the question and breaking, where a narrower question fails the same way. |
| `grain` | The dimension keys `rows` are grouped by, in declared order: the declared keys, or the `by` you asked for. Zip it against a row to read its group. |
| `filters` | The page filters that APPLIED to this dataset, over the dimensions it declares and less any dimension this subscription names in `unfiltered`: a string for one value, an array of strings for a set, `{ from, to }` for a range. A dimension with no filter is ABSENT, never `null`, so `'region' in ds.filters` reads "this number is filtered by region". |
| `members` | When `ready`, how many members the grain has under the filters and any `having`, BEFORE a `limit` cut them - the "of 12,000" beside a top ten, counted by Dashies. Equal to `rows.length` wherever nothing was cut. `null` in the other three states. Draw it with `dashies.format(ds.members, ds)`, which puts in the page's separators: with the dataset in place of a measure entry, `dashies.format` formats that dataset's `members` and nothing else. |
| `other` | When the subscription asked `other: true` and a `limit` left members out, those members as ONE row: every declared measure and ratio, worked out exactly over their rows. It carries no dimension value, and reading one throws, so label it yourself. `null` otherwise. |

**The four states, and what the page says in each:**

- **`pending`** - no answer yet, and nothing failed. A dataset is here while Dashies is still
  extracting it, or re-extracting it, on a dashboard that already has data: the runtime asks
  again on its own, on a growing interval, so the page recovers with no reload. A dashboard that
  has never refreshed at all is here on every dataset, and a page opened before its first refresh
  lands does not fill itself in - it is reloaded once the numbers are there, which is why
  `SKILL.md` Step 7 has you stay until they are. Say "no data yet". Do not spin, and do not draw
  an error.
- **`loading`** - being worked out, including after a filter change. Say so; do not leave the
  previous numbers up as current. The runtime draws its own loading indication over your page by
  default, and reading this state is how you draw one on your own numbers.
- **`ready`** - draw `rows`.
- **`error`** - draw `error`. One case to recognise: an answer refused because the grain you draw
  is too wide, which arrives with `error_kind: "refused"`. It is refused on the subscriptions at
  that grain only: your other subscriptions on the same dataset still receive their rows, and the
  widgets on that dataset stop. The remedy is to subscribe at the grain you draw with `by` so
  the wide one is never requested, to bound the dataset's dimensions, or to declare fewer of them:
  the width is what was requested, never which columns you draw.

**Want a different grain? Ask for it with `by`.** `rows` are grouped by exactly what you asked for,
by the same machinery that answers a chart widget; adding rows up in the page to reach a coarser
grain is rule 1 broken, and nothing will ever check the number it produces. Declaring a second
dataset over the same records at the coarser grain is the same mistake at publish time: it extracts
and stores a second copy of those records to precompute rows the runtime produces on demand.
**Filters and a coarser grain**, below, carries the whole surface.

**The example. It handles every state, sums nothing, asks for nothing, shows the order the three
elements go in, and reads the dataset from the worked example above - declared month by region -
as a month series with a region control:**

```html
<script type="application/json" id="dashies-data">{}</script>
<section id="orders">
  <h2>Orders by month <span class="scope"></span></h2>
  <label>Region
    <select class="region">
      <option value="">All regions</option>
      <option>AMER</option><option>EMEA</option><option>APAC</option>
    </select>
  </label>
  <p class="state" hidden></p>
  <table>
    <thead><tr><th>Month</th><th class="num">Orders</th></tr></thead>
    <tbody></tbody>
  </table>
  <p class="cut" hidden>Showing part of the answer.</p>
</section>
<script data-dashies-runtime></script>
<script>
var root = document.getElementById('orders');
var select = root.querySelector('.region');
select.addEventListener('change', function () {
  // Set the page filter; the runtime fetches again and calls the function below again.
  dashies.filter('region', select.value === '' ? null : select.value);
});

dashies.data(function (datasets, page) {
  var ds = datasets.main;
  var state = root.querySelector('.state');
  var body = root.querySelector('tbody');
  var cut = root.querySelector('.cut');
  var scope = root.querySelector('.scope');

  // The control reads the PAGE state, so it is right after a reload from a shared link.
  var region = typeof page.filters.region === 'string' ? page.filters.region : '';
  if (select.value !== region) select.value = region;
  // The label reads what reached THIS dataset, so it cannot claim a filter that did not apply.
  scope.textContent = 'region' in ds.filters
    ? '(' + [].concat(ds.filters.region).join(', ') + ')'
    : '(all regions)';

  body.innerHTML = '';
  if (ds.status !== 'ready') {
    // pending, loading or error: rows is null, so there is nothing to draw and nothing to add up
    state.textContent = ds.status === 'pending' ? 'No data yet. It fills in after the first refresh.'
                      : ds.status === 'loading' ? 'Updating...'
                      : 'Could not load: ' + ds.error;
    state.hidden = false;
    cut.hidden = true;
    return;
  }

  state.hidden = true;
  cut.hidden = !ds.truncated;
  // The measure's entry, which carries its format; dashies.format draws a null as "-".
  var orders = ds.measures.find(function (me) { return me.key === 'orders'; });
  ds.rows.forEach(function (row) {
    var tr = document.createElement('tr');
    [row.month, dashies.format(row.orders, orders)].forEach(function (text, i) {
      var td = document.createElement('td');
      if (i === 1) td.className = 'num';
      td.textContent = text;
      tr.appendChild(td);
    });
    body.appendChild(tr);
  });
}, { main: { by: ['month'] } });   // one row per month; the regions are rolled up FOR you
</script>
```

Everything load-bearing in it, in order. **The data block comes first**, above the script that calls
`dashies.data`; publish fills it in, so `{}` is all you write. **The marker is there**, so the
function is called at all. **The month series is asked for with `by`**, so the runtime hands over
one row per month and the page adds nothing up across regions. **The control sets the filter and
reads it back from `page.filters`**, so a shared link opens on the view it names and the select
agrees with it; its options are the dimension's declared `domains`, written into the markup. A
subscription at `by: ['region']` alone would itself be filtered once a region is chosen, and the
menu would collapse to that one value; to draw the menu from the data instead, subscribe
`{ main: { by: ['region'], unfiltered: ['region'] } }`, which is answered without the region filter
and so keeps every region while one is chosen. **The label reads `ds.filters`**, so it can never
claim a filter that did not reach the number. **Every branch other than `ready` writes a sentence to the page and
draws nothing**, so a viewer never sees a number that is not the current answer. **Nothing is added
up**: `orders` is drawn as it arrived, through `dashies.format(row.orders, orders)`, with `orders`
the `orders` entry on `ds.measures`, which applies the measure's format and renders `null` as `-`
rather than 0. A measure arrives as a number when a float64 holds it exactly and otherwise as its
exact digits in a string, and `dashies.format` draws those digits as they are, so a value like
`"1234567890123456789"` is deliberate rather than a bug. `String()` and `toLocaleString()` are not
the recipe, and publish refuses both: `String()` shows a measure without its format, scale or
currency, and `toLocaleString()` rounds a decimal for display and throws on `null`, and a throw
inside the callback blanks the whole region. Never put a measure into arithmetic with a literal,
which is rule 1 broken whatever its type.

### Filters and a coarser grain

Two things page code does through the same machinery that answers the filter widget and the chart
widget. Neither adds a request your spec could not
already cause: a filter names a declared dimension and a value, and `by` names a subset of
declared dimensions. There is still no way to name a measure, a dataset or a query the spec did
not declare. `unfiltered` (below) adds none either: it asks at a state the page could reach by
clearing those filters.

```js
// A coarser grain, per dataset, on the subscription. [] is the grand total.
dashies.data(function (datasets, page) { /* ... */ }, { main: { by: ['month'] } });

// Every region, whatever region the page has chosen: the members a filter menu draws.
dashies.data(function (datasets, page) { /* ... */ }, { main: { by: ['region'], unfiltered: ['region'] } });

// The page filter on a declared dimension. Returns nothing; the runtime fetches again and
// calls every subscriber again.
dashies.filter('region', 'EMEA');                                   // exactly this value
dashies.filter('region', ['EMEA', 'APAC']);                         // any of these
dashies.filter('month', { from: '2026-01-01', to: '2026-06-30' });  // inclusive; date dimensions only
dashies.filter('region', null);                                     // clear
dashies.filter({ region: 'EMEA', channel: null });                  // several at once, one re-render
```

**`by`.** A subset of that dataset's declared dimension keys, in any order; `grain` comes back in
declared order, with duplicates removed, so a page can zip it against a row. An entry with no `by`
still asks for that dataset, at its declared grain. `rows` are one per
combination of those keys, every measure worked out at that grain: on a warehouse dashboard by the
query service, on the sample connection composed from what the page holds under each measure's
declared aggregate, and refused - `status: "error"` naming the measure - where that cannot be
exact. One subscription carries one grain per dataset. A page that wants two grains of one dataset
subscribes twice; a page that wants two aggregates of one column declares two measures, because
`by` carries every declared measure at its declared aggregate and no subset. A `by` naming a
dimension the dataset does not declare is `status: "error"` on that dataset for that subscription,
for good, naming the declared dimensions; there is no silent fall-back to the declared grain,
because a wrong-shaped answer drawn as a right one is the failure this surface exists to remove.

**`unfiltered`.** Declared dimensions of that dataset whose page filter this subscription is
answered without; every other page filter still applies, and any declared dimension may be named,
whether or not it is in `by`. It is what a menu of a dimension's members needs: subscribed at
`by: ['region']` alone, the rows collapse to the chosen region, while `unfiltered: ['region']`
keeps every region, on a shared link that opens filtered as much as after a click. That
subscription's `filters` leaves the named dimensions out, so `'region' in ds.filters` stays true
exactly when the region filter reached its rows; `page.filters` is the page's state either way. It
can never show a viewer rows they may not see: it removes only filters the page set. A key the
dataset does not declare is refused exactly as a bad `by` is.

**`dashies.filter`.** One dimension and a value, or one object of several, which applies all of
them or none. A value is a string, an array of strings, `{ from, to }` on a `date` dimension, or
`null` to clear. It sets the same state the filter widget sets, and **the URL hash carries
the page's WHOLE filter state whenever that state differs from the page's default view; the page
rewrites it to a bare URL as soon as the state returns to that default.** So the hash is
all-or-nothing rather than per dimension: once anything differs, every dimension travels in the
link, including the ones sitting at your default. A call your script makes before the viewer has
touched anything is what DECLARES that default, so it moves the yardstick rather than navigating
away from it; a call made after that is written to the hash exactly as a control's would be. And a
BARE link is not an unfiltered one: it runs your script again, so your defaults apply to it.
Setting a value equal to the current one does nothing. A call naming a dimension no dataset on the
page declares, a range on a dimension that is not a `date`, a set larger than a shared link can
carry (the refusal names the cap), or a single `date` value containing `..` throws a `TypeError` at
the call site once the page has booted, and changes nothing. The same call made in your script's
own top-level run, before the runtime has booted, is queued and applied at boot. Every call queued
that way is merged into ONE call, last writer per dimension, and applied under the same all-or-none
rule - so one bad key among them drops every queued filter, with one error on the console and no
throw.

**An initial view is therefore ONE UNCONDITIONAL call at the top of your script, checked twice as
carefully. Do not guard it on `location.hash`.** A call queued that way fills only the dimensions
the URL hash did not carry, so a shared link's own filters win on every dimension it names and your
defaults land on every dimension it leaves out.

**Only a call QUEUED BEFORE BOOT is read that way.** A call made after boot overrides the hash on
every dimension it names, exactly as it always did, and **a call from inside a `dashies.data`
callback is one**, because it runs on the first delivery. If your default can only be computed from
the numbers, so it has to live in that callback, guard it on `page.filters` - `if
(!page.filters.region) ...` - so it fills the dimension without overwriting a shared link that
already named it.

**One residual, worth knowing before you give a dimension a default.** A viewer who CLEARS that
dimension and shares the link gets your default back when somebody opens it. A cleared dimension
simply has no entry in the hash, so the link cannot say "no filter here" as distinct from "nothing
to say about this one", and your call fills it again.

**A filter change fetches every dataset THIS CALL ASKED FOR again, including one that does not
declare the dimension.** On a warehouse dashboard that dataset goes `loading` then `ready` with the
rows it had, and its `filters` does not carry the dimension - which is how a page labels a number honestly: read
`'region' in ds.filters` to say "filtered by region", and its absence to say the filter did not
reach this number. Do not remember what you asked for and label from that: a shared link changes the
state without going through your call, and so does a filter widget.

**`page.filters` is for drawing controls.** It carries the whole page state on every delivery, so
a control drawn inside the callback is right after a reload from a shared link and after every
change from anywhere. There is no synchronous read of the filter state: before boot it could only
lie, and after boot the callback already has it.

**Never duplicate records to precompute a rollup or a filter state.** `SKILL.md` carries the
measured instance under "How your script gets its numbers". A rollup is `by`; a filter state is
`dashies.filter`; a sentinel value per filter state and a dataset per grain are the same mistake
in two shapes, and both are paid at extraction as well as at view time.

### An order, a top N and a threshold

A page may not sort, slice or filter its rows by a number, so it asks Dashies for them on the same
subscription, and Dashies ranks the members the way the query service ranks them: on a warehouse
dashboard the service answers the question itself, and on the sample connection the page ranks the
rows it holds by the same rules.

```js
// The ten largest customers by revenue, the rest as one row, and how many there were.
dashies.data(function (datasets) {
  var ds = datasets.sales;
  if (ds.status !== 'ready') return;
  ds.rows;      // ten rows, the top one first, each with __rank_pos 1 to 10
  ds.members;   // 12000
  'of ' + dashies.format(ds.members, ds);   // 'of 12,000', in the page's own separators
  ds.other;     // { revenue: ..., orders: ..., aov: ... } for the other 11,990, or null
}, { sales: { by: ['customer'], sort: 'revenue:desc', limit: 10, other: true } });

// The countries whose average order is over 500, largest first.
dashies.data(function (datasets) { /* ... */ },
  { sales: { by: ['country'], sort: 'revenue:desc', having: [{ key: 'aov', op: '>', value: 500 }] } });
```

**`sort`.** `'<key>:asc'` or `'<key>:desc'`, and the direction is required. The key is a declared
measure, a declared `ratio`, or a dimension in the grain (`by`, or the declared grain), ordered by
its value - a `domains` list does not order a sort. A member with no value comes last in both
directions, and a tie is broken by every dimension of the grain you did not sort on, ascending, in
key order - on a top N over one dimension, the member's own value - so the order is the same on
every load. Each row then carries `__rank_pos`, its place from 1: a numbered list reads it, since a
count the page works out itself (`i + 1`) is refused at publish, and a page highlights the top item
with `r.__rank_pos === 1` or reads it as `rows[0]`. A grain asked without `sort` carries no
`__rank_pos` and arrives in its member order.

**`limit`.** A whole number from 1 to 10,000, and only beside `sort`: it keeps the first members of
that order. `members` says how many there were before the cut. On a warehouse dashboard, without a
`limit`, a grain whose members pass the 10,000 one answer holds reads `status: "error"`,
`error_kind: "refused"`, naming `limit`, rather than a first 10,000 drawn as the whole.

**`having`.** A list of conditions a member must ALL meet, checked before it is ordered, counted or
cut: `{ key, op, value }` with `key` a declared measure or `ratio`, `op` one of `>`, `>=`, `<`, `<=`,
`=` and `!=`, and `value` a number. A member with no value meets none, `!=` included. A condition on
a dimension is refused: to keep rows by a category value, pick them by name in your script
(`rows.filter(function (r) { return r.plan === 'pro'; })`), or set the page filter with
`dashies.filter`.

**`value` is in the unit the row carries, not the one the page shows.** It is compared BEFORE a
declared `scale`: on a measure declared `scale: cents`, a $500 threshold is `50000`; a percent
compares as its rows hold it, `0.25` for 25% under `scale: fraction` and `25` under `scale: points`;
a `ratio` compares its quotient, so one the page shows as 25% is `0.25`. Writing the figure the page
shows gives a threshold 100x off, and nothing can tell you so.

**A measure that is a date or a time** - a `min` or `max` over a date column - may be a `sort`:
`sort: 'last_order:desc'` puts the latest first. A condition on one is refused, since a condition
compares a number, and so is a `sort` or a condition on a `ratio` over one. To keep the members
with a row in a range of days, narrow the page with `dashies.filter` on a date dimension.

**`other`.** `true` beside a `limit`: `ds.other` is then every member past the cut as one row, each
measure and ratio worked out exactly over their rows - a distinct count included - so an "Other" bar
or slice is Dashies' number, not a sum the page made. It is `null` when nothing fell past the cut.
One case is refused rather than guessed: a sample-connection dataset that holds only pre-added
cells cannot gather a measure that does not add up across members, such as a distinct count, into
one row.

**What is refused**, each as `status: "error"` on that dataset for that subscription, naming the fix,
while the page's other subscriptions keep their rows: a key the dataset does not declare, a `sort`
with no direction, a dimension outside the grain, a `limit` with no `sort` or outside 1 to 10,000,
`other` with no `limit`, a condition on a dimension or with an operator outside the six, a condition
value that is not a number, any of the four on `by: []`, a `ratio` whose `num_scope` or
`den_scope` is `all` - a share of the total ranks exactly as its other operand does, and the
refusal names that operand - a condition on a measure that is a date or a time and a `sort` or
condition on a `ratio` over one, `other` over a measure that does not add up where the dataset holds
only pre-added cells, and, where the page ranks the rows it holds, a ranking by a measure whose
value has more digits than the page holds exactly.

### Reading the data block directly

**Page script never reads `<script id="dashies-data">` itself, or any script element's text, and
publish refuses a script that looks one up** (`page_script_escape`): the data block by its id,
`document.scripts`, `getElementsByTagName('script')`, or a selector naming a script. Page script
takes its numbers from `dashies.data(callback)` and nowhere else, because that is the one surface Dashies can check: publish reads what a script does with what
`dashies.data` hands it (rule 1 in `SKILL.md`), and a script that parses the data block for itself
reaches the same numbers around that reading. A page published before `dashies.data` existed keeps
rendering as it is; republishing it, `look: { from }` included, means moving its script onto
`dashies.data` first. On a warehouse dashboard the data block holds no rows to read anyway: they
are worked out when someone opens the page and handed to your callback.

## Migrating a dashboard that has no spec

A dashboard published before specs existed has nothing for `get_dashboard_spec` to read.
`derive_dashboard_spec({ slug })` reconstructs a draft from what that dashboard already carries,
read-only, storing nothing. The draft references the dashboard's CURRENT published page with
`look: { from: <slug> }` rather than inlining it, so the tool response and the eventual stored
spec both stay small; republishing resolves that page from storage and re-runs every dataset
live, so the page stays byte for byte while the numbers update, and every later edit is a spec edit.

**If the draft also carries a ready-to-paste block meant to replace its `look`, leave it out and keep
`look: { from: <slug> }`.**

## What a publish WARNING means

Errors block; warnings do not. A warning on the publish report is the server telling you it
seeded the dashboard, looked at the REAL values that came back, or read your page, and found
something that will read wrong at view time. Read them - they are the cheapest signal you will get.
**A widget's own rules are not among them**: publish does not draw the page, so a widget that cannot
draw what it was asked for says why in its own place when the page is viewed
(`references/widgets.md`, "What publish checks, and what waits until the page draws").

| warning | what it found | what to do |
|---|---|---|
| `domain_drift_at_publish` | a seeded value is outside the dimension's declared `domains` | add it to `domains`, or narrow the SQL. Widgets list it after the declared members, but the publish sized the dataset from the declared members alone, so it is larger than it was checked at |
| `null_leading_dimension` | a declared dimension is NULL across the whole leading head of the dataset | a null dimension cell renders as a blank label, so a table leads with unlabelled rows. The warning names the column and how many of the dataset's rows carry the null, so you can tell a handful to label from a broken join. Label it in SQL (`coalesce(...)` to an explicit value) if the null is meaningful, or filter it out if it is not |
| `percent_points_suspect` | a `percent`/`fraction` measure seeded values that look like 0..100 | declare `scale: points`, and page code is handed the value with `scale: 100` beside it. A widget is handed the raw value, so for a measure a widget draws, divide by 100.0 in the SQL and keep `scale: fraction` instead (the scale rules under the field table) |
| `rate_shaped_sum` | a `sum` measure seeded values all between 0 and 1 | summing rates is usually wrong - declare a ratio, or sum the underlying counts |
| `sum_over_stock` | the SQL sums a measure declared `stock: true` across the grain | for the level, read the latest period or use `max`; for a trend, a per-period `avg`, `min` or `max`. If the rows really do not overlap, ignore it (`stock`, under the measure fields) |
| `date_dim_not_iso` | a `date` dimension seeded values that are not ISO | bucket to `YYYY`, `YYYY-MM` or `YYYY-MM-DD` in SQL |
| `col_extra` | the query outputs a column nothing declared reads, so it reaches every viewer and is read by nothing | drop it from the `select`, or declare it. (An undeclared column that would ship real data is an ERROR, not this warning) |
| `look.html has no way to read its data` | the page neither calls `dashies.data` nor carries a widget, so every number on it is one you typed | read the data with `dashies.data(callback)` after the runtime marker, or put a widget on the page |
| `multi_series_controls` | a chart with several series (`data-measures` or `data-series`) carries `data-controls` | remove `data-controls`: such a chart draws no sort or limit controls. Chart a single measure if the reader needs to reorder it |
| `page_network_call` | your page code calls the network (`fetch`, `XMLHttpRequest`, `WebSocket` and the like) | remove the call: a published dashboard reaches only Dashies, so it fails in the viewer's browser (`SKILL.md` rule 2). Numbers come from `dashies.data`, a logo from `assets`, a font from a `data:` URI |
| `publishes with NO data` | the dataset's rows are kept OUTSIDE the page, so it publishes empty: its widgets read "Updating" and your page code is handed `status: "pending"`. The report says so ONCE per dataset, on one routine note that also says how page code reads the rows; the JSON part keeps the separate warnings that note stands for, `publishes pending` among them | usually nothing: this is the normal first-publish state for a dataset Dashies holds the data for, and a refresh fills the page in. Draw "no data yet" for `pending` in your page code - see "The shape your script is handed" - and stay until the refresh lands (`SKILL.md` Step 7). A publish whose `First data:` line says the rows are already served prints no such note, and counts the notes it left out |

**A line opening `Since the dry run of` is a count, not a warning.** A publish that passes a dry run's
`spec_hash` and the `report_id` that same dry run returned counts, on that line, the warnings and
obligations that dry run printed in full or itself counted, instead of printing them again. What prints under it is new,
or was last printed in full more than about an hour ago; the JSON part still lists every one. `SKILL.md`
Step 6 says when it applies.

## Publish and edit

Once the spec is written, go to Step 6 in `SKILL.md`: dry-run the document, then publish the
`spec_hash` that dry run returned rather than sending the same YAML a second time. To CHANGE a
published dashboard later, Step 8: `get_dashboard_spec` reads the stored spec back verbatim, and
you republish the same `path` with `spec_edits` - exact-string replacements against the stored
text - plus `base_spec_hash`, which both names the document being edited and is the lost-update
guard. **Send the change, not the document**; reserve a full `spec` for a first publish or a
genuine rewrite. `spec`, `spec_hash` and `spec_edits` are mutually exclusive.

**You never hand-edit the served page.** The next refresh rewrites its data, so an edit made
there would be lost or left inconsistent.
