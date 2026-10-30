---
name: omni-content-builder
description: Create, update, and manage Omni Analytics documents and dashboards programmatically — document lifecycle, drafts, tiles, visualizations, filters, controls, and layouts — using the Omni CLI. Use this skill whenever someone wants to build a dashboard, create a workbook or document, add tiles or charts, configure dashboard filters or controls, set up a KPI view, lay out or rearrange tiles and pages, edit a dashboard as a draft and publish it, change dashboard settings, rename/move/duplicate/delete a dashboard, modify dashboard-level model customizations like workbook-specific joins or fields, or build and edit an Omni app (custom HTML content in place of a dashboard) — including casual phrasings like "make a dashboard for…", "add a chart to…", or "clean up this dashboard's layout" that don't name the skill. Load it before any document API call, even when a local build script exists. For running a query or pulling metrics use omni-query; for adding a field to the shared model use omni-model-builder.
---

# Omni Content Builder

Create, update, and manage Omni documents, dashboards, and apps programmatically via the Omni CLI — document lifecycle, drafts, workbook models, filters, controls, and dashboard content.

> **Tip**: Use `omni-model-explorer` to understand available fields and `omni-content-explorer` to find existing dashboards to modify or learn from.

Documents are created and edited through the **v2 documents API** (`omni documents v2-*`) — an explicit envelope of `queryPresentations`, `controls`, `containers`, and `settings`, edited through a **draft → publish** flow.

## Design defaults

The mechanics here build a *correct* dashboard; for a *good* one, apply Omni's [Dashboarding Best Practices](https://docs.omni.co/guides/dashboards/dashboarding-best-practices). Its defaults apply when nobody has said otherwise. **They never override direction you have been given**: a requested layout, chart type, palette, or control placement wins; so does the convention of an existing dashboard you are editing or an org theme in force. When a request conflicts with a default, follow the request and, at most, mention the default once. The defaults: the answer top-left, 3–5 charts per page, functional color, the chart matched to the question, controls next to what they drive, a parent control for complexity, and charts that read without hovering. Each with its detail: [references/design-defaults.md](references/design-defaults.md).

For an operational or exec dashboard, also apply [references/dashboard-style.md](references/dashboard-style.md) (*Building dashboards people can act on*):

- **Order by what can still change.** At-risk before already lost; every list row names an owner.
- **Tables of 5 columns or fewer, with no truncated headers.** Otherwise use a markdown `{{#result}}` list row; size `limit` to the tile and check the PNG.
- **Every view drills.** Use `{{view.field.value}}` for names and key numbers in markdown; `.value_static` is display-only.
- **Relative dates everywhere** — on the date control and every tile filter; no month names in titles or labels.
- **One meaning per colour**, always with a text label; set single-series colours explicitly.
- **Fixed scope in tile filters**; 5 or fewer viewer controls.
- **A tile someone will alert on is a short categorical watchlist** (about 10 rows, filtered to the threshold), with the condition named in its subtitle.

## Known Issues & Safe Defaults

