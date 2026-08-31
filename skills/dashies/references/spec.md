# Filling the Dashies spec (Step 4)

You author a dashboard by writing a **spec** - one small YAML document - and passing it to
`publish_dashboard`'s `spec` argument. The server does the rest: it builds the dashboard from the
spec, checks the whole thing, and runs each dataset's `sql` once, live, so the published bytes
carry real numbers. **You write no markup and no styling.** A binding that names a column the SQL
never returns, or a tile with no type, is a **pointed publish error naming the exact field**, not
a blank tile or a silently wrong number that ships and rots.

So Step 4 is mechanical: turn the statements you wrote in Step 3 into datasets plus tiles. The
hard part - the grain and the correctness of the SQL - is already done.

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
  confined read-only path `validate_cube_sql` uses, then binds the tiles against the ACTUAL
  result columns. A dataset whose SQL fails, returns zero rows, or whose bindings do not match
  the columns it returned, cannot publish - so a spec that would render fake zeros never reaches
  the URL.
- **Numeric honesty is automatic.** Every value renders exactly or shows `-` (unavailable), never
  a rounded-wrong number. You do not manage precision.
- **Declare only what a tile uses.** A measure or dimension no tile reads raises
  ``[L3] /datasets/<ds>/measures/<key>: measure `<key>` is not referenced by any tile.`` (and the
  same wording for a dimension). This is a WARNING, not a blocking error: a spec whose only issues
  are these still publishes, and the advisory arrives on the SUCCESS report prefixed `warning:`. A
  FAILED publish lists only real errors, so its count is the number of things you actually have to
  fix. Two things that are NOT unreferenced: a measure used only as a ratio's `num` / `den` (the
  ratio is the reference), and a dimension in a dataset with no tile that could have shown it (a
  KPI-only dataset never warns about its grain).
- **No em or en dashes** in any spec string - titles, notes, labels, text tiles. Plain ASCII
  hyphens only.

## Top level

Required: `dashies`, `title`, `source`, `datasets`, plus `tiles`.

