---
name: omni-content-builder
description: Create, update, and manage Omni Analytics documents and dashboards programmatically — document lifecycle, drafts, tiles, visualizations, filters, controls, and layouts — using the Omni CLI. Use this skill whenever someone wants to build a dashboard, create a workbook or document, add tiles or charts, configure dashboard filters or controls, set up a KPI view, lay out or rearrange tiles and pages, edit a dashboard as a draft and publish it, change dashboard settings, rename/move/duplicate/delete a dashboard, modify dashboard-level model customizations like workbook-specific joins or fields, or build and edit an Omni app (custom HTML content in place of a dashboard) — including casual phrasings like "make a dashboard for…", "add a chart to…", or "clean up this dashboard's layout" that don't name the skill. For running a query or pulling metrics use omni-query; for adding a field to the shared model use omni-model-builder.
---

# Omni Content Builder

Create, update, and manage Omni documents, dashboards, and apps programmatically via the Omni CLI — document lifecycle, drafts, workbook models, filters, controls, and dashboard content.

> **Tip**: Use `omni-model-explorer` to understand available fields and `omni-content-explorer` to find existing dashboards to modify or learn from.

Documents are created and edited through the **v2 documents API** (`omni documents v2-*`) — an explicit envelope of `queryPresentations`, `controls`, `containers`, and `settings`, edited through a **draft → publish** flow. This is the only path for building, reading, or changing a document — never fall back to the v1 `documents create`/`get` commands (v1 `put`/`update` were removed in CLI 1.2.2). A few document-management operations (list, delete, move, duplicate, downloads) have no v2 form; see [Commands](#commands) below.

## Design defaults

The mechanics here build a *correct* dashboard; for a *good* one, apply Omni's [Dashboarding Best Practices](https://docs.omni.co/guides/dashboards/dashboarding-best-practices). The bullets below are that guide's defaults for when nobody has said otherwise. **They never override direction you have been given**: a requested layout, chart type, palette, or control placement wins; so does the convention of an existing dashboard you are editing or an org theme in force. When a request conflicts with a default, follow the request and, at most, mention the default once. Without such direction, default to:

- **Lead with the answer, top-left.** Put the main KPI / answering chart in the upper-left — viewers scan in an F/Z pattern.
- **3–5 charts per page.** Beyond that, split across pages/tabs (see [containers.md](references/containers.md)).
- **Functional color, 90/10.** Neutral tones dominate; one accent for emphasis or status — not decoration.
- **Match chart to question** — trend → line/area/bar; ranking → horizontal bar; part-to-whole → 100% stacked; correlation → scatter.
- **Put controls next to what they drive,** with action-oriented labels ("Filter by Region", not "Region").
- **Hide complexity behind a parent control** — one control drives many; leave the child controls unplaced (see [controls.md](references/controls.md#parent-controls-one-control-drives-many)).
- **Charts read without hovering.** A viewer should get the key insight from the chart itself; a tooltip is a detail, not the message.

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
- **`--body` overrides the shorthand flags.** With `--body`, every shorthand flag (`--name`, `--summary`, `--branch-id`, …) is ignored with no warning. Put those fields in the JSON body of every create and patch; use flags without `--body` only when the flags are the whole request.
- **The workbook model ID changes with every draft and publish** — each draft copies the workbook model (extensions included), and publishing switches the document to that copy. Don't cache a workbook model ID; read `workbookModelId` from `v2-get-draft` (or `omni documents list-drafts <identifier>`) each time you need it.
- **Markdown tiles need `automaticVis: false`** — otherwise the renderer auto-derives a chart and the tile is blank. See [references/visConfig.md](references/visConfig.md); markdown KPI and card recipes are in [references/markdown-tiles.md](references/markdown-tiles.md).
- **Mustache: read a filter's value from `filters`.** To caption a tile with a filter's current value, use **`{{filters.…summary}}`**; the `controls` namespace is for field switchers, pickers, and Top-N controls, and renders **empty** for a filter. The `filters` key is `view.field` in a markdown-viz tile and the control `id` in a dashboard text tile. Tokens and scenarios: [references/mustache.md](references/mustache.md).
- **`query.filters` needs the object form** — the relative-date shorthand (`"last 6 months"`) throws a 500; send `{type:"date", kind:"TIME_FOR_INTERVAL_DURATION", ui_type:"PAST", left_side, right_side}`. See [references/documents-v2.md](references/documents-v2.md).
- **A tile with no real `visConfig` renders as "Item missing".** New tiles start with `visConfig.visType: null` and `automaticVis: false`, which draws nothing. Give each tile an explicit `visConfig` when the user asked for a specific chart or formatting (e.g. the table recipe in [references/visConfig.md](references/visConfig.md)), otherwise `automaticVis: true`. A create places every tile in `order`, so the fix is always in the tile's `visConfig`.
- **"No chart available"** means the inner config, `visType`, or `prefersChart` is wrong. For a requested chart, send the complete config from [references/visConfig.md](references/visConfig.md) under `visConfig.visConfig.config`; use `chartType: "table"` only as a deliberate fallback.
- **Every query must include at least one measure** — a query with only dimensions produces empty/nonsense tiles (e.g., just months with no data).
- **Boolean filters may be silently dropped** when a `pivots` array is present (reported Omni bug). If boolean filters aren't applying, remove the pivot and test again.
- **Use `identifier` not `id`** — get a document's `identifier` from the `v2-create`/patch responses or `omni documents list` records.
- **Do not use `omni unstable documents-import` to update an existing dashboard** — import creates a new document and may drop newly-added tiles. Use the draft flow on the existing document.
- **Do not persist invalid query-level filters** — if `omni query run` returns a server-side parsing error for a tile query filter, validate the unfiltered base query once. Do not save that broken filter into the tile. If a dashboard-level control can satisfy the request, use that path and verify by readback; otherwise leave the dashboard unchanged and report the blocker.
- **Bound failed updates** — if a patch returns a validation error, stop after one corrected retry at most. Do not try repeated filter syntaxes or endpoint loops. Because edits happen on a draft, recovery is clean: **discard the draft** (`omni documents discard-draft <identifier>`) and report what was preserved — the published document was never touched.

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

> **Tip**: Use `-o json` to force structured output for programmatic parsing, or `-o human` for readable tables. The default is `auto` (human in a TTY, JSON when piped). `--compact` strips indentation for piping.

## Commands

**Build and edit documents with the `documents v2-*` commands — always.** There is no situation where you reach back to the v1 `documents create`/`get` path to build, read, or change a document; the v2 draft flow covers all of it.

| Operation | Command |
|---|---|
| Create document | `documents v2-create` |
| Read document / draft state | `documents v2-get` / `v2-get-draft` |
| Edit document (tiles, controls, layout, settings, rename) | `documents v2-patch-draft` (+ `v2-patch-draft-by-identifier`) |
| Get the workbook model ID | `workbookModelId` on `documents v2-get` (published) or `v2-get-draft` (that draft's); also on `documents list-drafts` |
| Rename a document's identifier (slug) | `documents v2-update-identifier <identifier>` |
| Bind a tile to a query model, or unbind it | `documents v2-bind-query-model` / `v2-unbind-query-model` on a draft (CLI ≥ 1.1.2); see [references/documents-v2.md](references/documents-v2.md) |
| Publish a draft | `documents v2-publish-draft` |
| Read or edit an **app** (HTML instead of a dashboard) | `documents get-app` / `put-app` / `patch-app` / `remove-app` (+ the draft and auto-draft forms) — alpha, CLI ≥ 1.4.0; see [references/documents-v2.md](references/documents-v2.md) |

A handful of **document-management** operations have no v2 form — they aren't alternatives to the v2 build path, just the only command for that job: `documents list` / `list-drafts` (find documents and drafts), `documents discard-draft` (abandon a draft), `documents delete` / `move` / `duplicate` (lifecycle), `documents get-queries` (extract a tile's runnable query for validation), `dashboards download` / `download-status`, and `models yaml-create` / `validate` (model writes).

## Dashboard Architecture

Omni dashboards are built from **documents**. A document's v2 state is an envelope of four slices, `queryPresentations`, `controls`, `containers`, and `settings` (annotated in [references/documents-v2.md](references/documents-v2.md#envelope)):

- **Tiles** live in `queryPresentations.data`, keyed by record key (`"1"`, `"2"`, …); `order` is the tab order. **Tile keys must be NUMERIC strings** (`"1"`, `"42"`) — a descriptive key like `"revenue_kpi"` or `"probe"` is rejected with `400 … Invalid key in record`. Track the tile↔meaning mapping in your build script, not in the key.
- **Filters and interactive controls** are one map: `controls` (see [references/controls.md](references/controls.md)). **Unlike tile keys, control ids here ARE arbitrary strings** (`"date_filter"`, `"granularity"`) — don't carry that freedom over to tile keys, or vice-versa.
- **Layout** is the `containers` tree — a tile renders only where a container references it (see [references/containers.md](references/containers.md)).
- Each document also has a **workbook model** for per-dashboard model changes (see [references/workbook-model.md](references/workbook-model.md)).

A document is edited through **drafts**: `v2-patch-draft` creates a draft and applies your patch; the published document is untouched until `v2-publish-draft`. `v2-get` returns the published state. `v2-get-draft` returns a draft's state, as does `v2-get` given the draft's own identifier (the response's `draftOf` names the document). Drafts can also be bound to a **model branch** (see [references/branch-bound-drafts.md](references/branch-bound-drafts.md)).

## Build queries on a topic

Build every tile's query **on a topic** whenever possible: set the query `table` to the topic's **base view** and pass `join_paths_from_topic_name: <topic>`, plus `topicName: <topic>` on the **presentation** (the presentation-level `topicName` is tile-specific — a standalone query has no equivalent). Joined-view fields then resolve through the topic's join map from the base view. For the full shape — how the join map reaches joined-view fields, the worked example, and verifying with `omni models get-topic` (`base_view_name`/`join_via_map`) — see **`omni-query`**'s *Build queries on a topic*.

A tile **not** built on a topic still runs (a bare base-view query or a raw-SQL `userEditedSQL` tile uses the global `relationships` file), but restricted queriers and viewers can't see it; the two Known Issues rules above say when to ask and when to advise Access Boost. To author a raw-SQL tile and boost it end to end, see [references/queryPresentations.md](references/queryPresentations.md) → *Raw-SQL tiles*; for the boost commands and the org-level prerequisite, see **`omni-admin`** → *Document Permissions* (`add-permits` with `accessBoost`, or `update-permission-settings`).

**Authoring limit (distinct from the visibility above):** if *you* are a Restricted Querier, you **can't author a non-topic / raw-SQL tile at all** — `QUERY_TOPICS` queries topics only — so **every tile you build must be topic-based**. The non-topic + Access-Boost path is only for a `QUERY_FULL_MODEL` author building for a restricted *audience*. (Check with `whoami`; see **`omni-admin`** → *Model Roles & Caller Access*.)

## Document Management

Create a document with `documents v2-create`, by name alone or with the full envelope (tiles, controls, settings) in one `--body`. Rename through a draft patch (`--name`, then publish). Delete, move, and duplicate with `documents delete` / `move` / `duplicate`; only published documents can be duplicated. Examples, the create-body key points, and the end-to-end build workflows: [references/document-lifecycle.md](references/document-lifecycle.md).

## Update Existing Dashboard

Edits go through the **draft flow**; the published dashboard is untouched until you publish:

1. **Read** the current state with `omni documents v2-get <identifier> > doc.json`, or `v2-get-draft` if a draft already exists. Find the document first with `omni-content-explorer` or `omni documents list` if you don't have its identifier.
2. **Author the patch**, sending only what changes. Patches merge by key; the `order` arrays and `containers` are full replacements. To delete a tile, set its key to `null` and remove it from `order`.
3. **Open the draft**: `omni documents v2-patch-draft <identifier> --body @patch.json`, with a `summary` in the body, and keep the returned `draftIdentifier`. `--body @file` needs no shell quoting and checks the JSON before sending.
4. **Validate the draft**: read it back with `v2-get-draft <identifier> <draftIdentifier>` and run the affected queries (see [Validation Loops](#validation-loops)). Iterate with `v2-patch-draft-by-identifier <identifier> <draftIdentifier>`.
5. **Publish** with `omni documents v2-publish-draft <identifier>`, then share the link (see [URL Patterns](#url-patterns)). To abandon the draft, `omni documents discard-draft <identifier>`; the published document is untouched.

Error map, merge-semantics details, and recipes are in **[references/updating-dashboards.md](references/updating-dashboards.md)**.

## Updating a Dashboard's Model

Dashboard-specific fields go in the document's **workbook model**, which extends the shared model. First decide where a new field belongs, based on your access (`omni whoami whoami --model-id <sharedModelId>`): a table calculation, a branch on the shared model, or this workbook model. Never write to the schema model. A field that exists only on an unmerged branch needs a [branch-bound draft](references/branch-bound-drafts.md). Write workbook-model YAML with `"mode": "extension"`; the default combined mode marks every field you leave out as ignored. The decision steps, the `yaml-create` recipe, the order for building a tile on a new field, and how to verify it: [references/workbook-model.md](references/workbook-model.md).

## Dashboard Filters & Controls

Filters and interactive controls share one envelope slice: `controls: {data, order}`. Each entry is `{config, map}` — `config` holds the filter/control definition, `map` optionally scopes it per tile. Include them at create time or patch them in later (controls merge by key like tiles); a create-body example is in [references/controls.md](references/controls.md#filters-and-controls-in-a-create-body).

- The keys in `controls.data` are arbitrary IDs and must match `order`.
- **Filter shapes** (date / string / number / boolean, required) and **interactive controls** (field/timeframe switchers) are documented with examples in [references/controls.md](references/controls.md).
- `map` scopes a control per tile: `{"<tileKey>": false}` excludes a tile, `{"<tileKey>": "<fieldName>"}` remaps it — for both filters and interactive switchers.
- **Every filter MUST include `fieldName`** with the fully qualified field name (no timeframe bracket for date filters), or it won't bind to any column.
- To learn exact shapes, build filters in the Omni UI and read them back with `omni documents v2-get` — the `controls` slice is directly reusable in a patch.

**Model it or control it?** Model a filter as a filter-only field when every workbook and dashboard on the topic should get it, when one control drives several columns or a measure threshold, or when a control switches which column or measure a field uses. Otherwise use a dashboard control. The full criteria, including what a Restricted Querier can do: [references/controls.md](references/controls.md#model-it-or-control-it).

## Document Settings

`settings` is a shallow-merged object: `crossfilterEnabled` (click a value in one tile to filter the others), `facetFilters`, `refreshInterval` (seconds, `null` disables), `runQueriesOn` (`"current-page"` / `"all-pages"` / `null`), and `customText` (`{queryError, queryNoResults}` overrides). Patch only the keys you're changing.

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
3. **Check each viz spec**: `prefersChart: true`, the spec under `visConfig.visConfig.config`, and a `chartType` that matches its `visType` and `configType`.
4. **Verify the draft before publishing**: read it back with `v2-get-draft`, run each tile's query (`omni documents get-queries` + `omni query run`), and report each tile's status and row count.

What to check in each response, the full viz-spec table, and the checklist: [references/validation-and-testing.md](references/validation-and-testing.md).

## Dashboard Downloads

Downloads are asynchronous: start one with `omni dashboards download`, poll `download-status` until the job reaches a terminal state, then fetch the file with `download-file`. Single-tile and data formats, the one-page limit on multi-page dashboards, and what "Job failed to render" means: [references/downloads.md](references/downloads.md).

## Docs Reference

- [Documents API](https://docs.omni.co/api/documents.md) · [Dashboard Downloads](https://docs.omni.co/api/dashboard-downloads.md) · [Query API](https://docs.omni.co/api/queries.md) · [Schedules API](https://docs.omni.co/api/schedules.md) · [Visualization Types](https://docs.omni.co/visualize-present/visualizations.md)

## Related Skills

- **omni-model-explorer** — understand available fields
- **omni-model-builder** — create shared model fields
- **omni-query** — test queries before adding to dashboards
- **omni-content-explorer** — find existing dashboards to learn from
- **omni-embed** — embed dashboards you've built in external apps
