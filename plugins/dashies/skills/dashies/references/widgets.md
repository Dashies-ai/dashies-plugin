# Widgets: the charts the runtime draws for you (Step 4)

A widget is an element of your page that carries `data-dash`. The runtime draws it from the numbers
Dashies works out, under the page's filters, and draws it again on every filter change and every
refresh. **You write the element and its attributes; you never write its numbers.** It sits in your
markup exactly where you put it, and it takes your page's CSS through the style contract
(`references/style.md`). The same runtime draws a widget on every connection: the sample data, a
warehouse and an uploaded file alike, and where a rule below depends on the connection, it says so.

**Prefer a widget wherever one draws what you need**, and write page code (`dashies.data`, with the
recipes in `references/charts.md`) for what no widget draws. A widget already handles every filter,
every state of its data, the exact totals and the refusals its picture needs, and it cannot show a
figure Dashies did not deliver. Page code has to do each of those by hand, and publish reads it line by
line against `SKILL.md` rule 1. One page can carry both, side by side.

## What a page with widgets carries

- **The data block**, `<script type="application/json" id="dashies-data">{}</script>`, exactly once,
  above any script that calls `dashies.data`. Publish fills it; `{}` is all you write.
- **The runtime marker**, `<script data-dashies-runtime></script>`. It is what draws every widget, and a
  page carrying any `data-dash` without it is refused at publish, because those widgets would ship with
  frozen numbers.
- **The widgets themselves**, anywhere in your markup.

```html
<script type="application/json" id="dashies-data">{}</script>
<header class="top">
  <h1>Orders</h1>
  <p>Updated <span data-dash="updated-at"></span></p>
  <div data-dash="filter" data-dim="region" data-label="Region"></div>
</header>
<section class="cards">
  <div class="card" data-dash="metric" data-measure="revenue">
    <span class="label">Revenue</span><span class="value" data-dash-value></span>
  </div>
  <div class="card" data-dash="metric" data-num="revenue" data-den="orders" data-format="currency">
    <span class="label">Average order</span><span class="value" data-dash-value></span>
  </div>
</section>
<div class="panel" data-dash="chart" data-type="line" data-x="month" data-measure="revenue"></div>
<div class="panel" data-dash="table" data-group="region" data-columns="revenue,orders"
     data-sort="revenue:desc"></div>
<script data-dashies-runtime></script>
```

That page reads the worked example's dataset in `references/spec.md`: `month` and `region`, and the
measures `revenue` and `orders`. The second card divides them under every filter, which is how a
widget shows a `ratio` (below).

## What publish checks, and what waits until the page draws

**Publish checks every name a widget uses, with one gap worth knowing.** Each attribute that names a
measure (`data-measure`, `data-measures`, `data-measure2`, `data-num`, `data-den`, `data-num2`,
`data-den2`, `data-x-measure`, `data-y-measure`), a dimension (`data-x`, `data-dim`, `data-group`,
`data-series`, `data-rows`, `data-cols`, `data-point`, `data-levels`), a table column (`data-columns`)
or a dataset (`data-dataset`, `data-drill`) has to name one the spec declares, or the publish is
refused naming the attribute. **The gap: on a warehouse or uploaded-file dataset, and on some
sample-connection datasets, publish also accepts any column the dataset's statement returns where a
widget names a measure or a dimension**, except in a table's `data-group`, `data-columns` and
`data-sort`, which take declared names only. So a chart naming `amount`, the column the measure
`revenue` reads, publishes there as readily as one naming `revenue`. Name a measure by its own key,
never by the column it reads.

A table's `data-group`, `data-columns` and `data-sort` are checked against the rules under **The
table**. A measure a widget draws cannot be declared `scale: cents` or `scale: points`, because a
widget is handed the raw value; divide in the SQL and declare `scale: units` or `scale: fraction`
for it (`references/spec.md`, under `unit`). On some datasets a `data-agg` the dataset cannot answer
is refused. A chart carrying both several series and `data-controls` is a warning.

