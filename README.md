# Dashies plugin for Claude Code

Publish AI-built dashboards to a stable `dashies.xyz` URL and keep them refreshed
on a schedule - from inside Claude Code, with no tokens to paste.

This plugin bundles two things:

- **The `dashies` skill** - the authoring guide for building a *refreshable*
  Dashies dashboard (cube design, the data-island binding contract, the sandbox
  CSP, the `source_config` manifest). It is auto-discovered from
  `skills/dashies/SKILL.md`.
- **The Dashies publish MCP** - the remote MCP server at `mcp.dashies.xyz/mcp`,
  wired in `.mcp.json`. It exposes `publish_dashboard`, `update_dashboard`,
  `get_dashboard`, `delete_dashboard`, `list_dashboards`,
  `list_dashboard_versions`, and `restore_dashboard_version`.

## Install

In Claude Code:

```
/plugin marketplace add https://dashies.xyz/marketplace.json
/plugin install dashies@dashies
```

The first `/plugin install dashies@dashies` is `<plugin>@<marketplace>` - both are
named `dashies`.

**No tokens to paste.** The MCP uses OAuth 2.1 + PKCE with Dynamic Client
Registration. The first time you call a Dashies tool, Claude Code opens your
browser, you sign in with Google once, and the access token is stored in your OS
keychain. Tokens auto-refresh; you only re-auth on an explicit sign-out.

After installing, the MCP tools appear as `mcp__plugin_dashies_dashies__<tool>`
(plugin name + server name).

## What it is for

Dashies is a BI product without a chart-builder: your AI generates a
self-contained HTML dashboard plus the SQL that feeds it, and Dashies hosts it at
a public URL and re-runs the SQL on a schedule. See <https://dashies.xyz>.

## Maintainer note - publishing this plugin

The marketplace at `https://dashies.xyz/marketplace.json` points the plugin at a
**public GitHub repo** (it has to: a URL-served marketplace only downloads the one
JSON file, so it cannot use a relative plugin source). The single out-of-repo step
to make the install above resolve is:

1. Create a **public** GitHub repo named `dashies-plugin` under the
   `MickeyBinnoon` account.
2. Push the contents of this `dashies-plugin/` directory to its default branch.

That repo (`MickeyBinnoon/dashies-plugin`) is the `source.repo` in the served
marketplace manifest (`mcp/worker/marketplace.json` in the Dashies repo). If you
host it elsewhere, change that one field and redeploy `dashies-router`.
