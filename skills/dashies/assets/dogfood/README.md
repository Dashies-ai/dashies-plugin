# Dogfood: "Dashies usage" refreshable dashboard

The reference refreshable dashboard authored with the `dashies` skill. It is the
canonical worked example: a fully self-contained, ready-to-publish dashboard plus
its refresh manifest, conforming to the runtime binding contract
(`web/dashboard-runtime/CONTRACT.md`, v1) and the FROZEN Manifest v1 in the skill.

It is committed but **not published yet**. PR3 (manifest-carrying publish +
`validate_cube_sql`) and PR4 (the refresh cron) are merged; the live publish just
waits on dashies-mcp finishing its deploy, and is coordinated by the team lead.

## Files

| File | What it is |
|---|---|
| `dashies-usage.html` | The fully-inlined dashboard: page markup with `data-dash` slots, the `#dashies-data` island (an initial **placeholder** cube), and the runtime inlined verbatim. Renders standalone with zero network and no storage. |
| `dashies-usage.manifest.json` | The `source_config` (Manifest v1): the real `cube_sql`, the grain, the additive measures, and the daily schedule. The cron reads this to rebuild the island. |

## Data source

`public.dashies_usage_metrics` (PR1) over the seeded `self` connection - a no-PII,
day-grain aggregate over `public.dashboards`. Columns: `day` plus eight additive
counts (`dashboards_published`, `public_count`, `private_count`, `active_count`,
`paused_count`, `failed_count`, `archived_count`, `scheduled_count`).

## Design notes

- **One dimension: `day` (a date).** That is the only thing to group/chart on, so
  the dashboard shows the trend and a per-day table rather than a filter dropdown
  of every date (the skill's "do not ship a high-cardinality filter" rule).
- **Every measure is an additive count** (`agg: sum`). The two share metrics
  (public share, scheduled share) are **not** stored; they render as `num/den`
  ratios (`data-num`/`data-den`), correct under any roll-up. This is the
  additive-vs-non-additive lesson made concrete.
- **`dimensions` + `measures` are byte-identical** between the manifest and the
  island (Manifest v1 invariant 5), so the cron can rebuild the island from
  `manifest + fresh rows`. The island measures carry the manifest's `additive`
  flag too; the runtime ignores unknown measure fields (CONTRACT.md s7), so this
  is contract-safe.
- **The embedded cube is a deterministic placeholder** (30 days, synthetic but
  internally consistent: `public + private == published`, the four status counts
  sum to `published`, `scheduled <= published`). The PR4 cron overwrites the
  island on run 1.

## Verified (headless, this artifact)

KPIs fill (Total published 102; status counts sum to 102; ratios render 70.6% /
43.1%), both charts draw, the table shows 14 rows, the freshness stamp renders
relative time, `localStorage.length === 0`, and the only network request is the
document itself (the runtime is inlined, nothing else is fetched).

## Publishing it (after PR3 + PR4 are live)

This is the publish step the skill's worked example points to. PR3's tools are
merged and the skill's tool signatures are final, so once dashies-mcp is deployed:

1. **Re-inline the current runtime.** The runtime bytes here are a point-in-time
   snapshot of `web/dashboard-runtime/runtime.js`. Re-inline the current file so
   the published copy is not stale (see the build note below).
2. **Validate the cube SQL** against the `self` connection (`validate_cube_sql`),
   confirm the returned columns equal the manifest's `dimensions` + `measures`
   keys, and paste the validated rows into the island in place of the placeholder.
3. **Publish** with `dashies-usage.manifest.json` as `source_config` (it carries
   `schedule: "daily"` - there is no separate frequency argument) and a slug such
   as `dashies-usage`.
4. **Confirm** it refreshes daily, slices client-side under `sandbox
   allow-scripts`, and uses no `localStorage`.

## Rebuilding the artifact

The HTML is assembled from page markup + a generated placeholder cube +
`runtime.js`. The build-time generator and template were scratch (not committed);
regenerate by re-inlining the current `web/dashboard-runtime/runtime.js` into the
markup and refreshing the cube rows. The HTML is the source of truth for the
published bytes.