**Everything else is decided when the page draws, which is most of what "Each role" below
describes**; the rules there that publish checks, the table's, say so. A widget that cannot draw what
it was asked for says why in its own place on the page - "Too many series", "select a single Month to
compare against", a measure that cannot be shown as a share - and never draws a plausible wrong
picture in its stead. Publish does not draw the page, so read a role's rules before you write it
rather than after a viewer meets the sentence.

## Routing: `data-dataset`

`data-dataset` names the dataset a widget reads. Leave it off and the widget reads the first dataset
the spec declares. A name the spec does not declare is refused at publish.

## Roles

`data-dash` names what a widget is. Seventeen roles, and every other attribute below is read by some of
them and ignored by the rest.

| Role | Requires | What it draws |
|---|---|---|
| `metric` | `data-measure`, or `data-num` and `data-den` | One figure. |
| `chart` | `data-x`, and `data-measure` or `data-measures` | Bars, horizontal bars, a line or an area (`data-type`). |
| `table` | nothing | The dataset's rows as a table, or rolled up by one dimension. |
| `matrix` | `data-rows`, `data-cols`, `data-measure` | A cross-tab of two dimensions, with exact totals. |
| `heatmap` | `data-rows`, `data-cols`, `data-measure` | The matrix with a colour scale. |
| `scatter` | `data-point`, `data-x-measure`, `data-y-measure` | One point per member, placed by two measures. |
| `treemap` | `data-x`, `data-measure` | Part of a whole, by rectangle area. |
| `waterfall` | `data-x`, `data-measure` | Contributions that build to a total. |
| `funnel` | `data-x`, `data-measure`, `data-stages` | Stage sizes, in the order you declare. |
| `drilldown` | `data-levels`, `data-measure` | A ranked breakdown a viewer can descend, one level per click. |
| `stacked` | `data-x`, `data-series`, `data-measure` | Stacked bars or areas, normal or 100 percent. |
| `combo` | `data-x`, `data-measure`, `data-measure2` | Two measures on two axes. |
| `pie` | `data-x`, `data-measure` | Share of a whole. |
| `donut` | `data-x`, `data-measure` | The same, with the total in the hole. |
| `gauge` | `data-measure`, `data-max` | One figure against a declared scale. |
| `filter` | `data-dim` | A control over one dimension, which filters the whole page. |
| `updated-at` | nothing | When the dashboard's data was last refreshed. |

## Naming what a widget shows

| Attribute | Value | Read by |
|---|---|---|
| `data-measure` | a measure key | Every role that shows a figure. It names an aggregate measure, never a `ratio`. |
| `data-num`, `data-den` | measure keys | A `ratio`, in place of `data-measure`: the widget divides the two under the current filters, never from a stored figure. Name the two measures the `ratio` you declared divides. |
| `data-num-scope`, `data-den-scope` | `all` | Takes that side of the ratio from the unfiltered dataset, which is how a share of the total is drawn. |
| `data-measures` | two to four measure keys, comma-separated | `chart`: one series per measure, at the same `data-x`. |
| `data-measure2` | a measure key | `combo`: the right-hand axis. |
| `data-num2`, `data-den2` | measure keys | `combo`: a ratio on the right-hand axis. |
| `data-x-measure`, `data-y-measure` | measure keys | `scatter`: the two axes, two DIFFERENT aggregate measures. |
| `data-agg` | an aggregate name | An override of the measure's aggregate. Leave it off and the declared aggregate is drawn. An override naming an aggregate the dataset cannot answer is refused at publish on some datasets, and drawn as `-` on others. |
| `data-x` | a dimension key | `chart`, `stacked`, `combo`, `treemap`, `waterfall`, `funnel`, `pie`, `donut`. |
| `data-rows`, `data-cols` | dimension keys | `matrix`, `heatmap`: the two axes, two DIFFERENT dimensions. |
| `data-point` | a dimension key | `scatter`: one point per member. |
| `data-levels` | one to six dimension keys, comma-separated | `drilldown`, outermost first, all different. |
| `data-series` | a dimension key | `chart`, beside one `data-measure`: one series per value. `stacked`: the segments. |
| `data-dim` | a dimension key | `filter`. |

