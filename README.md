<div align="center">

# Dashies

**Publish AI-built dashboards to a shareable URL, then let them refresh themselves on a schedule - with no AI in the loop after the first build.**

A one-install plugin for [Claude Code](https://claude.com/claude-code), [Codex](https://developers.openai.com/codex), and [Cursor](https://cursor.com): the `dashies` authoring skill plus the Dashies publish MCP server, bundled together.

[Website](https://dashies.xyz) ·
[Marketplace](https://dashies.xyz/marketplace.json) ·
[MCP server](https://mcp.dashies.xyz/mcp) ·
[Report an issue](https://github.com/Dashies-ai/dashies-plugin/issues)

![License MIT](https://img.shields.io/badge/license-MIT-blue?style=flat-square)
![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-d97757?style=flat-square)
![Codex plugin](https://img.shields.io/badge/Codex-plugin-4F46E5?style=flat-square)
![Cursor plugin](https://img.shields.io/badge/Cursor-plugin-111111?style=flat-square)
![MCP server](https://img.shields.io/badge/MCP-server-3b82f6?style=flat-square)
![OAuth 2.1 PKCE + DCR](https://img.shields.io/badge/OAuth%202.1-PKCE%20%2B%20DCR-2563eb?style=flat-square)

</div>

---

## What it is

Dashies turns a Claude Code conversation into a published, self-contained BI dashboard at a stable URL: `https://dashies.xyz/<your-handle>/<slug>`.

You describe the dashboard. Claude builds it as a single HTML file (inline CSS, inline JS, embedded data) and publishes it with one MCP call. You get back a link you can share.

The part that makes Dashies different: **a dashboard can keep itself up to date.** When it is backed by a connected data source, Claude authors the dashboard plus a small JSON manifest (a cube of SQL, dimensions, and additive measures) exactly once. From then on a server-side cron re-runs that SQL on your chosen schedule and rewrites only the numbers in the dashboard's data island. The HTML is never touched again, and no model runs again.

> [!NOTE]
> Anyone can publish a dashboard. Scheduled auto-refresh is the flagship feature, and it requires the dashboard to be backed by a connected data source. A one-off static dashboard publishes fine - it just will not refresh on its own.

## Install

### Claude Code

Two commands inside Claude Code:

```text
/plugin marketplace add https://dashies.xyz/marketplace.json
/plugin install dashies@dashies
```

### Codex

Two commands in your shell:

```sh
codex plugin marketplace add Dashies-ai/dashies-plugin
codex plugin add dashies@dashies
```

If the marketplace clone fails on SSH host-key verification, use the explicit HTTPS URL: `codex plugin marketplace add https://github.com/Dashies-ai/dashies-plugin.git`.

### Cursor

Install Dashies from the [Cursor marketplace](https://cursor.com/marketplace) (Cursor 2.5+) - search **Dashies** under Customize -> Plugins, or run `/add-plugin` in the editor. _(Marketplace listing pending Cursor's review; until it lands, the one-click MCP below works today.)_

In every case, the plugin bundles the `dashies` authoring skill and wires up the Dashies MCP server, so there is nothing to configure by hand and no token to paste.

> [!TIP]
> This replaces the older manual MCP setup (`claude mcp add dashies ...` or `codex mcp add dashies --url ...`). If you ran that before, the plugin install supersedes it.

### Authentication: no tokens, ever

Dashies uses the standard MCP **OAuth 2.1 + PKCE** flow with **Dynamic Client Registration**. There are no API keys or tokens to copy, paste, or rotate. The first time you use a Dashies MCP tool, a browser opens for a one-click Google sign-in. The resulting access token is stored in your OS keychain and refreshes automatically; when it expires, the next tool call re-runs the one-click handshake.

### Using another AI tool?

This plugin makes Claude Code, Codex, and Cursor one-install paths, but Dashies is a plain remote MCP server, so any MCP-capable client can publish to it. Point your tool at the same URL - `https://mcp.dashies.xyz/mcp`:

- **Cursor (MCP only, no skill)** - prefer the one-install plugin above. For just the MCP, one-click **Add to Cursor** on [dashies.xyz](https://dashies.xyz), or add `{ "dashies": { "url": "https://mcp.dashies.xyz/mcp" } }` under `mcpServers` in `~/.cursor/mcp.json`.
- **Codex (MCP only, no skill)** - prefer the one-install plugin above. For just the MCP, run `codex mcp add dashies --url https://mcp.dashies.xyz/mcp`, then `codex mcp login dashies`.
- **Claude web, desktop, and Cowork** - add a custom connector for that URL under Settings -> Connectors.

The same one-click OAuth sign-in applies everywhere, with no token to paste. [dashies.xyz](https://dashies.xyz) has copy-paste setup for each tool.

## Quick start

Once installed, just ask:

```text
Publish a dashboard of last month's signups by plan.
```

Claude builds a self-contained HTML dashboard, calls `publish_dashboard`, and hands back a live URL:

```text
https://dashies.xyz/<your-handle>/signups-by-plan
```

That is the full loop: one request, one shareable link.

## How the no-AI refresh works

The model runs once, at authoring time. After that, refresh is pure server-side cron: it re-executes the saved SQL and writes the new numbers back into the published file's data island. The HTML, the layout, and the bindings stay untouched.

```mermaid
flowchart LR
    subgraph once["Authored once (AI in the loop)"]
      A["You describe the dashboard"] --> B["Claude builds HTML + manifest:<br/>cube SQL, dimensions,<br/>additive measures"]
      B --> C["publish_dashboard"]
    end
    C --> D[("dashies.xyz/your-handle/slug")]
    subgraph loop["On schedule (no AI)"]
      E["Cron fires:<br/>hourly / daily / weekly / monthly"] --> F["Re-run the saved cube SQL<br/>against your connected source"]
      F --> G["Write fresh numbers into<br/>the data island only"]
    end
    G --> D
```

Why this design holds up:

- **The HTML never changes after publish.** Refresh swaps data, not markup, so a dashboard cannot drift or break visually between runs.
- **No model is in the refresh path.** Lower cost, deterministic output, and no risk of an AI re-interpreting your dashboard differently each cycle.
- **The cube is the contract.** A low-cardinality grain plus additive measures is what lets the same SQL re-aggregate forever without re-authoring.

## Features

- **Publish in one call.** A self-contained HTML dashboard becomes a stable, shareable URL scoped to your handle.
- **Self-refreshing dashboards.** Pick hourly, daily, weekly, or monthly. The server re-runs your cube SQL and updates the numbers, with no AI in the loop.
- **Zero-token auth.** OAuth 2.1 + PKCE + Dynamic Client Registration. One browser click, keychain-stored, auto-refreshing.
- **Safe renames.** Renaming a dashboard preserves the old URL with a 301 redirect, so links you already shared keep working.
- **Versioned bodies.** Republishing snapshots the prior body automatically (up to 20 retained). List and roll back to any snapshot.
- **Sandboxed by design.** Published dashboards render under a strict sandbox CSP, isolated from the rest of the origin.
- **Guided authoring.** The bundled `dashies` skill walks you through the connected-data gate, cube design, the data-island binding contract, the sandbox constraints, schedule choice, and the manifest.

## What's bundled

### The `dashies` authoring skill

Loads automatically after install. It is the playbook for building a *refreshable* dashboard: the connected-database gate, designing a cube with a low-cardinality grain and additive measures, the data-island and data-dash binding contract, the inlined client runtime, the sandbox CSP constraints, choosing a schedule, and writing the `source_config` manifest.

### The MCP tools

OAuth triggers on first use of any tool below (one browser click).

| Tool | What it does |
|---|---|
| `publish_dashboard` | Upload a self-contained HTML / JSON / CSV / image file (up to ~5 MB) and get a stable URL back. |
| `update_dashboard` | Edit metadata (name, tags, chart, visibility) or rename the slug without re-uploading the body. Renames keep the old URL alive via a 301 redirect. |
| `get_dashboard` | Read back a previously published file. |
| `delete_dashboard` | Retire a dashboard by slug. The URL stops resolving and the bytes are removed. |
| `list_dashboards` | Enumerate your active dashboards, newest first, with cursor pagination. |
| `list_dashboard_versions` | List the saved prior body snapshots of one of your personal dashboards, each with a `version_id`. |
| `restore_dashboard_version` | Roll a personal dashboard back to a prior snapshot. The current body is snapshotted first, so the restore is normally reversible. |
| `get_dashboard_version` | Read back the body of a prior snapshot of a personal dashboard, to inspect or diff it before restoring. |
| `update_dashboard_version` | Set or clear a snapshot's label (a short name like "Before redesign"). Metadata only; the body is untouched. |
| `introspect_schema` | Inspect a connected data source's schema while authoring a cube - the built-in `self` metrics view, or a warehouse connection you own. |
| `validate_cube_sql` | Check a cube's SQL against a connection (`self` or a warehouse you own) before publishing a refreshable dashboard. |
| `list_connections` | List the warehouse connections you own - Postgres, BigQuery, or Snowflake (id, label, engine, status). Read-only, never returns secrets; warehouses are connected in the Dashies web app. |
| `get_refresh_status` | Check whether a personal dashboard is refreshing on schedule: cadence, next run, last run, and recent run history. Read-only. |
| `get_source_config` | Read back the stored refresh manifest (`source_config`) of a personal dashboard, exactly as saved. Read-only. |

## Build your first refreshable dashboard

A refreshable dashboard needs a connected data source, so the authoring flow starts there.

1. **Connect a data source.** Auto-refresh re-runs SQL against a live source, so this is the gate. Connect a warehouse - a Postgres database, a BigQuery project, or a Snowflake account - in the Dashies web app (the Connections page), credentials go through the app, never the AI - or build against Dashies' own built-in `self` metrics. Without a source you can still publish a static dashboard, but it will not refresh on its own.
2. **Ask Claude to build it.** For example: *"Build a refreshable dashboard of weekly active users by plan, and refresh it daily."* The `dashies` skill takes over from here.
3. **Design the cube.** Claude finds your connection with `list_connections`, uses `introspect_schema` to read its tables, then defines a cube: a low-cardinality grain (the dimensions you slice by) and additive measures (counts, sums) that can be re-aggregated safely every cycle.
4. **Validate the SQL.** `validate_cube_sql` confirms the cube runs against your source before anything is published.
5. **Publish with a schedule.** Claude calls `publish_dashboard` with the HTML plus the `source_config` manifest and your chosen cadence (hourly / daily / weekly / monthly). You get back `https://dashies.xyz/<your-handle>/<slug>`.
6. **Walk away.** The cron re-runs the cube SQL on schedule and writes fresh numbers into the data island. The dashboard stays current with no further AI involvement.

> [!TIP]
> For a one-off snapshot with no live data behind it, you do not need the cube or the manifest. Just ask Claude to publish a static dashboard - one `publish_dashboard` call and you have a URL.

<details>
<summary>Common follow-up requests</summary>

- **"What dashboards do I have?"** - Claude calls `list_dashboards` and summarizes them, newest first.
- **"Rename this dashboard."** - Claude calls `update_dashboard` with a new slug. The old URL 301-redirects to the new one, so shared links keep working.
- **"Roll this back."** - Claude calls `list_dashboard_versions` to find a snapshot, then `restore_dashboard_version` to restore it (personal dashboards only).
- **"Make it private."** - Claude calls `update_dashboard` with the visibility change; no re-upload needed.

</details>

## Links

- Home: https://dashies.xyz
- Marketplace manifest: https://dashies.xyz/marketplace.json
- MCP server: https://mcp.dashies.xyz/mcp
- Issues: https://github.com/Dashies-ai/dashies-plugin/issues

## License

[MIT](LICENSE).

---

<div align="center">

Built by [Dashies](https://dashies.xyz). Dashboards that keep themselves up to date.

</div>