| Key | Type | Notes |
|---|---|---|
| `dashies` | `1` | Format version. Always `1`. |
| `title` | string (1-120) | The dashboard name (also the default display name). |
| `slug` | kebab-case, `^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$` (1-64 chars, alphanumeric first and last) | Optional; must equal the publish path slug when set. |
| `description` | string (<=4000) | Optional prose shown in the header. |
| `intent` | string (<=2000) | Optional semantic hint (what this dashboard is for) - guidance for tooling, not shown to viewers. The same optional `intent` is accepted on a dataset (<=2000) and on a dimension, a measure and a tile (**<=1000 each** - the tighter limit, so budget a measure's against 1000). It is the field that carries a measure's **provenance** - see **Provenance** below. |
| `source` | object | The one connection and schedule the whole dashboard refreshes on (below). |
| `datasets` | map, 1-8 | Named datasets; each key `^[a-z][a-z0-9_]{0,31}$`. First declared is the default. |
| `tiles` | array, 1-64 | The tiles, in document order (below). |
| `layout` | object | Optional: `columns: 12`, `max_width` (640-1920). |

`source` (required `connection` plus `schedule`):

| Key | Type | Notes |
|---|---|---|
| `connection` | `"self"` or a connection UUID | The built-in connection, or a connection id from `check_readiness` / `list_connections`. Required, with no default. |
| `schedule` | `manual` / `hourly` / `daily` / `weekly` / `monthly` | The coarse cadence (Step 5). Refine the timing afterwards with `set_refresh_schedule`. |
| `timezone` | string (1-64 chars) | Optional business zone for date bucketing; use an IANA zone name (e.g. `America/New_York`). The schema checks length only, not that the value is a real zone. |

## datasets

Required: `sql`, `dimensions`, `measures`. **Nothing else is yours to decide** - how the data is
prepared and where it is kept is chosen by the server from exactly these three plus the source,
and the publish report tells you what it chose for each dataset and why.

| Key | Type | Notes |
|---|---|---|
| `sql` | string (8-100000) | The single read-only `SELECT` from Step 3, already validated. |
| `dimensions` | map, 1-12 | Each key `^[a-z][a-z0-9_]{0,63}$` is an output column of `sql`. Value: `{ type?, label?, domains?, buckets?, intent? }`. |
| `measures` | map, 1-24 | Each key `^[a-z][a-z0-9_]{0,63}$` is a measure. Value: an **agg measure** or a **ratio measure** (below). |
| `intent` | string (<=2000) | Optional semantic hint for this dataset. |

**dimension** - `type` is OPTIONAL and, when set, is `category` or `date` ONLY (a `type: string`
is an `[L2]` error). It describes the FILTER or AXIS role, not the SQL column type. Omit it and
the dimension is treated as `category`; set `type: date` for a date dimension so it buckets as
one. An optional `label` (<=80 chars) sets the display name.

**Declare the dimension's bound wherever you know it, and prefer to know it.** A `category`
dimension declares `domains` - its value list, 1 to 200 unique entries, each a string, number or
boolean. A `date` dimension declares `buckets` - the maximum bucket count, 1 to 1000. **This is
the single most useful thing you can tell the server**: a dimension with a known, small set of
values is what lets a dashboard be prepared cheaply and answer exactly under every filter. A
dimension you cannot bound is a signal to go back to Step 3 and ask a narrower question.

`domains` also fixes the ORDER of a filter menu - see "Member order" below.

**measure** - exactly one of:

- **agg measure** (`agg` required): `agg` is one of `sum` `count` `min` `max` `avg`
  `count_distinct` `median` `percentile_cont` `percentile_disc` `stddev` `variance` `mode`.
  Optional `column` (the raw column the aggregate reads; defaults to the measure key),
  `percentile` (0 < p < 1, for `percentile_cont` / `percentile_disc`), `label` (<=80), `unit`,
  `intent`.

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
  two other declared measures, recomputed correctly under filters and never a stored pre-divided
  average. Each side may optionally set `num_scope` / `den_scope: all` to divide by the unfiltered
  total instead of the filtered one. Optional `label` (<=80), `unit`, `intent`.

  **This is how you carry a rate or a percentage, and it is the exact way to carry an AVERAGE**:
  `num` is the sum measure, `den` is a `count(*)` measure, which makes the tile exactly sum
  divided by count - the true weighted mean over the source rows, correct under every filter. It
  is strictly better than a stored average, because a stored average cannot be re-derived once a
  viewer filters.

**unit** (optional, on any measure) - controls display, never the stored value:
`{ kind: currency|percent|count|number, ... }`. `currency` REQUIRES `scale` (`cents` or `units`)
and takes an optional uppercase three-letter `currency` code (`^[A-Z]{3}$`, e.g. `USD`);
`percent` REQUIRES `scale` (`fraction` for 0..1, `points` for 0..100); `count` and `number` take
no `scale`. Optional `decimals` (0-6), `compact`. **Pick `scale` to match what your SQL emits** -
if the column is already dollars use `units`, if it is integer cents use `cents`. The wrong scale
is a 100x display error nothing can catch for you, because it is a display choice rather than a
structural fault.

**Known gap - `decimals` on a non-currency unit is not reliably applied.** The `kind` always
reaches the tile (a `percent` measure renders as a percent, a `count` as an integer), but
`decimals` currently rides the dashboard's CURRENCY descriptor: it is emitted only as an override
against the first `currency` unit found. So in a dashboard with no `currency` measure at all
there is nothing to override, and `decimals: 1` on a `percent` or `number` measure is dropped -
while adding an unrelated `currency` measure somewhere else makes that same `decimals` start
applying. Separately, on a `combo` tile the SECONDARY measure never carries its own `decimals` or
`currency`: the runtime reads one unsuffixed pair and applies it to both axes. This is a known
gap rather than intended behaviour - treat `decimals` as a hint, and do not restructure a spec
around it. (`scale` is not part of this gap: `fraction` and `units` are the identity, so there is
nothing for them to emit.)

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
every dimension, every measure and every tile. It is stored **verbatim** as part of the
spec bytes, so `get_dashboard_spec` hands it back unchanged and an editor sees it before
touching the measure. Nothing renders it to a viewer, so it costs the dashboard nothing.

**Limits, which differ by level:** root and dataset `intent` are **<=2000** chars; a
**dimension, a measure and a tile are <=1000 each**. Provenance goes on the measure, so
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

## tiles

A CLOSED set, and the table below is every type this skill teaches - `type` is REQUIRED (a tile
with no type is a `[L2]` error, because it can never blank-render). **The schema is the whole
set and it is wider than this table**: it also admits a `custom` type, an escape hatch for a
hand-written renderer, which nothing here describes and which you should not reach for. Some optional fields are common but are
NOT on every type; each tile's schema is closed, so an unaccepted key is a `[L2]` error naming
it. **No count is given here on purpose: the schema at the top of this file decides the set, and
a number written beside it goes stale the day a type is added, with nothing to show it.**

- `intent` and `w` (1-12 grid columns) are accepted on EVERY type.
- `dataset` (which dataset it reads; omit for the first, which is the default) on every type
  EXCEPT `text`, which has no data.
- `title` (<=120 chars) and `note` (<=1000) on every type that carries data - so on all of them
  EXCEPT `filter` and `text`, which is easier to remember as the exception than as a list.

The per-type "Key fields" column lists each type's own fields. A tile binding that names a
measure/dimension no dataset declares is an `[L3]` reference error.

| `type` | Required | Key fields |
|---|---|---|
| `kpi` | `measure` | `measure` (a measure key); `drill` (a dataset to drill into). |
| `chart` | `chart`, `x` | `chart` = `bar`/`hbar`/`line`/`area`; `x` (a dimension); then EXACTLY ONE of `measure` OR `measures` (2-4 unique, multi-series). A single `measure` may ADDITIONALLY take `series` (a dimension that splits that one measure into series) - `series` accompanies `measure`, it is not a third alternative and cannot be combined with `measures`. Optional `sort` (`value-desc`/`value-asc`), `limit` (1-100), `height` (120-800), `cross_filter` (bar/hbar single-measure only), `viewer` (`["sort","limit"]`, 1-2 unique, single-measure only), `drill`. |
| `table` | - | `columns` (1-12 unique measure/dim keys), `group` (a dimension), `sort` (`col:asc`/`col:desc`), `limit` (1-500), `viewer` (`["sort","limit"]`, 1-2 unique), `drill`. |
| `matrix` | `rows`, `cols`, `measure` | A pivot: two dimensions crossed, one measure, with margins. `rows` and `cols` are DIFFERENT dimensions of the tile's dataset; `measure` is one measure key (a `ratio` measure works, and renders the ratio per cell). Optional `subtotals` (`both` (default) / `row` / `col` / `none` - the token names the axis whose members get a total, so `row` adds the per-row Total COLUMN and `col` adds the per-column Total ROW; the grand total sits at their intersection and so appears only under `both`), `limit` (1-1000, rendered rows before truncation; default 200), `color` (`heat` / `diverging` - conditional formatting, off by default). See "The matrix" below. |
| `heatmap` | `rows`, `cols`, `measure` | The matrix with a colour scale. Every `matrix` field means the same thing here; the only difference is that `color` defaults to `heat` instead of off. See "The heatmap" below. |
| `drilldown` | `levels`, `measure` | A ranked breakdown of ONE dimension at a time, with an optional exact residual. `levels` is the hierarchy outermost-first (1-6 DIFFERENT dimensions of the tile's dataset) - one level is a plain Top-N list, two or more make each row a drill target. `measure` is one measure key (a `ratio` measure works). Optional `top_n` (1-1000, show only the top N by that measure), `other` (boolean, add the residual row - REQUIRES `top_n`), `total` (boolean, add the total row). See "The drill-down" below. |
| `scatter` | `point`, `x_measure`, `y_measure` | An AGGREGATE scatter: one point per member of `point` (a dimension), positioned by two measures. `x_measure` and `y_measure` are DIFFERENT declared agg measures (not ratios). Optional `limit` (1-2000, plotted points; default 500), `height` (120-800), `drill`. See "The scatter and the treemap" below. |
| `treemap` | `x`, `measure` | One rectangle per member of `x` (a dimension), its AREA being that member's share of the total. `measure` must DECOMPOSE - `sum` or `count` only. Optional `limit` (1-200, rectangles; default 24), `height` (120-800), `drill`. See below. |
| `stacked` | `x`, `series`, `measure` | A stacked column or area: `x` (a dimension), `series` (a DIFFERENT dimension whose values are the segments, at most 5 declared `domains`), `measure` (one measure key, which must be a `sum` or a `count` - see "Stacked charts" below). Optional `stack` (`normal` (default) / `percent` for the 100% stack), `chart` (`bar` (default) / `area`), `limit` (1-400 x categories; default 60), `height` (120-800). |
| `combo` | `x`, `measure`, `measure2` | A dual-axis chart: `x` (a dimension), `measure` on the LEFT axis and `measure2` on the RIGHT, two DIFFERENT measure keys (either may be a `ratio`). Optional `chart` (`bar` (default) / `line` / `area`), `chart2` (`line` (default) / `bar` / `area`), `axis_sync` (boolean - put both on one shared scale), `limit` (1-400), `height` (120-800). See "Dual-axis (combo) charts" below. |
| `pie` / `donut` | `x`, `measure` | A share of a whole. `x` is the slice dimension (at most 5 members); `measure` must be one whose parts add up to its whole (`sum` or `count`) - a ratio, a `min` / `max` or any other aggregate is refused, because its parts do not. Optional `height` (120-800). No `limit`: a wider dimension is refused, not truncated. `pie` and `donut` differ only in the hole. See "Pie, donut and gauge" below. |
| `gauge` | `measure`, `max` | One value against a declared scale. `max` is required (and > `min`); optional `min` (default 0), `target` (must lie within the scale, marked on the arc), `height` (120-800). A ratio measure is allowed here. See "Pie, donut and gauge" below. |
| `waterfall` | `x`, `measure` | Contributions that build to a total: each bar starts where the previous ended, closed by the total. `measure` must DECOMPOSE - `sum` or `count` only. Optional `limit` (1-200, contribution bars; default 40), `height` (120-800), `drill`. See "The waterfall and the funnel" below. |
| `funnel` | `x`, `measure`, `stages` | Stage sizes in an order YOU declare: `stages` lists the dimension VALUES, 2-12, no repeats. It shows sizes only - it does NOT compute conversion between stages. Optional `height` (120-800), `drill`. See below. |
| `filter` | `dimension` | `dimension`; `label` (<=80); optional `multi` / `range` (booleans, mutually exclusive - set at most one; a filter is single-select when neither is set). A `multi` or `range` filter asks more of the dataset than a single-select one, because it has to answer combinations rather than one value at a time; where a measure cannot answer them, publish refuses and says what to change. |
| `text` | `body` | `body` (markdown, <=4000) - static prose, no data. |

## Member order on an axis - your ROW ORDER is the default

No tile has an `order` field, and most draw a dimension's members in **the order the dataset's
rows arrive** - the order your `sql` returned them in. So **end the `sql` in an explicit
`ORDER BY`**. Without one the sequence is whatever the warehouse happened to produce, and it can
change between refreshes with nothing in the spec changing.

**Nothing warns you when this is wrong.** There is no publish error and no advisory: the axis or
the menu simply comes out in some order, looks deliberate, and may not be the same order next
month. That is the whole reason this section exists.

**Do not assume a `date` dimension is exempt.** Some tiles put it in calendar order and some
treat it exactly like a category - a month `filter` menu is one of the latter, so it still needs
the `ORDER BY`. Which is which is the DATE column below, and it does not track the kind of tile:
a `matrix` sorts a date, a grouped `table` does not, and both are grids of cells.

Read the row you need. The table is the source of truth here - it was derived one tile at a time,
twice per tile, and it has survived independent re-measurement. The prose summaries that used to
sit here, restating it in sentence form, kept turning out wrong; that is why they are gone rather
than corrected, and why a future edit should add a column instead of a sentence.

| Tile | CATEGORY dimension | DATE dimension |
|---|---|---|
| `matrix`, `heatmap` | **Your row order.** No `sort` field exists on these two, so the SQL is the only lever. | Calendar ascending |
| `chart` (`x` axis) | Your row order, unless you set `sort: value-desc` / `value-asc`. | Calendar ascending |
| `waterfall` | **Its own: largest contribution first.** | Calendar ascending |
| `table` (with `group`) | Your row order, unless you set the tile's own `sort`. | **Your row order** |
| `pie` / `donut` | Your row order. | **Your row order** |
| `filter` menu, and a `cross_filter` selection | Your row order (first-seen). | **Your row order** |
| `stacked`, `combo` | Your row order. **Neither has a `sort` field** (only `chart` and `table` do), so the SQL is the only lever. | Calendar ascending on the `x` axis |
| `treemap` | Its own: largest share first. | Its own: largest share first |
| `drilldown` | Its own: ranked by the measure. | Its own: ranked by the measure |
| `funnel` | The `stages` list you declare on the tile. | The `stages` list |

**ONE EXCEPTION, and it is under your control rather than the server's.** Where a dimension
declares `domains`, the filter menu is built from that ARRAY and an `ORDER BY` cannot reach it.
So **list `domains` in the order you want the menu**. Measured with a control that isolates the
cause rather than merely observing it: strip `domains` and the menu starts following row order
again, so it is the declaration doing the work.

Two consequences that are easy to miss:

- **`matrix` / `heatmap` `limit` truncates from the FRONT of that order.** The tile renders the
  first `limit` rows and says so ("Showing the first N of M rows"), so your row order decides
  which members are on screen at all, not just their sequence. Totals are unaffected - every
  margin is re-evaluated over the whole selection, not over what is displayed.
- **If a tile's row says it sorts itself, there is no way to override it** - not from the spec
  (those tiles have no `sort` field) and not from the SQL. For a `waterfall` specifically, when
  the bar SEQUENCE is the point of the chart, use a `funnel` instead: you list its members in
  `stages`, in the order you want them drawn.

Every row above was measured against the runtime rather than read out of it: each tile rendered
twice, once with the data in one order and once reversed, reading the DOM back - for a category
dimension and again for a date one.

## The matrix

The pivot table - two dimensions crossed, one measure per cell, with row totals, column
totals and a grand total. It needs no new SQL and no new dataset: whatever dataset you already
wrote for the KPIs answers it, as long as it groups by both axes.

```yaml
- type: matrix
  rows: region        # the row axis (a dimension of this tile's dataset)
  cols: month         # the column axis (a DIFFERENT dimension)
  measure: customers  # one measure per cell
  subtotals: both     # both (default) | row | col | none
  title: Customers by region and month
```

Three things worth knowing, because they change what you can put in one:

- **Both axes draw in your ROW ORDER** (a date dimension excepted - it sorts ascending), and
  `limit` truncates from the front of that order. A matrix has no `sort` field, so give its
  dataset's `sql` an explicit `ORDER BY`. See "Member order on an axis" above.
- **Every total is the measure RE-EVALUATED at that total's grain, never a sum of the cells on
  screen.** So **a distinct-count or median subtotal is EXACT** - the thing Tableau and Power BI
  cannot answer off a pre-aggregate - and truncating a long axis cannot corrupt a total (the tile
  truncates at 200 rows / 100 columns and says so).
- **Two blanks that mean different things.** An empty body cell means there are no rows at that
  intersection (the usual pivot convention). A `-` means the value cannot be shown exactly. If
  the DATASET cannot answer the tile at all, the whole tile refuses with the reason instead of
  filling itself with dashes.

Rules the validator enforces, so none of these can reach a published dashboard:

- `rows` and `cols` must be declared dimensions of the tile's dataset, and must differ.
- A ratio measure with `num_scope` / `den_scope: all` (percent of total) cannot go in a matrix: a
  cell has three totals - its row, its column and the grand - and the scope names none of them.
  Put that measure on a `kpi` instead.

**Bound both axes.** A matrix crosses two dimensions, so its cost is the product of their two
member counts and it is the tile most likely to ask for something that cannot be prepared. Declare
`domains` or `buckets` on both and keep them small; if the combination is too wide, publish says
so and says what to change.

## The heatmap, and conditional formatting

A heatmap is the matrix with a colour scale. It takes every matrix field and adds `color`:

```yaml
- type: heatmap
  rows: region
  cols: month
  measure: revenue
  color: heat         # heat (default) | diverging
  title: Revenue by region and month
```

The same `color` field works on a plain `matrix`, where it is OFF unless you set it - that is
the "conditional formatting" case, when you want a table that is still primarily read as
numbers with the magnitudes shaded in behind them. Use `type: heatmap` when the colour IS the
point and `type: matrix` with `color:` when the numbers are.

- **`heat`** is a sequential ramp, palest at the lowest visible value and deepest at the
  highest. Reach for it on a quantity - revenue, users, orders.
- **`diverging`** is red-neutral-blue and **pivots at ZERO**, always. Reach for it on a signed
  measure - margin, variance to target, week-over-week change. There is no midpoint option on
  purpose: a midpoint parked at the average moves every time a viewer filters, so half the
  cells change colour for reasons that have nothing to do with the data. If you want to
  diverge around something other than zero, subtract it in SQL and the measure *is* the
  deviation (`sum(actual) - sum(target) as variance`).

Three things about the colouring that are worth knowing when you author one:

- **The scale is computed from the cells ON SCREEN, every time the view changes.** Filter the
  dashboard and the ramp re-derives over what is left, so the colours always describe what the
  viewer is actually looking at. The legend prints the two endpoints, so the domain is visible
  rather than implied.
- **Totals are never coloured.** A row total is a much bigger number than any cell under it,
  so colouring it would make it the darkest thing on screen and squash the whole body into the
  palest band. The margins render as ordinary numbers.
- **A cell that has no exact value is never given a colour.** It renders `-` on a hatched
  background, which is deliberately not a colour on the ramp: in a heatmap an uncoloured cell
  reads as "the smallest value here", and that would be a claim about a number that does not
  exist. An EMPTY cell (no rows at that intersection) stays empty, as in any pivot.

Everything the matrix refuses, a heatmap refuses identically and for the same reason - the two
share a resolver - so the axis and percent-of-total rules above both apply unchanged, as does
the advice to bound both axes.
## The scatter and the treemap

Two more objects that need no new SQL and no new dataset shape: both read ONE grouping set -
the same one a bar chart of that dimension reads - and differ only in how they draw it.

```yaml
- type: scatter
  point: product        # one point per PRODUCT
  x_measure: revenue    # two measures, re-evaluated at that member
  y_measure: margin
  title: Revenue against margin by product

- type: treemap
  x: product            # one rectangle per PRODUCT
  measure: revenue      # area = that product's share of total revenue
  limit: 20
  title: Revenue share by product
```

**The scatter is the AGGREGATE form, and that is the whole thing to understand about it.**
One point per dimension MEMBER, not one point per source row - "revenue vs margin by product",
which is what most enterprise scatters actually are. The chart says so in its own accessible
name ("one point per Product"), so nobody reads it as a cloud of observations.

A **raw-observation** scatter (one point per row) is a different object and does not exist.
A scatter always plots one point per member of `point`, never one per source row, and asking
for the second is refused at publish with the reason. There is no way to ask for it and get
something that looks right but is not.

Two more scatter rules, both refused at publish:

- `x_measure` and `y_measure` must be DIFFERENT measures. The same measure on both axes draws
  a perfect diagonal whatever the data says - every number in it exact, and the picture a lie.
- Both must be plain agg measures. A `ratio` measure cannot go on an axis (the markup carries
  one num/den pair and a scatter has two axes); put it on a `kpi`.

At view time, a point whose coordinate cannot be computed exactly is **not plotted at all**,
and the tile says how many were dropped. It is never placed at the origin - that would claim a
value of zero on both axes.

**The treemap's denominator is the resolver's total, never the sum of the rectangles.** The
consequence is worth knowing before you set `limit`: if you show the largest 20 of 137
products, the rectangles fill 20-products' worth of the box and **the rest stays empty**,
rather than being stretched to fill it. A truncated treemap therefore LOOKS truncated, and the
tile says so. That is deliberate - the alternative is a picture claiming those 20 products are
the whole business.

Because area asserts part-of-whole, a treemap refuses anything that would make that assertion
false, at publish:

- `measure` must DECOMPOSE: `sum` or `count`. A distinct count's parts overlap, a median's do
  not combine, and a `min` of the parts is just the smallest part - in each case the areas
  would claim a decomposition the data does not have. Use a `chart` (a bar chart compares the
  values without claiming they are shares of a total).
- No `ratio` measure: a share of a rate is not a part of a whole.

At view time it also refuses a negative value (an area cannot show one) and a total that is
not positive (there is no whole to be a part of). No percentage is drawn anywhere - the area
carries the proportion, and each rectangle is labelled with its own exact value.

## The drill-down

A ranked breakdown of one dimension, where each row can open the next level down. It needs no
new SQL and no new dataset: drilling asks the same dataset for a different grouping at a
narrower filter state, and it is answered exactly rather than by re-adding what is on screen.

```yaml
- type: drilldown
  levels: [category, subcategory]   # outermost first; 1-6 dimensions
  measure: revenue                  # ranks the rows, and is what each row shows
  top_n: 5                          # show only the top 5
  other: true                       # ... plus an exact residual row
  total: true                       # ... plus the total for the current filters
  title: Revenue by category
```

One level (`levels: [customer]`) is the plain "Top 10 customers" tile. Two or more make it a
drill-down: click a row to go a level deeper, and a breadcrumb walks back out.

Three things worth knowing, because they change what you can put in one:

- **Drilling filters the WHOLE dashboard.** A drilled member becomes a normal single-select
  filter on that level's dimension, so every other tile follows it, the URL carries it, and
  Back undoes it. The tile says so on its face. If a sibling tile's dataset does not declare
  that dimension it cannot follow, and that tile shows its usual "not filtered by X" note - so
  a broader number sitting next to a drilled one is always labelled.
- **"Other" is RE-EVALUATED, not subtracted.** It is the measure computed over the members you
  cut, not the total minus the rows on screen. For a measure whose parts add up the two agree; for
  a `min` / `max` measure only the first means anything. And for one whose parts do not (a distinct
  count, a median, a true average) there is no honest residual at all - "distinct customers in
  Other" cannot be derived from anything on screen - so that row renders `-` and says why. The
  rows you DID show stay exact.
  If the breakdown does not add up to the total at all (a dataset missing a member at that
  grain), the residual refuses too rather than quietly coming up short - it is the one number
  on the tile you could not otherwise check.
- **The total is re-evaluated too**, so cutting the list to the top 5 cannot corrupt it. It is
  the total for the current filters, never the whole dataset and never the sum of the visible
  rows.

Rules the validator enforces, so none of these can reach a published dashboard:

- Every `levels` entry must be a declared dimension of the tile's dataset, and they must all
  differ. At most 6.
- `other` requires `top_n`. With every member on screen there is no residual, so the row would
  be an empty claim.
- A ratio measure with `num_scope`/`den_scope: all` (percent of total) cannot go in one: a row
  has three candidate denominators - the rows shown, the residual and the total - and the scope
  names none of them. Put that measure on a `kpi` instead.

A measure whose parts do not add up is answered exactly here too: every member is then one
precomputed cell and therefore exact at any depth. The residual still refuses honestly, which
is the point.

## Stacked charts

One measure, one category axis, and a series dimension whose values are the segments.

```yaml
- type: stacked
  x: month            # the category axis
  series: channel     # a DIFFERENT dimension - its values are the segments (max 5)
  measure: sessions   # must be a sum or a count
  stack: normal       # normal (default) | percent (the 100% stack)
  chart: bar          # bar (default) | area
  title: Sessions by channel
```

**Bound the `series` dimension, and the reason is not performance.** A stacked bar needs two
grains: the `(x, series)` grouping for its segments and the `x`-only grouping for its total.
Where the dataset can answer both - which is what declaring the bounds on both dimensions buys -
the tile renders each column's total from its own answer rather than by adding up the segments,
and then **asserts that the segments agree with that total**, refusing the tile with the reason
if they do not. Tableau and Power BI have no second grain to check against. Where the dataset can
only answer one grain there is nothing to check the total against; the tile is still exact for a
measure whose parts add up, but the cross-check is what you give up.

**The measure must ADD across the segments** - a `sum` or a `count`. This is checked at
publish, and it is a separate rule from the assertion above rather than a duplicate of it: a
`ratio` measure is composable, so the two grains agree with each other while the segments
being drawn are ratios, which do not add to the ratio of the whole. The assertion cannot see
that. A `min`, a `max`, a distinct count, a median or a percentile is refused for the same
reason. To show a rate over a stacked chart, put it on a `combo` tile's secondary axis.

Three things the renderer refuses at VIEW time, because they depend on what the data turns
out to be rather than on what the spec says:

- **A negative segment is never stacked.** Bar length stops being the sum of the parts, so
  the tile falls back to GROUPED bars over the same exact values and says why. (Power BI
  renders the misleading version.)
- **A 100% stack refuses a column that mixes positive and negative segments**, because no
  share of it is a true proportion.
- **A 100% stack shows nothing for a column whose total is zero** (every share would be 0/0)
  and names it under the chart.

None of these can be prevented in the spec, so a stacked chart is one of the few tiles whose
tile-level state can change on a refresh. If your measure can go negative, prefer
`stack: normal` (which degrades gracefully) over `percent` (which refuses).

## Dual-axis (combo) charts

Two measures at one grain, drawn against two scales - revenue columns with a margin line is
the canonical shape.

```yaml
- type: combo
  x: month
  measure: revenue      # the LEFT axis
  measure2: margin      # the RIGHT axis - a DIFFERENT measure; a ratio works here
  chart: bar            # bar (default) | line | area
  chart2: line          # line (default) | bar | area
  title: Revenue and margin
```

Each measure resolves exactly as a single-measure chart of it would, so a combo series equals
the chart you would have drawn on its own. Any aggregate works on either side, including one
whose parts do not add up to its whole - a combo never claims the two series make a whole,
which is why it needs no rule about that at all.

Dual axis is criticised for letting two arbitrary scales imply a relationship. Three things
are built in rather than left to the author:

- `axis_sync: true` puts both measures on ONE shared scale (Tableau's Synchronize Axis). Use
  it when the two measures share a unit; leave it off when they do not.
- **Both axes are always drawn and always labelled**, each in its own measure's format, and
  the legend names which axis each measure is read against. There is no configuration in
  which a second scale is present and unlabelled.
- A standing note under the chart states either that the two scales are not comparable by
  height, or that they have been synchronised.

A `ratio` measure with `num_scope`/`den_scope: all` (percent of total) cannot go on a combo:
the two sides share one binding, so a scope on one would be ambiguous about the other. Put
that measure on a `kpi`.
## Pie, donut and gauge

Two shapes, three types. A `pie` / `donut` shows how ONE decomposable measure splits across a
small dimension; a `gauge` shows one number against a declared target.

```yaml
- type: donut          # or: pie - identical, the donut just has a hole
  x: channel           # the slice dimension (<= 5 members)
  measure: sessions    # one DECOMPOSABLE measure (sum or count)
  title: Share of sessions by channel

- type: gauge
  measure: sessions
  min: 0               # optional, default 0
  max: 5000            # REQUIRED - the arc has to be a fraction of something
  target: 4000         # optional, marked on the arc
  title: Sessions against target
```

Three things decide whether a pie is possible at all, and it is worth knowing them before you
write one, because each is refused at publish rather than at view time:

- **The measure's parts must add up to its whole - `sum` or `count`.** This is stricter than everywhere else
  in the format, and the reason is that a pie claims its parts compose into its whole. A
  distinct count, a median, a percentile, a **min**, a **max** and a ratio can all be computed
  exactly per slice and still not add up to anything: five exact regional medians do not
  compose into the overall median. So they are refused with the aggregate named. Show that
  measure on a `chart` (bar) instead, which compares values without claiming they compose.
- **At most 5 slices.** The mark palette is five colours wide (every one contrast-validated),
  so a sixth slice would repeat one and two members would read as one. If a dimension declares
  more than 5 `domains` the spec is rejected; if it turns out wider at refresh, the tile
  refuses and says so. There is no top-N and no "Other" slice - use a bar chart, or filter the
  dimension down.
- **The slice dimension has to be something the dataset groups by**, like any other binding, and
  the measure has to be one it declares. A binding naming something the dataset does not have is
  a pointed publish error rather than an empty ring.

**What a pie shows, and what it deliberately does not.** Each slice states its own value and
the tile states the TOTAL - in the hole for a donut, in the legend for a pie. It never prints a
percentage. That is not an omission: a rendered "24%" is a number the renderer would have
divided into existence, and the wedge already carries the proportion exactly. The same rule is
why a gauge shows the value and the target but no "% of target".

**Why the total is worth trusting.** It is computed SEPARATELY - the dataset's own
rolled-up figure for the current filters - not by adding up the slices being drawn. So if
anything cannot be shown, the circle is left visibly OPEN and the tile says why, instead of the
remaining wedges quietly growing to fill it. On a well-formed dataset this never happens and
the circle closes.

**Gauge specifics.** `max` is required and has no default: deriving one from the value would
make the picture a function of the number it is describing. A value outside `min..max` pins the
arc to its end and says so - the printed figure stays exact, and the note tells the reader which
to trust. A value that cannot be computed exactly draws no arc at all and prints `-`, never a
needle sitting at the minimum. A ratio measure IS allowed on a gauge (a conversion rate against
a target is one number against another), unlike on a pie.


## The waterfall and the funnel

Two more objects on the same one grouping set, both about SEQUENCE rather than shape.

```yaml
- type: waterfall
  x: reason            # one bar per reason
  measure: delta       # each bar is that reason's contribution
  title: What moved the net change

- type: funnel
  x: step
  measure: people
  stages: [visited, signed_up, activated, paid]   # the order YOU declare
  title: Journey by stage
```

**A waterfall orders its own bars, and you cannot change that from the spec or the SQL.** A
category `x` reads largest contribution first; a date `x` reads in calendar order. An `ORDER
BY` in the dataset's `sql` does not reach it, and there is no `sort` field. If the sequence is
the point of the chart, use a `funnel` - its `stages` is a declared order.

**A waterfall decomposes only, and it is all-or-nothing.** Its bars claim to compose into its
total, one after another, so `measure` must be `sum` (or `count`, which folds to sum). A
distinct count's parts overlap, a median's do not combine, a `min` of the parts is just one
part - and a `ratio` composes, so nothing downstream would catch it while the bars drawn were
rates that do not add. All of those are refused at publish.

The part worth knowing before you build one: **if any single contribution cannot be shown
exactly, the whole chart is withheld.** That is deliberate. Every later bar is positioned where
the previous one ended, so one missing contribution moves all of them - and the chart would
still reconcile start-to-end, because the total is read separately. A zero-height step would
read as "no change this period", which is a confident claim about the business made out of
missing data. The Total bar is always the resolver's own total, never the sum of the bars.

**A funnel shows stage sizes. It does not compute conversion.** This is the one to read twice,
because it is the thing people expect a funnel to do.

Nothing in the data can show that your stages are **nested cohorts** - that everyone who
reached `paid` also appears in `signed_up`. They might be disjoint groups, or overlapping
ones, or the same people counted on different days. So a "42% conversion" between two stages is
a number the data cannot justify, and there is no field to ask for one: no rate option, no
percentage is drawn, and a `ratio` measure on a funnel is refused at publish.

If you want a conversion rate, declare it as a `ratio` measure - where the numerator, the
denominator and therefore the cohort claim are yours - and put it on a `kpi`.

**A stage with no data is "-", never 0.** A stage you declared that the dataset says nothing
about (most often a typo) draws no bar and reads "-". Rendering it as 0 would show a 100%
drop-off that only ever existed in the missing data. The validator also checks every stage
against the dimension's declared `domains`, so the usual way to reach that state is caught
before you publish.

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
        date_trunc('month', o.placed_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/New_York')::date as month,
        o.region                                                                                  as region,
        sum(o.amount_cents)                                                                       as revenue_cents,
        count(*)                                                                                  as orders
      from analytics.fct_orders o
      where o.placed_at >= now() - interval '18 months'
      group by 1, 2
      order by 1, 2
    dimensions:
      month:  { type: date, buckets: 18, label: Month }
      region: { type: category, domains: [AMER, EMEA, APAC], label: Region }
    measures:
      revenue_cents:
        agg: sum
        unit: { kind: currency, scale: cents, currency: USD }
        intent: >-
          dbt semantic layer, metric `revenue` (models/marts/metrics.yml). Definition taken from
          dbt, not re-derived.
      orders:
        agg: sum
        unit: { kind: count }
      aov:
        ratio: { num: revenue_cents, den: orders }
        label: Average order value
        unit: { kind: currency, scale: cents, currency: USD }
tiles:
  - { type: filter, dimension: region, label: Region }
  - { type: kpi, measure: revenue_cents, title: Revenue }
  - { type: kpi, measure: aov, title: Average order value }
  - { type: chart, chart: line, x: month, measure: revenue_cents, title: Revenue by month }
  - { type: table, columns: [region, revenue_cents, orders], group: region, title: By region }
```

Note what is NOT in it: nothing about how the data will be prepared or where it will be kept.
The publish report says what the server chose for `main` and why.

## Migrating a dashboard that has no spec

A dashboard published before specs existed has nothing for `get_dashboard_spec` to read.
`derive_dashboard_spec({ slug })` reconstructs a draft from what that dashboard already carries,
read-only, storing nothing. The draft references the dashboard's CURRENT published page with
`look: { from: <slug> }` rather than inlining it, so the tool response and the eventual stored
spec both stay small; republishing resolves that page from storage and re-runs every dataset
live, so the layout stays byte for byte while the numbers update. A `look` spec declares
`datasets` and `source` and carries no `tiles` or `layout`.

Where the old page has recognizable tiles, the draft also returns a ready-to-paste `tiles:`
block. **Taking it is the better outcome**: it moves the dashboard onto the managed layout, where
the server owns the rendering, and it is what makes every later edit a spec edit.

## What a publish WARNING means

Errors block; warnings do not. A warning on the publish report is the server telling you it
seeded the dashboard, looked at the REAL values that came back, and found something that will
read wrong at view time. Read them - they are the cheapest signal you will get, and several
describe a tile that publishes clean and then refuses to draw.

| warning | what the seed found | what to do |
|---|---|---|
| `slice_cardinality` | the `pie`/`donut` slice dimension seeded more than 5 distinct members | declare `domains` to pick 5, or use a `chart` (bar), which has no colour limit. The renderer REFUSES a wider set rather than dropping a slice, so this tile would show its reason instead of your data |
| `series_cardinality` | a `chart`/`stacked` `series` dimension seeded more than 5 | declare `domains` to pick 5. A `chart` reuses a colour; a `stacked` refuses outright |
| `funnel_stage_absent` | a `stages` entry is not one of the seeded values of the funnel's `x` | fix the spelling, or drop the stage. An absent stage renders as `-`, which reads like a 100% drop-off |
| `stack_percent_mixed_sign` | a `stack: percent` column seeded both positive and negative segments | use `stack: normal` (same exact values, signed axis) or a `chart`. No share of a mixed-sign column is a true proportion, and the runtime refuses that column |
| `domain_drift_at_publish` | a seeded value is outside the dimension's declared `domains` | add it to `domains`, or narrow the SQL. The runtime filter drops it |
| `null_leading_dimension` | a declared dimension is NULL across the whole leading head of the dataset | a null dimension cell renders as a blank label, so a table leads with unlabelled rows. The warning names the column and how many of the dataset's rows carry the null, so you can tell a handful to label from a broken join. Label it in SQL (`coalesce(...)` to an explicit value) if the null is meaningful, or filter it out if it is not |
| `percent_points_suspect` | a `percent`/`fraction` measure seeded values that look like 0..100 | declare `scale: points` |
| `rate_shaped_sum` | a `sum` measure seeded values all between 0 and 1 | summing rates is usually wrong - declare a ratio, or sum the underlying counts |
| `date_dim_not_iso` | a `date` dimension seeded values that are not ISO | bucket to `YYYY`, `YYYY-MM` or `YYYY-MM-DD` in SQL |
| `col_extra` | the query outputs a column nothing declared reads, so it reaches every viewer and is read by nothing | drop it from the `select`, or declare it. (An undeclared column that would ship real data is an ERROR, not this warning) |
| `is not referenced by any tile` | a declared dataset, measure or dimension no tile reads | delete it, or bind it. See "House rules" for the two cases that are NOT unreferenced |

The member-bound four (`slice_cardinality`, `series_cardinality`, `funnel_stage_absent`,
`stack_percent_mixed_sign`) are warnings rather than errors ON PURPOSE: they are judged against
the data as it was AT PUBLISH, and the next refresh can move it. Where you declare `domains`,
the same rules become blocking errors - a declared bound is a claim you wrote down, so the
server holds you to it. That is the tradeoff: declare `domains` and get a hard gate, leave it
off and get an advisory plus the runtime's own refusal as the backstop.

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
