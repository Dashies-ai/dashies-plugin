# Filling the Dashies spec (Step 4)

You author a refreshable dashboard by writing a **spec** - one small YAML document -
and passing it to `publish_dashboard`'s `spec` argument. The server does the rest:
it **compiles** the spec into the HTML + data island + refresh manifest, **validates**
the whole thing, and **seeds** it (runs each dataset's cube once, live) so the published
bytes carry real numbers. You never write `data-dash` markup, the `#dashies-data` island,
the runtime marker, or the `source_config` manifest - the compiler emits all of them and
keeps them consistent. A binding that names a column the SQL never returns, a role-less
tile, a non-additive agg (`avg`, `count_distinct`, `median`) on a `cube` measure - each is a
**pointered publish error naming the exact field**, not a blank tile or a silently-wrong
number that ships and rots.

So Step 4 is: turn the cube you designed in Steps 1-3 into datasets + tiles. The cube SQL
and its additivity classification (the hard part) are already done; the spec is mechanical.

The full field contract is the JSON Schema at `https://dashies.xyz/schema/dash/v1.json`
(`$id`, draft 2020-12) - it is the exhaustive source of truth. This reference is its
readable form - the fields you author with and their load-bearing bounds; the schema above
stays the exhaustive contract for the exact limits. `additionalProperties` is `false`
everywhere - an unknown or misspelled key is a `[L2]` error naming the key, never silently
ignored.

## House rules (read once)

- **YAML 1.2 core** (the server parses with `version: "1.2"`). Only `true` / `false` are
  booleans, only `null` / `~` / empty is null, and a bare number is a number - so quote a
  STRING value that would otherwise read as one of those (a numeric-looking code like a zip,
  a literal `true` you want as text, a bare `null`). Unlike YAML 1.1 there is NO "Norway
  problem" here: `no` / `off` / `yes` / `NO` and a date-like `2026-07-01` all already parse
  as plain strings, so `domains: [NO, SE]` is fine (quoting a string is always safe too).
  JSON is also accepted (a spec is valid JSON-as-YAML) if you prefer no ambiguity.
- **The `slug`, when present, must equal the publish `path` slug** (`publish_dashboard({ path: "<slug>", spec })`).
  Omit it and the path slug is used. A mismatch is a `[identity]` error at `/slug`.
- **Every publish SEEDs live.** The compiler runs each dataset's `sql` through the same
  confined read-only executor `validate_cube_sql` uses, then binds the tiles against the
  ACTUAL result columns. A dataset whose SQL fails, or that returns zero rows, or whose
  bindings do not match the seeded columns, cannot publish - so a spec that would render
  fake zeros never reaches the URL.
- **Numeric honesty is automatic.** The runtime renders every value exactly or shows `-`
  (unavailable) - never a rounded-wrong number. You do not manage precision.
- **No em/en dashes** in any spec string (titles, notes, labels, text tiles) - plain ASCII
  hyphens only.

## Top level

Required: `dashies`, `title`, `source`, `datasets`, plus EXACTLY ONE of `tiles` OR `look`
(mutually exclusive - the schema's top-level `oneOf`). `look` additionally forbids `theme`
and `layout` (a look-mode body owns its own styling and markup).

| Key | Type | Notes |
|---|---|---|
| `dashies` | `1` | Format version. Always `1`. |
| `title` | string (1-120) | The dashboard name (also the default display name). |
| `slug` | kebab-case, `^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$` (1-64 chars, alphanumeric first + last) | Optional; must equal the publish path slug when set. |
| `description` | string (<=4000) | Optional prose shown in the header. |
| `intent` | string (<=2000) | Optional semantic hint (what this dashboard is for) - guidance for tooling, not shown to viewers. The same optional `intent` annotation is accepted on a dataset (<=2000), a dimension, a measure, and every tile (<=1000 there). |
| `source` | object | The one connection + schedule the whole dashboard refreshes on (below). |
| `datasets` | map, 1-8 | Named datasets; each key `^[a-z][a-z0-9_]{0,31}$`. First declared = the default. |
| `tiles` | array, 1-64 | The tiles, in document order (below). Mutually exclusive with `look`. |
| `look` | object | v1.1 whole-look escape hatch: `{ html }` (the body inline, preserved verbatim outside its data island) or `{ from: <slug> }` (references the current published body of the publish target instead of inlining it) - exactly one of the two (below). Mutually exclusive with `tiles`/`theme`/`layout`. |
| `layout` | object | Optional: `columns: 12`, `max_width` (640-1920). Not allowed with `look`. |
| `theme` | object | Optional: `accent` (`#rrggbb`), `font` (`sans`/`serif`/`mono`), `density` (`compact`/`comfortable`/`spacious`), `mode` (`light`/`dark`/`auto`), `css` (<=50000). Prefer the `dashies-design` skill for real branding. Not allowed with `look`. |

`source` (required `connection` + `schedule`):

| Key | Type | Notes |
|---|---|---|
| `connection` | `"self"` \| warehouse UUID | `self` (Dashies' no-PII metrics) or a connection id from `list_connections`. |
| `schedule` | `manual`\|`hourly`\|`daily`\|`weekly`\|`monthly` | The coarse cadence (Step 5). Refine timing later with `set_refresh_schedule`. |
| `timezone` | string (1-64 chars) | Optional business zone for date bucketing; use an IANA zone name (e.g. `America/New_York`). The schema checks length only, not that the value is a real zone. |

## datasets

Each dataset is one materialization (Steps 1-3 chose its `mode`). Required: `sql`,
`dimensions`, `measures`.

| Key | Type | Notes |
|---|---|---|
| `mode` | `cube`\|`lattice`\|`hybrid`\|`rows` | Optional. Omit and the server auto-selects `cube` or `lattice` from the measures + dimensions; declare `rows` or `hybrid` explicitly (they ship row-level bytes). The report's `mode_choices` tells you what each resolved to and why. |
| `sql` | string (8-100000) | The single read-only cube SELECT from Step 3 (already validated). For `lattice`/`hybrid` it is the `GROUP BY CUBE` lattice. |
| `rows_sql` | string (8-100000) | REQUIRED for `hybrid` (the row-level slice), forbidden otherwise. |
| `rows_window` | int (100-8e6) | `rows`/`hybrid` only: bound the inline slice to the first N rows of the windowed statement's ORDER BY (`sql` for `rows`, `rows_sql` for `hybrid`). That top-level ORDER BY is REQUIRED and enforced at publish - see cube.md. Order by time descending for "the most recent N". |
| `dimensions` | map, 1-12 | Each key `^[a-z][a-z0-9_]{0,63}$` = an output column of `sql`. Value: `{ type?, label?, domains?, buckets?, intent? }`. |
| `measures` | map, 1-24 | Each key `^[a-z][a-z0-9_]{0,63}$` = a measure. Value: an **agg measure** or a **ratio measure** (below). |
| `intent` | string (<=2000) | Optional semantic hint for this dataset. |

**dimension** - `type` is OPTIONAL and, when set, is `category` or `date` ONLY (a
`type: string` is a `[L2]` error "type must be one of category, date"); it describes the
FILTER/AXIS role, not the SQL column type. Omit `type` and the dim is treated as `category`;
set `type: date` for a date dimension (so it buckets as a date). An optional `label`
(<=80 chars) sets the display name. A `category` dim may declare `domains` (its bounded value
list: 1-200 unique entries, each a string / number / boolean); a `date` dim may declare
`buckets` (max bucket count, 1-1000). A `lattice`/`hybrid` dimension MUST declare its bound
(`domains` for category, `buckets` for date) - that is what keeps the lattice finite.

**measure** - exactly one of:
- **agg measure** (`agg` required): `agg` is one of `sum` `count` `min` `max` `avg`
  `count_distinct` `median` `percentile_cont` `percentile_disc` `stddev` `variance` `mode`;
  optional `column` (the raw column the agg reads; defaults to the measure key), `percentile`
  (0<p<1, for `percentile_cont`/`_disc`), `label` (<=80), `unit`, `intent`. The **allowed aggs
  depend on the mode**: a `cube` measure is `sum`/`count`/`min`/`max` only and takes NO
  `column` (additive-only, enforced); `rows` widens to `avg`/`count_distinct`/`median`/
  `percentile_cont`; `lattice`/`hybrid` allow ANY agg (each exact per cell). Declaring a
  non-additive agg on a `cube` measure is a `[L2]` error pointing you to `lattice`/`rows`.
  On a `cube` the runtime re-aggregates the pre-aggregated cells, so a count-of-rows
  (`count(*)` in the SQL) declared `agg: count` is rolled up by **summing** the per-cell
  counts: `agg: count` and `agg: sum` on that column are equivalent and both total correctly
  (the compiler maps a cube measure's `count` to a `sum` re-aggregation - it never "counts
  the cells"). This is why `cube.md`'s additive table shows a `count(*)` column
  re-aggregating by `sum`.
- **ratio measure** (`ratio` required): `{ num: <measure key>, den: <measure key> }` - a
  ratio of two other declared measures, recomputed correctly under filters (never a stored
  pre-divided average); each side may optionally set `num_scope`/`den_scope: all` to divide
  by the unfiltered total instead of the filtered one. Optional `label` (<=80), `unit`, `intent`.
  This is how a `cube` carries a rate/percentage, **and it is the only exact way a `cube`
  carries an AVERAGE**: `num` = the sum measure, `den` = a `count(*)` measure, which makes the
  tile exactly sum divided by count - the true weighted mean over the source rows, correct under
  every filter. Averaging a cube's cells directly (`data-agg: avg`) is rejected, because each
  cell is already a group total; see `dashboard.md`.

**unit** (optional, on any measure) - controls display, never the stored value:
`{ kind: currency|percent|count|number, ... }`. `currency` REQUIRES `scale` (`cents` or
`units`) + takes an optional uppercase 3-letter `currency` code (`^[A-Z]{3}$`, e.g. `USD`);
`percent` REQUIRES `scale` (`fraction` for
0..1, `points` for 0..100); `count`/`number` take no `scale`. Optional `decimals` (0-6),
`compact`. Pick `scale` to match what your SQL emits - if the column is already dollars use
`units`, if it is integer cents use `cents`; the wrong scale is a 100x display error the
format cannot catch (it is a display choice, not a structural fault).

## tiles

A closed set of eighteen types; `type` is REQUIRED (a role-less tile is a `[L2]` error - it can
never blank-render). Some optional fields are common but are NOT on every type - each tile's
schema is closed, so an unaccepted key is a `[L2]` error naming it:

- `intent` and `w` (1-12 grid columns) are accepted on **all eighteen** types.
- `dataset` (which dataset it reads; omit = the first/default) on all EXCEPT `text` (it has
  no data) and `custom` (which names its datasets in `reads` instead).
- `title` (<=120 chars) and `note` (<=1000) on `kpi` / `chart` / `table` / `matrix` / `heatmap` / `scatter` / `treemap` / `waterfall` / `funnel` / `drilldown` / `stacked` / `combo` / `pie` / `donut` / `gauge` / `custom` only (NOT on `filter` or `text`).
- `title` (<=120 chars) and `note` (<=1000) on `kpi` / `chart` / `table` / `matrix` / `heatmap` / `scatter` / `treemap` / `drilldown` / `stacked` / `combo` / `pie` / `donut` / `gauge` / `custom` only (NOT on `filter` or `text`).

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
| `heatmap` | `rows`, `cols`, `measure` | The matrix with a colour scale. Every `matrix` field means the same thing here; the only difference is that `color` defaults to `heat` instead of off. See "The heatmap" below. || `scatter` | `point`, `x_measure`, `y_measure` | An AGGREGATE scatter: one point per member of `point` (a dimension), positioned by two measures. `x_measure` and `y_measure` are DIFFERENT declared agg measures (not ratios). Optional `limit` (1-2000, plotted points; default 500), `height` (120-800), `drill`. See "The scatter and the treemap" below. |
| `treemap` | `x`, `measure` | One rectangle per member of `x` (a dimension), its AREA being that member's share of the total. `measure` must DECOMPOSE - `sum` or `count` only. Optional `limit` (1-200, rectangles; default 24), `height` (120-800), `drill`. See below. |

| `stacked` | `x`, `series`, `measure` | A stacked column or area: `x` (a dimension), `series` (a DIFFERENT dimension whose values are the segments, at most 5 declared `domains`), `measure` (one measure key, which must be a `sum` or a `count` - see "Stacked charts" below). Optional `stack` (`normal` (default) / `percent` for the 100% stack), `chart` (`bar` (default) / `area`), `limit` (1-400 x categories; default 60), `height` (120-800). |
| `combo` | `x`, `measure`, `measure2` | A dual-axis chart: `x` (a dimension), `measure` on the LEFT axis and `measure2` on the RIGHT, two DIFFERENT measure keys (either may be a `ratio`). Optional `chart` (`bar` (default) / `line` / `area`), `chart2` (`line` (default) / `bar` / `area`), `axis_sync` (boolean - put both on one shared scale), `limit` (1-400), `height` (120-800). See "Dual-axis (combo) charts" below. |
| `pie` / `donut` | `x`, `measure` | A share of a whole. `x` is the slice dimension (at most 5 members); `measure` must be ADDITIVE (`sum`/`count`) - a ratio, a `min`/`max` or any non-additive aggregate is refused, because its parts do not add up to its whole. Optional `height` (120-800). No `limit`: a wider dimension is refused, not truncated. `pie` and `donut` differ only in the hole. See "Pie, donut and gauge" below. |
| `gauge` | `measure`, `max` | One value against a declared scale. `max` is required (and > `min`); optional `min` (default 0), `target` (must lie within the scale, marked on the arc), `height` (120-800). A ratio measure is allowed here. See "Pie, donut and gauge" below. |
| `waterfall` | `x`, `measure` | Contributions that build to a total: each bar starts where the previous ended, closed by the total. `measure` must DECOMPOSE - `sum` or `count` only. Optional `limit` (1-200, contribution bars; default 40), `height` (120-800), `drill`. See "The waterfall and the funnel" below. |
| `funnel` | `x`, `measure`, `stages` | Stage sizes in an order YOU declare: `stages` lists the dimension VALUES, 2-12, no repeats. It shows sizes only - it does NOT compute conversion between stages. Optional `height` (120-800), `drill`. See below. |
| `filter` | `dimension` | `dimension`; `label` (<=80); optional `multi` / `range` (booleans, mutually exclusive - set at most one; a filter is single-select when neither is set). A `multi`/`range` filter on a non-composable measure needs a `hybrid` dataset (Steps 1-3). |
| `text` | `body` | `body` (markdown, <=4000) - static prose, no data. |
| `custom` | `reads` | Escape hatch 1 (below). |

## The matrix

The pivot table - two dimensions crossed, one measure per cell, with row totals, column
totals and a grand total. It needs no new SQL and no new dataset shape: whatever cube or
lattice you already wrote for the KPIs answers it.

```yaml
- type: matrix
  rows: region        # the row axis (a dimension of this tile's dataset)
  cols: month         # the column axis (a DIFFERENT dimension)
  measure: customers  # one measure per cell
  subtotals: both     # both (default) | row | col | none
  title: Customers by region and month
```

Two things worth knowing, because they change what you can put in one:

- **Every total is the measure RE-EVALUATED at that total's grain, never a sum of the cells
  on screen.** On a `lattice` (or a `hybrid`'s lattice half) the `GROUP BY CUBE` already
  precomputed the row-only, column-only and all-rolled-up grouping sets, so the matrix looks
  each one up. That means **a distinct-count or median subtotal is EXACT** - the thing
  Tableau and Power BI cannot answer off a pre-aggregate - and it means truncating a long
  axis cannot corrupt a total (the tile truncates at 200 rows / 100 columns and says so).
- **Two blanks that mean different things.** An empty body cell means there are no rows at
  that intersection (the usual pivot convention). A `-` means the value cannot be shown
  exactly. If the DATASET cannot answer the tile at all, the whole tile refuses with the
  reason instead of filling itself with dashes.

Rules the validator enforces, so none of these can reach a published dashboard:

- `rows` and `cols` must be declared dimensions of the tile's dataset, and must differ.
- The dataset must be `cube`, `lattice` or `hybrid`. **A `rows` dataset cannot carry a
  matrix** (there is no row-level matrix renderer) - use `lattice` or `hybrid`.
- A ratio measure with `num_scope`/`den_scope: all` (percent of total) cannot go in a matrix:
  a cell has three totals - its row, its column and the grand - and the scope names none of
  them. Put that measure on a `kpi` instead.

A matrix over a `cube` dataset is fine and exact, because a `cube`'s measures are already
restricted to `sum`/`count`/`min`/`max` (or a ratio of them) - the aggregates that re-compose.
Reach for `lattice` the moment you want a non-additive measure (a distinct count, a median, a
true average) in the grid, since that is what makes its margins exact too.

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
share a resolver - so the axis, measure, percent-of-total and `rows`-dataset rules above all
apply unchanged.
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
Row-level data lives in a `rows` dataset, and a scatter cannot be built on one - the validator
refuses it and tells you so. There is no way to ask for it and get something that looks right
but is not.

Two more scatter rules, both refused at publish:

- `x_measure` and `y_measure` must be DIFFERENT measures. The same measure on both axes draws
  a perfect diagonal whatever the data says - every number in it exact, and the picture a lie.
- Both must be plain agg measures. A `ratio` measure cannot go on an axis (the markup carries
  one num/den pair and a scatter has two axes); put it on a `kpi`.

At view time, a point whose coordinate cannot be resolved exactly is **not plotted at all**,
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
- The dataset must be `cube`, `lattice` or `hybrid`, same as a matrix.

At view time it also refuses a negative value (an area cannot show one) and a total that is
not positive (there is no whole to be a part of). No percentage is drawn anywhere - the area
carries the proportion, and each rectangle is labelled with its own exact value.

## The drill-down

A ranked breakdown of one dimension, where each row can open the next level down. It needs no
new SQL and no new dataset shape: drilling asks for a DIFFERENT grouping set at a narrower
filter state, and a `GROUP BY CUBE` lattice already contains every one of them.

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
- **"Other" is RESOLVED, not subtracted.** It is the measure re-evaluated over the members you
  cut, not the total minus the rows on screen. For an additive measure the two agree; for a
  `min`/`max` measure only the first means anything. And for a NON-additive measure (a distinct
  count, a median, a true average) there is no honest residual at all - "distinct customers in
  Other" cannot be derived from anything on screen - so that row renders `-` and says why. The
  rows you DID show stay exact.
  If the breakdown does not add up to the total at all (a lattice missing a member at that
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
- The dataset must be `cube`, `lattice` or `hybrid`. **A `rows` dataset cannot carry a
  drill-down** (there is no row-level renderer) - use `lattice` or `hybrid`.
- A ratio measure with `num_scope`/`den_scope: all` (percent of total) cannot go in one: a row
  has three candidate denominators - the rows shown, the residual and the total - and the scope
  names none of them. Put that measure on a `kpi` instead.

Reach for `lattice` when you want a non-additive measure in the list: every member is then one
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

**Prefer `lattice` for a stacked chart, and the reason is not performance.** A stacked bar
needs two grains: the `(x, series)` grouping set for its segments and the `x`-only grouping
set for its total. A `GROUP BY CUBE` lattice contains BOTH, so the tile renders each column's
total from the precomputed cell rather than by adding up the segments - and it then **asserts
that the segments agree with that total**, refusing the tile with the reason if they do not.
Tableau and Power BI have no second grain to check against. A `cube` dataset has only one
grain, so on a cube there is nothing to check the total against; the tile is still exact for
an additive measure, but the verification is a lattice property. Say `mode: lattice` if you
want it.

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
the chart you would have drawn on its own. Any aggregate works on either side, including a
non-additive one - a combo never claims the two series make a whole, which is why it needs no
additivity rule.

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

Two shapes, three types. A `pie` / `donut` shows how ONE additive measure splits across a
small dimension; a `gauge` shows one number against a declared target.

```yaml
- type: donut          # or: pie - identical, the donut just has a hole
  x: channel           # the slice dimension (<= 5 members)
  measure: sessions    # one ADDITIVE measure (sum or count)
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

- **The measure must be ADDITIVE - `sum` or `count`.** This is stricter than everywhere else
  in the format, and the reason is that a pie claims its parts compose into its whole. A
  distinct count, a median, a percentile, a **min**, a **max** and a ratio can all be resolved
  exactly per slice and still not add up to anything: five exact regional medians do not
  compose into the overall median. So they are refused with the aggregate named. Show that
  measure on a `chart` (bar) instead, which compares values without claiming they compose.
- **At most 5 slices.** The mark palette is five colours wide (every one contrast-validated),
  so a sixth slice would repeat one and two members would read as one. If a dimension declares
  more than 5 `domains` the spec is rejected; if it turns out wider at refresh, the tile
  refuses and says so. There is no top-N and no "Other" slice - use a bar chart, or filter the
  dimension down.
- **The dataset must be `cube`, `lattice` or `hybrid`,** never `rows` (there is no row-level
  radial renderer).

**What a pie shows, and what it deliberately does not.** Each slice states its own value and
the tile states the TOTAL - in the hole for a donut, in the legend for a pie. It never prints a
percentage. That is not an omission: a rendered "24%" is a number the renderer would have
divided into existence, and the wedge already carries the proportion exactly. The same rule is
why a gauge shows the value and the target but no "% of target".

**Why the total is worth trusting.** It is resolved SEPARATELY - the dataset's own precomputed
rolled-up figure for the current filters - not by adding up the slices being drawn. So if
anything cannot be shown, the circle is left visibly OPEN and the tile says why, instead of the
remaining wedges quietly growing to fill it. On a well-formed dataset this never happens and
the circle closes.

**Gauge specifics.** `max` is required and has no default: deriving one from the value would
make the picture a function of the number it is describing. A value outside `min..max` pins the
arc to its end and says so - the printed figure stays exact, and the note tells the reader which
to trust. A value that cannot be resolved exactly draws no arc at all and prints `-`, never a
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

**A waterfall is additive only, and it is all-or-nothing.** Its bars claim to compose into its
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

## The two escape hatches

1. **`type: custom` tile** - a bespoke visual the built-in tiles cannot express. Required
   `reads: [<dataset name>, ...]` (1-8 datasets it consumes) plus `html` (<=100000) and/or
   `js` (<=200000). The runtime mounts your HTML/JS with a read-only view of the declared
   datasets; refresh integrity still holds because the island provably carries what `reads`
   declares. Use it for a custom chart or layout for ONE tile, not to bypass the whole
   template.
2. **`look` (whole-look escape hatch, v1.1)** - a fully bespoke dashboard body, declared right
   in the spec as ONE of two forms (mutually exclusive with each other, and both mutually
   exclusive with `tiles`/`theme`/`layout`):
   - `look: { html: <string> }` (<=4 MiB) - the body inline, byte-verbatim.
   - `look: { from: <slug> }` - REFERENCES the CURRENT published body of the publish target
     instead of inlining it. `from` MUST equal the `path` slug you are publishing to (a
     `[identity]` error at `/look/from` otherwise - "keep the current body" only ever means the
     body of the dashboard you are publishing, never a different one). The server resolves the
     body from storage at compile/dry-run time and re-seeds its island, so the compiled output
     is byte-identical to inlining that same body via `{ html }` - but the body itself never
     round-trips through you, so the spec you send and the stored `spec_hash` stay ~KB instead
     of however large the body is. A target slug with no existing published body has nothing to
     keep (also a `[identity]` error at `/look/from`) - publish an initial body first with
     `{ html }`, or inline it directly. `derive_dashboard_spec` emits `{ from }` by default (see
     Step 7 in `SKILL.md`), which is why a derived draft stays small; to hand-edit the markup
     instead, `get_dashboard` the body, edit it, and publish `{ html }`.

   `datasets` and `source` are declared exactly as normal either way, so the compiler still
   compiles the refresh manifest and SEEDS it live - `look` only replaces the managed `tiles`
   markup with your own body. Two rules the compiler enforces on the resolved body (whichever
   form produced it): it must carry EXACTLY ONE `<script id="dashies-data">` data island (zero =
   nothing to refresh into; two or more would let the runtime/cron silently read only the
   first), and every byte OUTSIDE that island is preserved verbatim - the compiler splices only
   the freshly-seeded island JSON into it, touching nothing else in your markup. Any `data-dash`
   bindings in your body still have to resolve against the compiled manifest (the same `#555`
   cross-namespace consistency check a legacy HTML publish enforces). Author the body itself
   using the `data-dash` markup / data-island / custom-renderer conventions in
   `references/dashboard.md`; `look` is what lets that body ride the spec's compile + validate +
   seed pipeline instead of a raw `body` + `source_config` publish. Reach for it only when the
   managed template + a `custom` tile genuinely cannot do it, or when migrating an existing
   hand-authored dashboard - the `derive_dashboard_spec` MCP tool reconstructs exactly this shape
   from one of your own refreshable dashboards (see Step 7 in `SKILL.md`). The 4 MiB cap applies
   to the resolved body regardless of which form produced it: a `{ from }` reference is
   re-validated against the same `look.html` size limit once its body is resolved, so a legacy
   dashboard whose body exceeds 4 MiB cannot be kept via `{ from }` either (it fails with the
   same pointered `[L2]` error at `/look/html`). What `{ from }` saves is the round-trip - a
   body under the cap is referenced, not re-uploaded - not an exemption from the cap; a
   dashboard whose body is genuinely too large for either form has to stay on the legacy
   `body` + `source_config` path.

## Worked example (minimal cube)

```yaml
dashies: 1
title: Signups
slug: signups
source:
  connection: self
  schedule: daily
datasets:
  main:
    mode: cube
    sql: >
      select date_trunc('day', created_at)::date as day, count(*) as signups
      from users group by 1
    dimensions:
      day: { type: date }
    measures:
      signups: { agg: count }
tiles:
  - type: kpi
    measure: signups
    title: Total signups
  - type: chart
    chart: line
    x: day
    measure: signups
    title: Signups per day
```

For a multi-dataset report (a KPI strip + a distinct-count lattice trend + a row-level
table), declare each grain as its own dataset and route each data tile with `dataset:` - the
same `mode` choice per dataset (Steps 1-3), several datasets under one `source`.

## Publish + edit

Once the spec is written, go to Step 6 (dry-run then publish) in `SKILL.md`. To CHANGE a
published dashboard later, Step 7: `get_dashboard_spec` reads the stored spec back verbatim,
you edit one field, and republish the same `path` with `base_spec_hash` (the lost-update
guard). You never hand-edit the served HTML. If the dashboard has no stored spec yet, Step 7
also covers `derive_dashboard_spec`, which reconstructs one from an existing refreshable
dashboard.