**A `ratio` goes on a widget as its two operands.** A `ratio` you declared is worked out for page code
on every row, but no widget reads it by its own key: write `data-num` and `data-den` naming the two
measures it divides. A ratio draws on a `metric`, a `matrix`, a `heatmap`, a `drilldown`, either side of
a `combo`, and a `gauge`; every other role draws plain measures only. **Every one of them draws a ratio
as a percent unless `data-format` says otherwise** (`data-format2` on a combo's right side), whatever
the ratio's `unit` declares, so write `data-format` on a widget showing a ratio of another kind.

## Shape and size

| Attribute | Value | Read by |
|---|---|---|
| `data-type` | `bar`, `hbar`, `line`, `area` | `chart`. `stacked` takes `bar` (its default) or `area`; `combo` takes `bar` (its default), `line` or `area` for its left side. |
| `data-type2` | `line` (its default), `bar`, `area` | `combo`: the right side. |
| `data-stack` | `normal` (its default), `percent` | `stacked`: `percent` is the 100% stack. |
| `data-axis-sync` | present | `combo`: both measures on one shared scale. |
| `data-subtotals` | `both` (its default), `row`, `col`, `none` | `matrix`, `heatmap`. The token names the axis whose members get a total: `row` adds the Total column, `col` the Total row, and the grand total appears only under `both`. |
| `data-color` | `heat`, `diverging` | `matrix` (off unless set), `heatmap` (`heat` unless set). |
| `data-min`, `data-max`, `data-target` | numbers | `gauge`: the scale and an optional target mark. Numbers you write, never measure keys. `data-max` is required, `data-min` defaults to 0, and a target sits inside the scale. |
| `data-stages` | two to twelve dimension values, comma-separated | `funnel`, in the order it runs. |
| `data-top-n` | a number | `drilldown`: show only the top members by its measure. |
| `data-other` | present | `drilldown`, beside `data-top-n`: adds an exact row for every member left out. |
| `data-total` | present | `drilldown`: adds the total for the current filters. |
| `data-height` | a number of pixels | Every role that draws a chart. |
| `data-limit` | a whole number | How many members a widget draws before it stops and says so. See **Where a widget stops**. |
| `data-sort` | `value-desc` or `value-asc` on a `chart`; `<column>:asc` or `<column>:desc` on a `table` | The order, where the role takes one. |
| `data-columns` | column keys, comma-separated | `table`: the columns it draws, in the order written. |
| `data-group` | one dimension key | `table`: rolls the rows up by that dimension. |

## Display

| Attribute | Value | Read by |
|---|---|---|
| `data-label` | a string | `filter`: its visible label. |
| `data-format` | `currency`, `percent`, `integer`, `decimal`, `compact` | How a figure is drawn. `combo` reads `data-format2` for its right side. On `updated-at`, `absolute` draws the date and time instead of "3 hours ago". |
| `data-currency` | an ISO 4217 code | The currency of a `currency` figure. |
| `data-decimals` | 0 to 6 | Decimal places. |
| `data-dash-value` | present, on an element INSIDE a `metric` | Where the figure goes. Without one the metric replaces its own text, so a card that carries a label of yours puts the figure in a child marked `data-dash-value`. |

**Declare a figure's format on its measure, in the `unit`, and most widgets draw it.** A widget
drawing one measure - the table's columns included - draws it in the kind its `unit` declares
(currency, percent, a count) wherever Dashies carries the format with the data. Two kinds of dataset do
not carry it: where the publish report's `Datasets:` sentence says the answers are worked out for each
state its filters can be in, or that its filter combinations travel inside the page, a widget draws a
plain number unless it says otherwise. **And two shapes never take the `unit`:**

- **A ratio drawn through `data-num` and `data-den`** draws as a percent on every role that takes
  one, whatever the ratio's `unit` declares.
- **A `chart` with `data-measures`** draws plain numbers.

**`data-format` overrides all of that.** Write it where the data carries no format, on a widget
showing a ratio of any kind but a percent, on a chart with `data-measures` (where it covers every
series), and wherever a widget should draw a measure differently from its `unit`. Two roles differ: a
`table` reads no `data-format` at all, and a `scatter` applies its one `data-format` to both axes, so
leave it off a scatter whose two measures differ in kind. A `combo` reads `data-format2` for its right
side.

**Currency and decimal places are page-wide, not per measure.** No widget reads the currency code or
the decimal places a measure's `unit` declares. Every widget prints currency in one currency and
precision, which Dashies takes from the first currency measure the spec declares, so declare first the
currency measure whose currency and precision the page should print. `data-currency` and
`data-decimals` override that on every role that draws a figure but two: a `table` reads neither, and a
`chart` reads `data-currency` for its axis and neither for the values it prints. A `combo` reads one
`data-currency` and one `data-decimals` for both of its sides. A figure in a second currency, or at a
precision of its own, is drawn exactly by page code, where `dashies.format` reads each measure's own.

## Viewer controls

| Attribute | Value | Effect |
|---|---|---|
| `data-multi` | present | A `filter` that takes several values. |
| `data-range` | present | A `filter` over a `date` dimension becomes a from-and-to range. On any other dimension it is ignored. Write at most one of `data-multi` and `data-range`. |
| `data-controls` | `sort`, `limit`, or `sort,limit` | Live sort and top-N controls above a `table` or a one-measure `chart`, so a viewer can reorder it or show more. A chart over a `date` x gets no sort control, since time already orders it, and a chart with several series gets neither. |
| `data-widget` | an id: lower-case letters, digits, `-` and `_` | **Required with `data-controls`, and without it the controls are simply not drawn, with nothing at publish to say so.** It keys the viewer's choices in the page's state and in a shared link (`t:<id>.sort`, `t:<id>.n`), so give each controlled widget its own. |
| `data-xfilter` | present | A one-measure `bar` or `hbar` `chart`: clicking a bar filters the whole page to that member. |
| `data-drill` | a dataset name | A View detail button, on a widget that shows a value, which opens the records behind the number from that dataset, in a dialog. Every measure of that dataset is then drawn by a widget, so none of them can be `scale: cents` or `scale: points`. On sample data whose measures all add up, the dialog opens saying detail is not available, and publish says nothing. |

**A filter widget sets the same page state `dashies.filter` sets**, so the two are one mechanism: the
URL hash carries it, a shared link opens on it, and every widget and every subscription follows it. A
filter lists its dimension's members, in the order **Member order on an axis** gives. A widget whose
dataset does not declare a filtered dimension cannot follow that filter, and says so under itself.

## Time intelligence

Four attributes, on a `metric` only. On any other role the widget refuses with the reason.

| Attribute | Value |
|---|---|
| `data-timeintel` | the `date` dimension to walk |
| `data-compare` | `yoy`, `qoq`, `mom`, `pop`, `ytd`, `running`, `movavg` |
| `data-compare-as` | `pct` (its default), `delta`, `prior`, `current`, for the four that compare two periods |
| `data-window` | 2 to 1,000 periods, required by `movavg` |

`yoy`, `qoq` and `mom` compare the selected period with the one 12, 3 or 1 months before it; `pop` with
the previous period present in the data; `ytd` and `running` total up to and including it; `movavg`
averages the last `data-window` periods ending at it.

**It works on a warehouse or an uploaded-file dashboard. On sample data whose measures all add up, a
comparison is refused in the widget's place, on every view, and publish says nothing**; there, declare
the comparison as measures in the SQL instead - a prior period and a `ratio`, as the KPI recipe in
`references/charts.md` does.

**Every one needs a single period selected on that `date` dimension**, which is what it compares FROM:
with none, the metric reads "select a single" and the dimension's label, and draws no figure. So put a
single-select `filter` widget on the same dimension, or set its first value from your script
(`dashies.filter`). **And both periods have to have exact values**: where the earlier one is missing, the
metric says so rather than treating the gap as zero and reporting a confident change. A running or
to-date total needs a `sum` or `count` measure, because nothing else accumulates.

## Each role

What each role does with its data, including what it refuses. The refusals in this section happen when
the page draws, in the widget's own place.

### The metric

One figure: the measure, or the ratio of `data-num` over `data-den`, under the current filters. It
draws `-` where the value cannot be shown exactly, never a rounded-wrong number.

### The chart

`data-type` picks bars, horizontal bars, a line or an area over `data-x`. It draws one measure, or
several series in either of two ways: `data-measures` names two to four measures at the same `data-x`,
or `data-series` beside one `data-measure` splits it into one series per value. **Five series at most**:
on a warehouse or uploaded-file dataset a missing value is a series of its own, labelled `-`, and counts
toward the five, and past five the chart shows `Too many series: <dimension> has N values, max 5.` in
place of the chart. Split by a dimension with at most five values, or narrow it in the SQL. A chart of
one measure also takes `data-controls` and `data-xfilter`; a chart with several series takes neither.

### The table

`data-columns` lists the columns to draw, in order, each a dimension or measure the dataset declares
and none of them a `ratio`; a table cannot draw a column the SQL returns and the spec does not declare.
**Without `data-group`, the table rolls up to the dimensions it lists**: `data-columns="region,revenue"`
draws one row per region with its total. **With `data-group`**, it rolls the rows up by that one
dimension and draws it first, then the measures `data-columns` names, or every measure of the dataset
when there is no `data-columns`; a second dimension in `data-columns` beside `data-group` is refused at
publish, since it cannot be drawn without grouping by it too. With neither, it draws every dimension and
then every measure.

`data-sort` is `<column>:asc` or `<column>:desc`, where `<column>` is one the table's rows carry: its
group, a dimension it lists (any dimension when it lists none), or any measure that is not a `ratio`,
drawn or not. Publish refuses any other key, a chart's `value-desc`, and a direction other than `asc`
or `desc`. A grouped table with no `data-sort` is ordered by its group key, so its rows do not move
between refreshes.

**A table is for reading.** What a table costs is its cells, rows TIMES columns, so ask for the columns a
person will read and leave `data-limit` at its default (**Where a widget stops**). Do not raise it to
hold every row: a browser tab has a fixed ceiling, and a table that drains a large dataset into it is
how a page stops loading.

### The matrix and the heatmap

Two dimensions crossed, one figure per cell, with a total per row, per column and overall
(`data-subtotals`). It needs no dataset of its own: the dataset your other widgets read answers it, as
long as it declares both dimensions.

- **Every total is the measure worked out again at that total's grain, never a sum of the cells on
  screen.** So a distinct count's or a median's subtotal is exact, and cutting a long axis cannot
  corrupt a total.
- **Two blanks that mean different things.** An empty cell has no rows at that intersection; a `-`
  cannot be shown exactly.
- **A ratio that takes a side from the unfiltered total** (`data-num-scope` or `data-den-scope`) cannot
  go in one: a cell has three totals, its row's, its column's and the grand one, and the scope names none
  of them. Put it on a `metric`.
- **Bound both dimensions.** A matrix crosses them, so its cost is the product of their member counts.

`data-color` shades the cells. **`heat`** runs palest to deepest, for a quantity. **`diverging`** pivots at
ZERO, always, for a signed measure such as a margin or a variance; to diverge around anything else,
subtract it in the SQL so the measure is the deviation. The scale is worked out over the cells on
screen every time the view changes, and its legend prints both ends. Totals are never coloured, and a
cell with no exact value is drawn `-` on a hatch rather than given a colour on the scale.
`heatmap` is the matrix with `data-color` on by default.

### The scatter and the treemap

Both read one grouping, the one a bar chart of that dimension reads.

**The scatter is the AGGREGATE form**: one point per member of `data-point`, never one per source row,
and it says so in its own accessible name. `data-x-measure` and `data-y-measure` are two different
aggregate measures (the same one on both axes draws a perfect diagonal whatever the data says), and
neither may be a `ratio`. A point whose position cannot be worked out exactly is left off, and the
widget says how many; it is never placed at the origin.

**The treemap's whole is the dataset's own total, never the sum of its rectangles.** So when
`data-limit` shows the largest 20 of 137 members, the rest of the box stays empty rather than being
stretched to fill it, and the widget says so. Because area claims a part of a whole, its measure has to
be a `sum` or a `count`, never a `ratio`, and it refuses a negative value and a total that is not
positive. It draws no percentage: the area carries the share, and each rectangle carries its own value.

### The drill-down

A ranked breakdown of one dimension at a time, where each row opens the next level of `data-levels`.
One level is a plain top-N list.

- **Drilling filters the whole page.** A drilled member becomes an ordinary filter on that level's
  dimension, so every other widget follows it, the URL carries it, and Back undoes it.
- **The Other row (`data-other`) is worked out again, not subtracted**: the measure over the members you
  cut. For a measure whose parts do not add up (a distinct count, a median, an average) there is no
  honest residual, so that row reads `-` with the reason, and the rows shown stay exact.
- **The total (`data-total`) is worked out again too**, so cutting to the top five cannot corrupt it.
- `data-other` needs `data-top-n`, and a ratio that takes a side from the unfiltered total cannot go in
  one.
- It draws at most 200 members per level, so a `data-top-n` above 200 changes nothing. Use it to cut, not
  to widen.

### The stacked chart

One measure over `data-x`, split into the segments of `data-series`, which has at most 5 values.

- **The measure has to add up across the segments: a `sum` or a `count`.** A `ratio`, a `min`, a `max`,
  a distinct count, a median and a percentile are refused. To show a rate beside a stack, use a `combo`.
- **Where the dataset can answer both groupings, the widget checks its segments against each column's own
  total** and refuses the chart, saying why, if they disagree.
- **A negative segment is never stacked**: the same exact values are drawn as grouped bars instead, with a
  line saying why. A 100% stack refuses a column mixing positive and negative segments, and shows nothing
  for a column whose total is zero. These depend on the data, so they can change on a refresh: if the
  measure can go negative, prefer `normal` over `percent`.

### The combo chart

Two measures at one grain, `data-measure` against the left axis and `data-measure2` against the right.
Each side is exactly the chart of that measure alone, and either may be a ratio (`data-num` and
`data-den`, `data-num2` and `data-den2`). **Both axes are always drawn and labelled**, each in its own
format, the legend says which axis each measure reads against, and a note under the chart says whether
the two scales are comparable by height. `data-axis-sync` puts both on one scale; use it when they share
a unit. A ratio that takes a side from the unfiltered total cannot go on one.

### The pie, the donut and the gauge

**A pie or donut shows how ONE measure splits across a small dimension**, and three things decide
whether it can draw at all:

- **The measure's parts must add up to its whole: a `sum` or a `count`.** A distinct count, a median, a
  percentile, a `min`, a `max` and a ratio are each exact per slice and still do not compose, so they are
  refused. Use a bar chart, which compares values without claiming they make a whole.
- **At most 5 slices.** A slice's identity is its colour and the palette is five wide. There is no
  "Other" slice and no top N: a wider dimension is refused, not cut.
- **Each slice states its own value, and the widget states the total**, in the hole for a donut. The total
  is the dataset's own figure, not the slices added up, so if a slice cannot be shown the circle is left
  visibly open and the widget says why. No percentage is printed: the wedge carries the share.

**A gauge shows one figure against `data-min` to `data-max`**, with an optional `data-target`. A value
outside the scale pins the arc to its end and says so, while the printed figure stays exact; a value
that cannot be shown exactly draws no arc and prints `-`. A ratio is allowed here.

### The waterfall and the funnel

**A waterfall orders its own bars**: largest contribution first over a category, calendar order over a
date. Nothing in the page or the SQL changes that, so when the sequence is the point, use a funnel. Its
measure has to be a `sum` or a `count`, never a `ratio`. **If any one contribution cannot be shown
exactly, the whole chart is withheld**, because every later bar sits where the previous one ended, and
a step drawn as zero would read as "no change". Its Total bar is the dataset's own total, never the
bars added up.

**A funnel shows stage sizes in the order of `data-stages`. It does not compute conversion**: nothing in
the data shows that the stages are nested cohorts, so there is no percentage, and a ratio is refused. For a
conversion rate, declare a `ratio` whose numerator and denominator are yours and show it on a `metric`.
A stage the data says nothing about (most often a typo) reads `-`, never 0.

### The filter

One dimension (`data-dim`), single-select unless `data-multi` or `data-range` says otherwise, labelled by
`data-label`. See **Viewer controls**.

### The updated-at stamp

`<span data-dash="updated-at"></span>` receives the time the dashboard's data was last refreshed, as
"3 hours ago", or as a date and time with `data-format="absolute"`, the one attribute it reads.

## Member order on an axis

**Every widget puts a dimension's members in one order, the same order page code is handed rows in:**
the members the dimension declares in `domains`, in that order; then every other member, by its value
(a number column numerically, a text column by character code, so capitals come before lower case);
then the member with no value, where the widget draws one. It is the same on every connection, so
**`domains` is the one lever: declare it for the order you want.** Your statement's `ORDER BY` does not
decide it on any connection, and a member the data carries that `domains` does not list is never
dropped: it comes after the declared ones. The member-order rows were measured by drawing each widget
over rows that arrive in neither the declared order nor value order:

| Widget | A category dimension | A date dimension |
|---|---|---|
| `chart` (`data-x`), and its series | member order, unless `data-sort` | calendar order |
| `matrix`, `heatmap` | member order, on both axes | calendar order |
| `pie`, `donut` | member order | calendar order |
| `stacked`, `combo` | member order, on the x axis and the series | calendar order on the x axis |
| `filter`, and a `data-xfilter` selection | member order, listing every declared member even where no row carries it, and never the member with no value | calendar order |
| `table` with `data-group` | the rows' own order, unless `data-sort`: your SQL's on a dataset whose rows travel in the page, the order Dashies answers in on one it keeps | the rows' own order |
| `waterfall` | its own: largest contribution first | calendar order |
| `treemap` | its own: largest share first | its own: largest share first |
| `drilldown` | its own: ranked by its measure | its own: ranked by its measure |
| `funnel` | the `data-stages` you write | the `data-stages` you write |

**One exception, on a warehouse or uploaded-file dashboard:** a dimension whose column type Dashies
could not tell when you published - every sampled value empty, and no type from the warehouse - keeps
the order Dashies' answer arrives in, `domains` and all. Republish once the column carries values.

A `matrix` or `heatmap` cuts its rows from the FRONT of that order (`data-limit`), so `domains` decides
which members are on screen at all, not just their sequence; every total is still worked out over the
whole selection.

## Where a widget stops

Some widgets cap how much they draw even with no `data-limit`. Past the cap a widget cuts and says so,
naming the total it cut from ("the first 200 of 4,913 rows") - except a table, which says only how many
rows it shows, since counting the rest would cost a second pass over the data.

| Widget | Draws by default | `data-limit` can raise it to |
|---|---|---|
| `table` | 10,000 rows | anything, which is the reason to leave it alone (**The table**) |
| `matrix`, `heatmap` | 200 rows, 100 columns | 1,000 rows |
| `scatter` | 500 points | 2,000 |
| `treemap` | 24 rectangles | 200 |
| `waterfall` | 40 contribution bars | 200 |
| `drilldown` | 200 members per level | not raisable |
| `stacked`, `combo` | 60 positions on the x axis | 400 |
| `pie`, `donut` | 5 slices, and past that it refuses rather than cuts | not raisable |

A `chart` draws every member unless you give it a `data-limit`, which then keeps the first that many of
its order.

## What a widget cannot do

- **Show a figure Dashies did not deliver.** Every value a widget draws was worked out by Dashies under
  the page's filters, and where it cannot be exact the widget says so in place. That is why it is the
  first thing to reach for.
- **Reach anything outside Dashies.** A published dashboard is locked to Dashies' own origins, and the
  page around a widget is under the same lock: `SKILL.md` rule 2 has what it refuses.
- **Remember anything.** The page runs in an isolated origin with no cookies and no storage; a viewer's
  choices live in the URL hash, which is what makes a shared link open on the same view.