- **Always run the full validation loop before publishing** — see [Validation Loops](#validation-loops) below.
- **A tile reads back in the same shape you write.** `v2-get` / `v2-get-draft` return the inner vis config as `{ visType, config }`, so a tile can be edited and patched back as is, including for restores, duplicates, and moves. **Verify each tile you write**: read it back and run its query before publishing. See [references/documents-v2.md](references/documents-v2.md).
- **Patches merge by key; only `containers` (and the `order` arrays) are full replacements.** To change one tile, send just that key. To delete a tile, set its key to `null` AND remove it from `order`. When you send `containers`, send the complete layout tree with your edit applied; omit it to keep the layout and let the server auto-place added tiles.
- **New tiles are auto-placed when a create or patch carries no `containers`** — each dashboard-eligible tile goes on the first page. Send `containers` only to set the layout yourself, and then reference every tile that should be visible. See [references/containers.md](references/containers.md).
- **Tile `"1"` on create is merged into a server seed tile**, which keeps `automaticVis: true` even when you send `false` (tiles `"2"` onward keep `false`). If it matters, patch tile `"1"` again on a draft.
- **A control is shown only where a container places it.** To hide a control, leave it out of every container; it keeps applying its value. See [references/controls.md](references/controls.md#hiding-a-control).
- **Tile queries carry no `modelId`.** Don't send `modelId` or `model_extension_id` in a tile query; the server anchors tiles to the document's workbook model and rewrites any value you send with no warning. The other required query fields are listed in [references/documents-v2.md](references/documents-v2.md); leaving one out returns a 400 that names it.
- **HARD RULE — no non-topic tile from handed-over SQL without an explicit user decision.** Map each query to a topic first (see `omni-query`). If none fits, **stop and ask** whether to extend a topic or create one (on a branch via `omni-model-builder`, merged only with confirmation). Build a non-topic / `userEditedSQL` tile only after the user **explicitly chooses** that path (declined modeling, a genuine one-off, or `userEditedSQL` is required); Access Boost is never the default for handed-over SQL. See [Build queries on a topic](#build-queries-on-a-topic).
- **Non-topic tiles are invisible to Viewers and Restricted Queriers.** A tile with a populated `userEditedSQL`, or a bare base-view query with no `join_paths_from_topic_name`, is non-topic. Before finalizing one, **ask whether the dashboard's audience includes those roles**. If it does, **advise** Access Boost (it makes the tiles viewable on the dashboard only, for chosen users, groups, or the org; it needs the org capability and Manager on the document) as a separate, explicitly confirmed step with the **narrowest scope** that works. Never enable it without that go-ahead. See the *Raw-SQL tiles* recipe in [references/queryPresentations.md](references/queryPresentations.md) and **`omni-admin`** → *Document Permissions*.
- **`--body` overrides every shorthand flag; the workbook model ID changes with every draft and publish; boolean filters can drop when `pivots` is present.** [references/documents-v2.md](references/documents-v2.md#behaviors-to-design-around).
- **Chart configs by family:** which chart a question wants is in [references/design-defaults.md](references/design-defaults.md#match-chart-to-question) and how measures combine in one X/Y chart (fold, second axis, separate layers, facets) in [references/layers.md](references/layers.md#choosing-a-shape); classic cartesian in [references/visConfig.md](references/visConfig.md), layer-compiled in [references/layers.md](references/layers.md), KPI in [references/kpi-tiles.md](references/kpi-tiles.md), pie / heatmap / boxplot / funnel / sankey / map in [references/other-chart-types.md](references/other-chart-types.md), markdown and AI tiles in [references/markdown-tiles.md](references/markdown-tiles.md).
- **Rendering and caption pitfalls** — a blank markdown tile, "Item missing", "No chart available": [references/visConfig.md](references/visConfig.md#known-rendering-issues); a caption that shows a filter's value: [references/mustache.md](references/mustache.md#pitfalls).
- **`query.filters` needs the object form** — the relative-date shorthand (`"last 6 months"`) throws a 500; send `{type:"date", kind:"TIME_FOR_INTERVAL_DURATION", ui_type:"PAST", left_side, right_side}`. See [references/documents-v2.md](references/documents-v2.md).
- **X/Y charts made in the UI are layer-compiled; an API-made tile is classic until its config carries `behaviors.useLayerCompiler: true`.** The recipes in [references/visConfig.md](references/visConfig.md) are classic. For a layer chart, or to move a tile in place, follow [references/layers.md](references/layers.md): the flag, encodings per layer, same-axis same-mark measures folded into one Measure values layer (separate layers never stack), no hex string in `series[].color` (the tile silently reverts to classic).
- **Every query must include at least one measure** — a query with only dimensions produces empty/nonsense tiles (e.g., just months with no data).
- **Use `identifier` not `id`** — get a document's `identifier` from the `v2-create`/patch responses or `omni documents list` records.
- **Do not use `omni unstable documents-import` to update an existing dashboard** — import creates a new document and may drop newly-added tiles. Use the draft flow on the existing document.
- **Do not persist invalid query-level filters** — if `omni query run` returns a server-side parsing error for a tile query filter, validate the unfiltered base query once. Do not save that broken filter into the tile. If a dashboard-level control can satisfy the request, use that path and verify by readback; otherwise leave the dashboard unchanged and report the blocker.
- **Bound failed updates** — if a patch returns a validation error, stop after one corrected retry at most. Do not try repeated filter syntaxes or endpoint loops. Because edits happen on a draft, recovery is clean: **discard the draft** (`omni documents discard-draft <identifier>`) and report what was preserved — the published document was never touched. Full recovery steps: [references/updating-dashboards.md](references/updating-dashboards.md#recovery-rules).

## Prerequisites

```bash
# Verify the Omni CLI is installed — if not, ask the user to install it
# See: https://github.com/exploreomni/cli#readme
command -v omni >/dev/null || echo "ERROR: Omni CLI is not installed."

# Verify the CLI has the v2 documents commands — if not, ask the user to upgrade it
omni documents v2-get --help >/dev/null 2>&1 || echo "ERROR: CLI is too old for the v2 documents API — upgrade it."
```

```bash
# Show available profiles and select the appropriate one
omni config show
# If multiple profiles exist, ask the user which to use, then switch:
omni config use <profile-name>

# Confirm the active profile is authenticated and inspect your permissions:
omni whoami whoami
```

> **Auth**: if `whoami` or any call returns **401**, ask the user to run `! omni config login <profile>`. Profile setup, when you may run the login yourself, and `--schema`: the [**`omni-api-conventions`**](../../rules/omni-api-conventions.mdc) rule.

## Discovering Commands

```bash
omni documents --help              # Document operations (v2-* + lifecycle)
omni dashboards --help             # Dashboard downloads
omni models yaml-create --help     # Writing model YAML
omni documents v2-create --schema  # Body schema + example (add --depth 1 for an overview, --field PATH to drill in)
```

## Commands

**Build and edit documents with the `documents v2-*` commands — always.** The command for each task, and the document-management commands that have no v2 form (list, discard a draft, delete, move, duplicate, downloads, layout upgrade): [references/documents-v2.md](references/documents-v2.md#commands-by-task).

## Dashboard Architecture

Omni dashboards are built from **documents**. A document's v2 state is an envelope of four slices, `queryPresentations`, `controls`, `containers`, and `settings` (annotated in [references/documents-v2.md](references/documents-v2.md#envelope)):

- **Tiles** live in `queryPresentations.data`, keyed by record key (`"1"`, `"2"`, …); `order` is the tab order. **Tile keys must be NUMERIC strings** (`"1"`, `"42"`) — a descriptive key like `"revenue_kpi"` or `"probe"` is rejected with `400 … Invalid key in record`. Track the tile↔meaning mapping in your build script, not in the key.
- **Filters and interactive controls** are one map: `controls` (see [references/controls.md](references/controls.md)). **Unlike tile keys, control ids here ARE arbitrary strings** (`"date_filter"`, `"granularity"`) — don't carry that freedom over to tile keys, or vice-versa.
- **Layout** is the `containers` tree — a tile renders only where a container references it (see [references/containers.md](references/containers.md)).
- Each document also has a **workbook model** for per-dashboard model changes (see [references/workbook-model.md](references/workbook-model.md)).

A document is edited through **drafts** (see [Update Existing Dashboard](#update-existing-dashboard)), which can also be bound to a **model branch**: [references/branch-bound-drafts.md](references/branch-bound-drafts.md).

## Build queries on a topic

Build every tile's query **on a topic** whenever possible: set the query `table` to the topic's **base view** and pass `join_paths_from_topic_name: <topic>`, plus `topicName: <topic>` on the **presentation** (the presentation-level `topicName` is tile-specific — a standalone query has no equivalent). Joined-view fields then resolve through the topic's join map from the base view. The full shape, a worked example and how to verify it: **`omni-query`** → *Build queries on a topic*.

A tile not built on a topic still runs, but restricted queriers and viewers can't see it, and a Restricted Querier can't author one, so every tile you build as a Restricted Querier must be topic-based. Access Boost and raw-SQL tiles: [references/queryPresentations.md](references/queryPresentations.md#tiles-not-built-on-a-topic).

## Document Management

Create a document with `documents v2-create`, by name alone or with the full envelope (tiles, controls, settings) in one `--body`. Rename through a draft patch (`--name`, then publish). Delete, move, and duplicate with `documents delete` / `move` / `duplicate`; only published documents can be duplicated. Examples, the create-body key points, and the end-to-end build workflows: [references/document-lifecycle.md](references/document-lifecycle.md).

## Update Existing Dashboard

Edits go through the **draft flow**; the published dashboard is untouched until you publish. Read the document with `omni documents v2-get <identifier>` (find it first with `omni-content-explorer` or `omni documents list`), send only what changes with `omni documents v2-patch-draft <identifier> --body @patch.json` and a `summary`, and keep the returned `draftIdentifier`. Read the draft back with `v2-get-draft` and run the affected queries (see [Validation Loops](#validation-loops)), iterate with `v2-patch-draft-by-identifier`, then publish with `v2-publish-draft` and share the link (see [URL Patterns](#url-patterns)), or abandon the draft with `discard-draft`. Each step, the error map and recipes: **[references/updating-dashboards.md](references/updating-dashboards.md)**.

## Updating a Dashboard's Model

Dashboard-specific fields go in the document's **workbook model**, which extends the shared model. First decide where a new field belongs, based on your access (`omni whoami whoami --model-id <sharedModelId>`): a table calculation, a branch on the shared model, or this workbook model. Never write to the schema model. A field that exists only on an unmerged branch needs a [branch-bound draft](references/branch-bound-drafts.md). Write workbook-model YAML as the whole file read with `--mode combined`, sent with `"mode": "combined"`; a body holding only your new fields marks every field you left out as ignored. The decision steps, the `yaml-create` recipe, the order for building a tile on a new field, and how to verify it: [references/workbook-model.md](references/workbook-model.md).

## Dashboard Filters & Controls

Filters and interactive controls share one envelope slice: `controls: {data, order}`. Each entry is `{config, map}` — `config` holds the filter/control definition, `map` optionally scopes it per tile. Include them at create time or patch them in later (controls merge by key like tiles); a create-body example is in [references/controls.md](references/controls.md#filters-and-controls-in-a-create-body).

- The keys in `controls.data` are arbitrary IDs and must match `order`.
- **Filter shapes** (date / string / number / boolean, required) and **interactive controls** (field/timeframe switchers) are documented with examples in [references/controls.md](references/controls.md).
- **Every filter MUST include `fieldName`** with the fully qualified field name (no timeframe bracket for date filters), or it won't bind to any column.
- To reuse a filter from an existing dashboard, read it back with `omni documents v2-get`; its `controls` slice can go into a patch as is.

**Model it or control it?** Whether a filter belongs in the model as a filter-only field or on the dashboard as a control, including what a Restricted Querier can do: [references/controls.md](references/controls.md#model-it-or-control-it).

## Document Settings

`settings` is a shallow-merged object; patch only the keys you're changing. The keys and their values: [references/documents-v2.md](references/documents-v2.md#settings).

## Layout (containers)

The `containers` tree decides where tiles and controls render: a reserved `"filter-bar"` stack, then one `page` container per page, each holding a 24-column `grid` of tile stacks with `gridPosition {x,y,w,h}`. When to send it, and that it replaces the whole layout, are in Known Issues above. Multi-page dashboards, page switchers, grouped bands, in-tile controls, and sizing rules: [references/containers.md](references/containers.md).

## URL Patterns

After creating or finding content, always provide the user a direct link:

```
Dashboard: {OMNI_BASE_URL}/dashboards/{identifier}
Workbook:  {OMNI_BASE_URL}/w/{identifier}
Draft:     {OMNI_BASE_URL}/dashboards/{draftIdentifier}
```

The `identifier` comes from the `v2-create`/patch responses or `omni documents list`; the `draftIdentifier` comes from the `v2-patch-draft` response or `omni documents list-drafts`.
Replace `{OMNI_BASE_URL}` with the actual base URL from the active profile or
environment, normalized without a trailing slash. Do not return the literal
placeholder string unless credentials are unavailable and you explicitly say the
URL is a template.

## Validation Loops

Every build or update must be validated **before publishing**: broken tiles, bad field references, and misconfigured specs show "Chart unavailable" or "No data" with no API error.

1. **Validate the model** with `omni models validate <modelId>`.
2. **Test every query first** with `omni query run`, including the filters the dashboard will use.
3. **Check each viz spec**: `prefersChart: true`, the spec under `visConfig.visConfig.config`, and a `chartType` that matches its `visType` and `configType`. On a layer-compiled spec (`behaviors.useLayerCompiler: true`) also check that each `series[]` entry has its own `mark`, that stacked measures share one Measure values layer, and that no `series[].color` is a hex string.
4. **Verify the draft before publishing**: read it back with `v2-get-draft`, run each tile's query (`omni documents get-queries` + `omni query run`), and report each tile's status and row count.

What to check in each response, the full viz-spec table, the checklist, and an optional browser check with its own waiting rules: [references/validation-and-testing.md](references/validation-and-testing.md).

## Dashboard Downloads

Downloads are asynchronous: start one with `omni dashboards download`, poll `download-status` until the job reaches a terminal state, then fetch the file with `download-file`. Single-tile and data formats, the one-page limit on multi-page dashboards, and what "Job failed to render" means: [references/downloads.md](references/downloads.md).

## Docs Reference

Omni docs pages for documents, queries and charts: [references/docs-links.md](references/docs-links.md).

## Related Skills

- **omni-model-explorer** — understand available fields
- **omni-model-builder** — create shared model fields
- **omni-query** — test queries before adding to dashboards
- **omni-content-explorer** — find existing dashboards to learn from
- **omni-embed** — embed dashboards you've built in external apps
- **omni-admin** — scheduled deliveries, recipients and email-only users
