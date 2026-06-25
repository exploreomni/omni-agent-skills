---
name: omni-content-builder
description: Create, update, and manage Omni Analytics documents and dashboards programmatically — document lifecycle, drafts, tiles, visualizations, filters, controls, and layouts — using the Omni CLI. Use this skill whenever someone wants to build a dashboard, create a workbook, add tiles or charts, configure dashboard filters or controls, update an existing dashboard's model, set up a KPI view, create visualizations, lay out a dashboard, arrange tiles or pages, create a document, edit a dashboard as a draft, publish a draft, change dashboard settings, rename a workbook, delete a dashboard, move a document to a folder, duplicate a dashboard, or any variant of "build a dashboard for", "create a report showing", "add a chart to", "make a dashboard", "update the dashboard layout", "rename this document", "publish this draft", "move to folder", or "delete this dashboard". Also use when modifying dashboard-level model customizations like workbook-specific joins or fields.
---

# Omni Content Builder

Create, update, and manage Omni documents and dashboards programmatically via the Omni CLI — document lifecycle, drafts, workbook models, filters, controls, and dashboard content.

> **Tip**: Use `omni-model-explorer` to understand available fields and `omni-content-explorer` to find existing dashboards to modify or learn from.

Documents are created and edited through the **v2 documents API** (`omni documents v2-*`) — an explicit envelope of `queryPresentations`, `controls`, `containers`, and `settings`, edited through a **draft → publish** flow. This is the only path for building, reading, or changing a document — never fall back to the v1 `documents create`/`get`/`put`/`update` commands. A few document-management operations (list, delete, move, duplicate, downloads) have no v2 form; see [Commands](#commands) below.

## Known Issues & Safe Defaults

- **Always run the full validation loop** — see [Validation Loops](#validation-loops) below. At minimum: validate the model, test every query via `omni query run`, check viz spec consistency, and verify the dashboard by reading the draft back and executing its queries **before publishing**.
- **Never round-trip a `v2-get` tile back into a patch unchanged** — a GET returns the inner vis config *flat*, but a patch only persists it *nested under `config`*. Re-sending the flat shape — even for an unrelated edit like a rename — silently drops the vis config (KPI loses its number, charts lose `mark`/`series`, markdown goes blank). Always re-author the inner `visConfig` nested under `config`. See [references/documents-v2.md](references/documents-v2.md).
  - **This applies to *any* write whose tile JSON came from a GET payload — not just edits.** Restoring, reverting, duplicating, or moving a tile by copying it out of a `v2-get`/snapshot and patching it back is *also* a round-trip: the inner config is flat and will be dropped (renders "No chart available"). A "restore to how it was" still needs the config re-nested. And **verify the specific tile you wrote** — re-read it (`v2-get`) and run its query to confirm the config persisted; if a visual/preview tool is available, you can also request a screenshot to confirm the render — *including reverts*; don't assume a restore is safe.
- **Patches merge by key; only `containers` (and the `order` arrays) are full replacements.** To change one tile, send just that key. To delete a tile, set its key to `null` AND remove it from `order`. When you send `containers`, send the complete layout tree with your edit applied.
- **A multi-tile `v2-create` only lays out the first tile** — the rest are stored but render nowhere until you author the full `containers` tree. See [references/containers.md](references/containers.md).
- **Tile `"1"` on create merges over a server seed tile** — some seed properties (e.g. `automaticVis: true`) can win over what you sent. Read the document back and re-patch tile `"1"` if its exact fields matter.
- **Every tile `query` must include the full collection-field set** — `sorts`, `filters`, `calculations`, `column_totals`, `row_totals`, `fill_fields`, `pivots`, `userEditedSQL` (empty values are fine) alongside `table`, `fields`, `limit`, `join_paths_from_topic_name`. Omitting the schema-required ones is a 400 with per-field errors. Do **not** include `modelId` or `model_extension_id` — the server anchors tiles to the document's workbook model and silently rewrites any value you send.
- **HARD RULE — never build a non-topic tile from handed-over SQL without an explicit user decision.** When the user hands you SQL (or a metric) and existing topics don't express it, you may **not** silently convert it to a non-topic / `userEditedSQL` tile. First apply the topic-first reflex (see `omni-query`): map each query's intent to a topic. If none fits, **stop and ask** whether to model it — extend a topic or create a new one (on a branch via `omni-model-builder`, validated, merged only with confirmation). Only build a non-topic / raw-SQL tile after the user has **explicitly chosen** that path (declined modeling, or it's a genuine one-off / `userEditedSQL` is required). Non-topic + Access Boost is never the default for handed-over SQL — it requires that explicit decision. This is the easiest thing to get wrong when "build a dashboard" starts from raw SQL.
- **Non-topic / raw-SQL tiles → ask about the audience, then counsel Access Boost.** When a tile's query is non-topic — a populated `userEditedSQL` (raw-SQL tile) or a bare base-view query (no `join_paths_from_topic_name`) — it is **invisible to Viewer / Restricted Querier roles by default**. Before finalizing such content, **ask the user whether the dashboard's audience includes Restricted Queriers or Viewers**. If it does, **advise** (don't silently enable) **Access Boost**: it makes those tiles viewable *on the dashboard* (dashboard-only — not the underlying workbook) for chosen users/groups or the whole org — provided the org capability is enabled and the caller has Manager on the document. Because it loosens access controls, treat enabling it as a separate, explicitly-confirmed step: recommend the **narrowest scope** that satisfies the need (specific users/groups over org-wide) and get a clear go-ahead before it's applied. See the *Raw-SQL tiles* recipe in [references/queryPresentations.md](references/queryPresentations.md) and **`omni-admin`** → *Document Permissions* (which carries the full confirmation checklist and the commands/prerequisite).
- **`--body` silently wins over shorthand flags** — if you pass `--body`, every promoted flag (`--name`, `--summary`, `--branch-id`, …) is ignored without warning. Put those fields inside the JSON body instead, or use flags alone with no `--body`.
- **Draft commands take the document identifier first, then the draft identifier**: `v2-get-draft <identifier> <draftIdentifier>` and `v2-patch-draft-by-identifier <identifier> <draftIdentifier>`.
- **Classic-layout dashboards return 422 from every v2 endpoint** — "Upgrade the dashboard to the advanced layout before editing it through the API." There is no API fallback; ask the user to upgrade the layout in the Omni UI, then retry.
- **The workbook model ID rotates on every draft → publish cycle** — each draft clones the workbook model (carrying extensions along), and publishing swaps the document to the clone. Never cache a workbook model ID; read it fresh from the draft's `workbookModelId` (`omni documents list-drafts <identifier>`) each time you need it.
- **Interactive controls scope per-tile via `map`** — a field/timeframe switcher's `{"<tileKey>": false}` excludes that tile, exactly like a filter's. See [references/controls.md](references/controls.md).
- **Markdown tiles need `automaticVis: false`** — otherwise the renderer auto-derives a chart and the tile is blank. See [references/visConfig.md](references/visConfig.md).
- **Mustache: reference a *filter* under `filters`, not `controls`.** To caption a tile with a filter's current value (e.g. a date window), use **`{{filters.…summary}}`** — *not* `{{controls.<id>.…}}` (a filter is configured as a control but mustache routes it to `filters`; the `controls` namespace is for `FIELD_SELECTION`/picker/Top-N controls and renders **empty** for a filter). The `filters` key is **context-dependent**: `view.field` in a markdown-viz tile (resolved against the tile's own query, so one token works per-tile), the control `id` in a dashboard text tile. Full namespace/token map + scenarios in [references/mustache.md](references/mustache.md).
- **`query.filters` needs the object form** — the relative-date shorthand (`"last 6 months"`) throws a 500; send `{type:"date", kind:"TIME_FOR_INTERVAL_DURATION", ui_type:"PAST", left_side, right_side}`. See [references/documents-v2.md](references/documents-v2.md).
- **A tile with no real `visConfig` renders as "Item missing"** — the server seeds new tiles with `visConfig.visType: null` + `automaticVis: false`, which draws nothing. Every tile needs either an explicit `visConfig` (e.g. the table recipe in [references/visConfig.md](references/visConfig.md)) or `automaticVis: true` to auto-derive one. Layout is separate: a multi-tile `v2-create` lays out all tiles you pass in `order`, so "Item missing" is a vis-config gap, not a `containers` gap.
- **Chart rendering**: Complex chart types may show "No chart available" if the inner config, `visType`, or `prefersChart` are misconfigured. If the user asks for a specific chart, include the complete chart-specific config from [references/visConfig.md](references/visConfig.md) nested under `visConfig.visConfig.config`. Use `chartType: "table"` only as a deliberate table fallback, not for requested charts.
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

> **Auth**: a profile authenticates with an **API key** or **OAuth**. If `whoami` (or any call) returns **401**, hand off — ask the user to run `! omni config login <profile>` (OAuth 2.1 browser flow; it blocks ~2 min on the browser). Don't run `config login` yourself in a headless/CI session (no browser → timeout); on a local interactive machine you *may*. See the **`omni-api-conventions`** rule for profile setup (`omni config init --auth oauth`) and discovering request-body shapes with `--schema`.

## Discovering Commands

```bash
omni documents --help              # Document operations (v2-* + lifecycle)
omni dashboards --help             # Dashboard downloads
omni models yaml-create --help     # Writing model YAML
omni documents v2-create --schema  # Body schema + example (add --depth 1 for an overview, --field PATH to drill in)
```

> **Tip**: Use `-o json` to force structured output for programmatic parsing, or `-o human` for readable tables. The default is `auto` (human in a TTY, JSON when piped). `--compact` strips indentation for piping.

## Commands

**Build and edit documents with the `documents v2-*` commands — always.** There is no situation where you reach back to the v1 `documents create`/`get`/`put`/`update` path to build, read, or change a document; the v2 draft flow covers all of it.

| Operation | Command |
|---|---|
| Create document | `documents v2-create` |
| Read document / draft state | `documents v2-get` / `v2-get-draft` |
| Edit document (tiles, controls, layout, settings, rename) | `documents v2-patch-draft` (+ `v2-patch-draft-by-identifier`) |
| Get the workbook model ID | `documents list-drafts` → `workbookModelId` (open a draft first) |
| Publish a draft | `documents v2-publish-draft` |

A handful of **document-management** operations have no v2 form — they aren't alternatives to the v2 build path, just the only command for that job: `documents list` / `list-drafts` (find documents and drafts), `documents discard-draft` (abandon a draft), `documents delete` / `move` / `duplicate` (lifecycle), `documents get-queries` (extract a tile's runnable query for validation), `dashboards download` / `download-status`, and `models yaml-create` / `validate` (model writes).

## Dashboard Architecture

Omni dashboards are built from **documents**. A document's v2 state is an envelope of four slices:

```jsonc
{
  "name": "…", "description": "…",
  "queryPresentations": { "data": { "<tileKey>": { /* tile: query + vis */ } }, "order": ["1", "2"] },
  "controls":           { "data": { "<controlId>": { "config": {…}, "map": {…} } }, "order": ["…"] },
  "containers":         [ /* layout tree: filter bar, pages, grids, tile stacks */ ],
  "settings":           { "crossfilterEnabled": …, "facetFilters": …, "refreshInterval": …, "runQueriesOn": …, "customText": … }
}
```

- **Tiles** live in `queryPresentations.data`, keyed by record key (`"1"`, `"2"`, …); `order` is the tab order.
- **Filters and interactive controls** are one map: `controls` (see [references/controls.md](references/controls.md)).
- **Layout** is the `containers` tree — a tile renders only where a container references it (see [references/containers.md](references/containers.md)).
- Each document also has a **workbook model** (per-dashboard model customizations) — its ID is the `workbookModelId` on the document's draft record from `documents list-drafts`.

A document is edited through **drafts**: `v2-patch-draft` creates a draft and applies your patch; the published document is untouched until `v2-publish-draft`. `v2-get` returns the current draft state if a draft exists, else the published state. Drafts can also be bound to a **model branch** (see [references/branch-bound-drafts.md](references/branch-bound-drafts.md)).

## Build queries on a topic

Build every tile's query **on a topic** whenever possible: set the query `table` to the topic's **base view** and pass `join_paths_from_topic_name: <topic>`, plus `topicName: <topic>` on the **presentation** (the presentation-level `topicName` is tile-specific — a standalone query has no equivalent). Joined-view fields then resolve through the topic's join map from the base view. For the full shape — how the join map reaches joined-view fields, the worked example, and verifying with `omni models get-topic` (`base_view_name`/`join_via_map`) — see **`omni-query`**'s *Build queries on a topic*.

**Access matters:** a tile **not** built on a topic is **not accessible to restricted queriers/viewers**. A bare base-view query (or a raw-SQL `userEditedSQL` tile) still works — it traverses the global `relationships` file — but is restricted-access-invisible in a dashboard. Use it only when no topic fits *and* the audience isn't restricted, **or** enable **Access Boost** on the document so Viewer/Restricted Querier roles can see it (dashboard-only — not the underlying workbook). To author a raw-SQL tile and boost it end-to-end, see [references/queryPresentations.md](references/queryPresentations.md) → *Raw-SQL tiles*; for the boost commands and the org-level prerequisite, see **`omni-admin`** → *Document Permissions* (`add-permits` with `accessBoost`, or `update-permission-settings`).

**If no existing topic fits the request**, don't just fall back to a base view (or raw SQL) — **ask the user** whether to *extend* an existing topic or *create* a new one, and build it on a branch only with their go-ahead. Don't silently convert un-modeled SQL into non-topic tiles. Use **`omni-query`** to choose/decide the topic and **`omni-model-builder`** to create or modify one (branch → validate → merge only on confirmation).

## Document Management

### Create Document (Name Only)

```bash
omni documents v2-create <model-id> "Q1 Revenue Report"
# optional flags: --identifier, --description, --folder-id
```

- `<model-id>` is the **shared** model; the server mints a per-document workbook model.
- The document is **created and published immediately**. The response returns only `{identifier, name, description}` — when you need the workbook model ID, open a draft and read its `workbookModelId` from `omni documents list-drafts <identifier>`.
- `--folder-id` omitted → the document lands in the creator's personal "My documents" (requires personal-content permission). Pass a folder ID to place it in a shared folder.

### Create Document with Queries and Visualizations

Pass the full envelope via `--body`. Tiles are keyed — write tile `"1"` explicitly to replace the server's seed tile:

```bash
omni documents v2-create --body '{
  "modelId": "your-shared-model-id",
  "name": "Q1 Revenue Report",
  "queryPresentations": {
    "data": {
      "1": {
        "name": "Monthly Revenue Trend",
        "type": "query",
        "topicName": "order_items",
        "prefersChart": true,
        "automaticVis": false,
        "query": {
          "table": "order_items",
          "fields": ["order_items.created_at[month]", "order_items.total_revenue"],
          "sorts": [{ "column_name": "order_items.created_at[month]", "sort_descending": false }],
          "filters": { "order_items.created_at": "this quarter" },
          "limit": 100,
          "join_paths_from_topic_name": "order_items",
          "calculations": [], "column_totals": {}, "row_totals": {},
          "fill_fields": [], "pivots": [], "userEditedSQL": ""
        },
        "visConfig": {
          "chartType": "lineColor",
          "fields": ["order_items.created_at[month]", "order_items.total_revenue"],
          "version": 0,
          "visConfig": {
            "visType": "basic",
            "config": {
              "x": { "field": { "name": "order_items.created_at[month]" } },
              "mark": { "type": "line" },
              "color": {},
              "series": [{ "field": { "name": "order_items.total_revenue" }, "yAxis": "y" }],
              "tooltip": [
                { "field": { "name": "order_items.created_at[month]" } },
                { "field": { "name": "order_items.total_revenue" } }
              ],
              "configType": "cartesian",
              "_dependentAxis": "y"
            }
          }
        }
      }
    },
    "order": ["1"]
  }
}'
```

> **The rendering spec goes in `visConfig.visConfig.config`** (visType beside it, spec nested under `config`). `chartType` and `fields` sit at the outer `visConfig` level. Misplaced spec keys are silently dropped on write — see the round-trip warning in Known Issues. See [references/queryPresentations.md](references/queryPresentations.md) and [references/visConfig.md](references/visConfig.md) for the structures and per-chart-type configs.

**Key points:**
- Tile keys are strings `"1"`, `"2"`, … and must appear in `order` to be tabs; tiles also need a `containers` entry to **render** on the dashboard. A multi-tile create auto-lays-out only tile `"1"` — author `containers` for the rest ([references/containers.md](references/containers.md)).
- `prefersChart` must be `true` to render a chart; set `automaticVis: false` when you author an explicit vis config.
- The `query` needs the full collection-field set (see Known Issues) and **no `modelId`**.
- `controls` and `settings` slices can be included in the same create body — see [Dashboard Filters & Controls](#dashboard-filters--controls).

**To learn the exact structure for a chart type**, build a reference dashboard in the Omni UI and read it back with `omni documents v2-get <identifier>` — remembering that the inner config reads back *flat* and must be re-nested under `config` before reuse.

### Rename Document

```bash
omni documents v2-patch-draft <identifier> --name "Q1 Revenue Report (Updated)" --summary "rename"
omni documents v2-publish-draft <identifier>
```

`--summary` is written to the document's history audit trail. (There is no `clearExistingDraft` in the v2 flow — if a draft already exists, patch it directly with `v2-patch-draft-by-identifier`, or discard it first.)

### Delete Document

```bash
omni documents delete <identifier>
```

Soft-deletes the document (moves to Trash).

### Move Document

```bash
omni documents move <identifier> "/Marketing/Reports" --scope organization
```

Use `"null"` as the folder path to move to root. `--scope` is optional — auto-computed from the destination folder.

### Duplicate Document

```bash
omni documents duplicate <identifier> "Copy of Q1 Revenue Report" --folder-path "/Marketing/Reports"
```

Only published documents can be duplicated. Draft documents return 404.

## Update Existing Dashboard

Edits go through the **draft flow** — the published dashboard is untouched until you publish, so validation happens before anything goes live:

1. **Read** the current state: `omni documents v2-get <identifier> > doc.json`.
2. **Author the patch** — patches **merge by key**, so send only the slices you're changing:
   - **Add a tile**: new key in `queryPresentations.data` + append it to `order` (+ a `containers` tile stack so it renders).
   - **Edit a tile**: send just that key — and **re-author its inner vis config nested under `config`** (never echo the flat GET shape back).
   - **Delete a tile**: set its key to `null` and remove it from `order` (and its stack from `containers`).
   - **Layout**: `containers` is a full replacement — send the whole tree with your edit applied.
3. **Create the draft + apply**: `omni documents v2-patch-draft <identifier> --body - < patch.json` — capture `draftIdentifier` from the response. Include a `summary` in the body for the audit trail.
4. **Validate the draft** — `omni documents v2-get-draft <identifier> <draftIdentifier>`, run the affected queries (see [Validation Loops](#validation-loops)). Iterate with `omni documents v2-patch-draft-by-identifier <identifier> <draftIdentifier> --body …`.
5. **Publish**: `omni documents v2-publish-draft <identifier>`. On failure or abandonment, `omni documents discard-draft <identifier>` cleans up without touching the published doc.

Error map, merge-semantics details, and recipes are in **[references/updating-dashboards.md](references/updating-dashboards.md)**.

## Updating a Dashboard's Model

> **First decide where a new field belongs.** Skill users are almost always **modelers or admins** who *can* write to the shared model — so choose the field's right home, not the lowest-friction path. In order:
> 1. **Can it be a calculation?** A table calculation is scoped to a **single query/tile** (computed on the result set). Prefer one for logic local to one query — but lean to a model field (→ #2/#3) when (a) the **query shape rules a calc out**, or (b) you're building **multiple queries at once** and the same logic spans them and can be expressed as a dimension/measure. **Window-shaped logic** (running total, moving average, % change) should almost always stay a calc — it runs post-query on the result set, not in-warehouse; only reach for an in-warehouse field when the window must span rows *outside* the result set. (See `omni-query`'s table-calculation guidance.)
> 2. **Reusable elsewhere?** If the field is likely to be used beyond this one dashboard, prefer adding it to a **branch on the shared model** and follow **`omni-model-builder`** to create, validate, and ship it.
> 3. **One-off for this dashboard (and not a calculation)?** Add it to the **workbook model** — see [Building a tile that queries a workbook-model field](#building-a-tile-that-queries-a-workbook-model-field) below.
> 4. **Unsure?** Ask the creator where the field should live.
> 5. **Never write to the schema model** — it's auto-generated and read-only.
>
> **If the field isn't in the *published* shared model yet** — it lives only on a model **branch** that hasn't merged — put the tile on a **branch-bound draft**. See **[references/branch-bound-drafts.md](references/branch-bound-drafts.md)**.

Push custom dimensions and measures to a specific dashboard by writing to its workbook model. Each workbook has its own model that **extends** the shared model — so the ID you write YAML to is a model ID, not a separate "workbook ID". Because every edit goes through a draft, and the field has to exist before a tile can reference it, the whole flow stays in the v2 draft path:

**Step 1 — open a draft and read its workbook model ID:**

```bash
omni documents v2-patch-draft <identifier> --summary "add workbook field"   # creates the draft
omni documents list-drafts <identifier>
# → use the draft record's "workbookModelId" — that IS the model you write YAML to
```

> **Note**: The workbook model (which extends the shared model) is what you pass to `omni models yaml-create`. Each draft has its **own** clone of it, and the ID **changes on every draft → publish cycle** — always read it fresh from `list-drafts`; never reuse a cached value.

**Step 2 — POST YAML to the draft's workbook model with `mode: "extension"`:**

```bash
omni models yaml-create <draftWorkbookModelId> --body '{
  "fileName": "order_items.view",
  "yaml": "dimensions:\n  is_high_value:\n    sql: \"${sale_price} > 100\"\n    label: High Value Order\nmeasures:\n  high_value_count:\n    sql: \"${order_items.id}\"\n    aggregate_type: count_distinct\n    label: High Value Orders",
  "mode": "extension"
}'
```

> **Critical**: Always pass `"mode": "extension"` when editing an existing view in a workbook model. The default is `"combined"`, which treats your YAML body as the *complete* view definition and marks every field you didn't include as `ignored: true` — silently breaking queries that depend on fields from the shared base view. Extension mode layers your new dimensions and measures on top of the inherited view.

`fileName` must be `"model"`, `"relationships"`, or end with `.view` or `.topic`. The `yaml` value is a YAML string (not a JSON object) containing the view's *contents* — no `views:` wrapper. Writing to a workbook model skips git sync entirely — authorization is still checked against the underlying shared model's permissions.

### Building a tile that *queries* a workbook-model field

v2 tile queries carry **no `modelId`** — the server anchors each tile to the draft's workbook model, so the field just has to exist in that model before the tile references it. The order is fixed:

1. **`documents v2-create`** (or use the existing document) — provisions the workbook model.
2. **`documents v2-patch-draft <identifier>`** — open the draft (a `--summary`-only patch is enough to create it).
3. **`documents list-drafts <identifier>`** → the draft's `workbookModelId`.
4. **`models yaml-create <draftWorkbookModelId>` with `mode: "extension"`** → add the field (above).
5. **`documents v2-patch-draft-by-identifier <identifier> <draftIdentifier>`** adding the tile that references the field — no `modelId` anywhere in the tile query.
6. **`documents v2-publish-draft <identifier>`** — the field and tile go live together.

After publishing, the workbook model ID has **changed** — open a new draft and re-read `workbookModelId` from `list-drafts` before any further `yaml-create`.

### Verify the Extension Worked

After writing, confirm the base view's fields are still available by querying one against the draft's workbook model:

```bash
omni query run --body '{
  "query": {
    "modelId": "<draftWorkbookModelId>",
    "table": "order_items",
    "fields": ["order_items.id", "order_items.high_value_count"],
    "limit": 1,
    "join_paths_from_topic_name": "order_items"
  }
}'
```

(Standalone `query run` bodies still take a `modelId` — only **tile** queries inside v2 documents omit it.) If the response errors on a field that exists in the shared model (e.g. `order_items.id`), your write likely used combined mode and ignored the inherited fields. Re-run Step 2 with `"mode": "extension"`.

## Dashboard Filters & Controls

Filters and interactive controls share one envelope slice: `controls: {data, order}`. Each entry is `{config, map}` — `config` holds the filter/control definition, `map` optionally scopes it per tile. Include them at create time or patch them in later (controls merge by key like tiles):

```bash
omni documents v2-create --body '{
  "modelId": "your-shared-model-id",
  "name": "Filtered Dashboard",
  "controls": {
    "data": {
      "date_filter": {
        "config": {
          "type": "date", "kind": "TIME_FOR_INTERVAL_DURATION", "ui_type": "PAST",
          "left_side": "6 months ago", "right_side": "6 months",
          "fieldName": "order_items.created_at",
          "topic": "order_items", "base_view": "order_items",
          "label": "Date Range"
        },
        "map": {}
      },
      "state_filter": {
        "config": {
          "type": "string", "kind": "EQUALS",
          "fieldName": "users.state",
          "topic": "order_items", "base_view": "order_items",
          "label": "State", "values": []
        },
        "map": {}
      }
    },
    "order": ["date_filter", "state_filter"]
  },
  "queryPresentations": { … }
}'
```

- The keys in `controls.data` are arbitrary IDs and must match `order`.
- **Filter shapes** (date / string / number / boolean, hidden, required) and **interactive controls** (field/timeframe switchers) are documented with examples in [references/controls.md](references/controls.md).
- `map` scopes a control per tile: `{"<tileKey>": false}` excludes a tile, `{"<tileKey>": "<fieldName>"}` remaps it — for both filters and interactive switchers.
- A control renders only where a container places it (filter bar, sidebar, or in-tile) — otherwise it lands in the HIDDEN CONTROLS tray. See [references/containers.md](references/containers.md).
- **Every filter MUST include `fieldName`** with the fully qualified field name (no timeframe bracket for date filters), or it won't bind to any column.
- To learn exact shapes, build filters in the Omni UI and read them back with `omni documents v2-get` — the `controls` slice is directly reusable in a patch.

## Document Settings

`settings` is a shallow-merged object: `crossfilterEnabled` (click a value in one tile to filter the others), `facetFilters`, `refreshInterval` (seconds, `null` disables), `runQueriesOn` (`"current-page"` / `"all-pages"` / `null`), and `customText` (`{queryError, queryNoResults}` overrides). Patch only the keys you're changing.

## Layout (containers)

The `containers` tree decides where tiles and controls render: a reserved `"filter-bar"` stack, then one `page` container per page, each holding a 24-column `grid` of tile stacks with `gridPosition {x,y,w,h}`. **Safe default on create: omit `containers`** and let the server lay out tile `"1"`, then author the full tree when you add more tiles. When editing, `containers` is a **full replacement** — round-trip the existing array with your change applied. Multi-page dashboards, page switchers, grouped bands, in-tile controls, and sizing rules: [references/containers.md](references/containers.md).

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

Every dashboard build or update must be validated **before publishing** — broken tiles, bad field references, and misconfigured viz specs fail **silently** ("Chart unavailable" / "No data") with no API-level error. The full methodology — commands, the viz-spec consistency table, and the post-creation checklist — is in **[references/validation-and-testing.md](references/validation-and-testing.md)**. In brief:

1. **Validate the model** — `omni models validate <modelId>`; treat any `is_warning: false` issue as an error.
2. **Test every query first** — run each tile's query via `omni query run` before building (the single most important step). Check for no `error`, `summary.row_count > 0`, and include the same filters you'll use on the dashboard.
3. **Check viz-spec consistency** — `prefersChart: true`; spec nested in `visConfig.visConfig.config`; a valid `chartType` with matching `visType`/`configType`; correct `_dependentAxis`; the stack/color dimension in `query.pivots`. See [references/visConfig.md](references/visConfig.md).
4. **Verify the draft before publishing** — read it back with `v2-get-draft`, confirm `queryPresentations.data` keys match `order`, run `omni documents get-queries` + `omni query run` per tile, and report each tile's status + row count. After one failed corrected patch, discard the draft and report the blocker.

## Recommended Build Workflows

### API-First (Full Programmatic Creation)

1. **Discover fields** — use `omni-model-explorer` to find topic + fields
2. **Validate model** — run `omni models validate <modelId>` and check for errors
3. **Test each query** — run every query you plan to include via `omni query run` (using `omni-query`) before building the dashboard. Include the same filters you plan to use as controls to confirm they parse correctly. This catches field name typos, missing join paths, bad filter expressions, and permission errors before they become broken tiles.
4. **Validate viz specs** — check each tile's `chartType`/`visType`/inner `config`/`prefersChart` against the consistency rules before assembling the payload
5. **Create document** — single `omni documents v2-create` with `queryPresentations` + `controls` + `settings` (and `containers` if multi-tile) in one body
6. **Verify the dashboard** — read it back with `omni documents v2-get`, confirm all tiles are present and placed, then run each tile's query via `omni documents get-queries` + `omni query run` to verify no broken tiles
7. **Share the link** — return `{OMNI_BASE_URL}/dashboards/{identifier}` to the user (only after verification passes)
8. **Refine in UI** — fine chart styling and pixel-level layout tweaks are still easiest in the Omni UI

### Update Existing Dashboard

1. **Find the dashboard** — use `omni-content-explorer` or `omni documents list` to locate it
2. **Read its current state** — `omni documents v2-get <identifier>`
3. **Author the patch** — merge-by-key edits to `queryPresentations`/`controls`/`settings`; full `containers` tree if layout changes; re-author inner vis configs nested under `config`
4. **Validate changes** — run new/modified queries via `omni query run`; check viz specs against the consistency rules
5. **Patch the draft** — `omni documents v2-patch-draft <identifier> --body …` (with a `summary`)
6. **Verify the draft** — `v2-get-draft`, then `get-queries` + `query run` on modified tiles
7. **Publish** — `omni documents v2-publish-draft <identifier>`; on failure, `discard-draft` and report
8. **Share the link** — return `{OMNI_BASE_URL}/dashboards/{identifier}` to the user (only after verification passes)

### UI-First (Hybrid Approach)

1. **Prepare the Model** — use `omni-model-builder` for shared fields, or the workbook-model flow above for dashboard-specific fields
2. **Build in UI** — add tiles, choose viz types, arrange the grid, set filters
3. **Iterate via API** — read the structure back with `v2-get`, update model fields, extract queries for reuse

## Dashboard Downloads

```bash
# Start async download
omni dashboards download <dashboardId> --body '{ "format": "pdf" }'

# Poll job
omni dashboards download-status <dashboardId> <jobId>
```

## Docs Reference

- [Documents API](https://docs.omni.co/api/documents.md) · [Dashboard Downloads](https://docs.omni.co/api/dashboard-downloads.md) · [Query API](https://docs.omni.co/api/queries.md) · [Schedules API](https://docs.omni.co/api/schedules.md) · [Visualization Types](https://docs.omni.co/visualize-present/visualizations.md)
- **Skill references**: [documents-v2.md](references/documents-v2.md) · [containers.md](references/containers.md) · [controls.md](references/controls.md) · [queryPresentations.md](references/queryPresentations.md) · [visConfig.md](references/visConfig.md) · [markdown-tiles.md](references/markdown-tiles.md) · [mustache.md](references/mustache.md) · [updating-dashboards.md](references/updating-dashboards.md) · [branch-bound-drafts.md](references/branch-bound-drafts.md) · [validation-and-testing.md](references/validation-and-testing.md)

## Related Skills

- **omni-model-explorer** — understand available fields
- **omni-model-builder** — create shared model fields
- **omni-query** — test queries before adding to dashboards
- **omni-content-explorer** — find existing dashboards to learn from
- **omni-embed** — embed dashboards you've built in external apps
