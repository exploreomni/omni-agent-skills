---
name: omni-content-builder
description: Create, update, and manage Omni Analytics documents and dashboards programmatically — document lifecycle, tiles, visualizations, filters, and layouts — using the Omni CLI. Use this skill whenever someone wants to build a dashboard, create a workbook, add tiles or charts, configure dashboard filters, update an existing dashboard's model, set up a KPI view, create visualizations, lay out a dashboard, create a document, rename a workbook, delete a dashboard, move a document to a folder, duplicate a dashboard, or any variant of "build a dashboard for", "create a report showing", "add a chart to", "make a dashboard", "update the dashboard layout", "rename this document", "move to folder", or "delete this dashboard". Also use when modifying dashboard-level model customizations like workbook-specific joins or fields.
---

# Omni Content Builder

Create, update, and manage Omni documents and dashboards programmatically via the Omni CLI — document lifecycle, workbook models, filters, and dashboard content.

> **Tip**: Use `omni-model-explorer` to understand available fields and `omni-content-explorer` to find existing dashboards to modify or learn from.

## Known Issues & Safe Defaults

- **Always run the full validation loop** — see [Validation Loops](#validation-loops) below. At minimum: validate the model, test every query via `omni query run`, check viz spec consistency, and verify the dashboard after creation by reading it back and executing its queries.
- **Chart rendering**: Complex chart types may show "No chart available" in the Omni UI if `config`, `visType`, or `prefersChart` are misconfigured. If the user asks for a specific chart, include the complete chart-specific `config` from [references/queryPresentations.md](references/queryPresentations.md) or [references/visConfig.md](references/visConfig.md). Use `chartType: "table"` with `config: {}` only as a deliberate table fallback, not for requested charts.
- **Every query must include at least one measure** — a query with only dimensions produces empty/nonsense tiles (e.g., just months with no data).
- **Use `identifier` not `id`** for all document API calls — `.id` is null for workbook-type documents and will silently fail.
- **Boolean filters may be silently dropped** when a `pivots` array is present (reported Omni bug). If boolean filters aren't applying, remove the pivot and test again.
- **Dashboard updates are full replacements** — `omni documents put <identifier>` replaces the entire document state. Always read the existing document first and modify from there, or you'll lose tiles you didn't include.
- **Do not use `omni unstable documents-import` to update an existing dashboard** — import creates a new document and may drop newly-added tiles. For an existing dashboard, use `omni documents put <identifier>` once with the full modified document.
- **Do not persist invalid query-level filters** — if `omni query run` returns a server-side parsing error for a tile query filter, validate the unfiltered base query once. Do not save that broken filter into the tile. If a dashboard-level `filterConfig` can satisfy the user request, use that path and verify it by readback; otherwise leave the dashboard unchanged and report the blocker.
- **Bound failed dashboard updates** — if `omni documents put` returns a server-side filter or document validation error, stop after one corrected retry at most. Do not try repeated filter syntaxes, import/export cycles, draft endpoints, or test-document creation loops. Report that the existing dashboard contains a filter/write-path issue and explain what was preserved.
- **Treat dropped visualization config as a failed partial update** — after `omni documents put`, read the document back. If a required visualization field such as `visType`, `fields`, or `config` comes back `null`, missing, or absent for a tile that needs it, restore the original document payload once, then report the partial write and rollback result instead of continuing to probe alternate endpoints or claiming completion.
- **Create readback shape differs from update validation** — after `documents create`, Omni may omit presentation-level `visType`, `fields`, and `config` on `documents get` while keeping the executable query and `query.visConfig` available through `documents get-queries`. For new dashboards, verify tile count, `prefersChart`, `query.visConfig.chartType`, and per-tile query execution. Do not treat create readback omissions as the same failed partial-write condition used for `omni documents put` updates.

## Prerequisites

```bash
# Verify the Omni CLI is installed — if not, ask the user to install it
# See: https://github.com/exploreomni/cli#readme
command -v omni >/dev/null || echo "ERROR: Omni CLI is not installed."
```

```bash
# Show available profiles and select the appropriate one
omni config show
# If multiple profiles exist, ask the user which to use, then switch:
omni config use <profile-name>
```

## Discovering Commands

```bash
omni documents --help           # Document operations
omni dashboards --help          # Dashboard operations
omni models yaml-create --help  # Writing model YAML
```

> **Tip**: Use `-o json` to force structured output for programmatic parsing, or `-o human` for readable tables. The default is `auto` (human in a TTY, JSON when piped).

## Dashboard Architecture

Omni dashboards are built from **documents** (workbooks). Each has:
- A **dashboard view** (the published, shareable layout)
- One or more **query tabs** (underlying queries)
- A **workbook model** (per-dashboard model customizations)

Documents can be created with full query and visualization configurations via `queryPresentations`. Fine-tuning tile layout is best done in the Omni UI.

## Build queries on a topic

Build every tile's query **on a topic** whenever possible: set the query `table` to the topic's **base view** and pass `join_paths_from_topic_name: <topic>`, plus `topicName: <topic>` on the **presentation** (the presentation-level `topicName` is tile-specific — a standalone query has no equivalent). Joined-view fields then resolve through the topic's join map from the base view. For the full shape — how the join map reaches joined-view fields, the worked example, and verifying with `omni models get-topic` (`base_view_name`/`join_via_map`) — see **`omni-query`**'s *Build queries on a topic*.

**Access matters:** a tile **not** built on a topic is **not accessible to restricted queriers/viewers**. A bare base-view query still works (it traverses the global `relationships` file) but is restricted-access-invisible in a dashboard — use it only when no topic fits *and* the audience isn't restricted.

**If no existing topic fits the request**, don't just fall back to a base view — decide whether to *extend* an existing topic or *create* a new one, and build it on a branch. Use **`omni-query`** to choose/decide the topic and **`omni-model-builder`** to create or modify one.

## Document Management

### Create Document (Name Only)

```bash
omni documents create --body '{
  "modelId": "your-model-id",
  "name": "Q1 Revenue Report"
}'
```

Returns the new document's `identifier`, `workbookId`, and `dashboardId`.

### Create Document with Queries and Visualizations

Use `queryPresentations` to create a document pre-populated with query tabs and visualization configurations.

> **Doc gap**: The [create-document API docs](https://docs.omni.co/api/documents/create-document.md) mention queryPresentations but don't show the complete structure. This section documents the full format.

```bash
omni documents create --body '{
  "modelId": "your-model-id",
  "name": "Q1 Revenue Report",
  "queryPresentations": [
    {
      "name": "Monthly Revenue Trend",
      "topicName": "order_items",
      "prefersChart": true,
      "chartType": "lineColor",
      "visConfig": {
        "visType": "basic",
        "fields": ["order_items.created_at[month]", "order_items.total_revenue"],
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
      },
      "fields": ["order_items.created_at[month]", "order_items.total_revenue"],
      "query": {
        "table": "order_items",
        "fields": ["order_items.created_at[month]", "order_items.total_revenue"],
        "sorts": [{ "column_name": "order_items.created_at[month]", "sort_descending": false }],
        "filters": { "order_items.created_at": "this quarter" },
        "limit": 100,
        "join_paths_from_topic_name": "order_items",
        "visConfig": { "chartType": "lineColor" }
      }
    }
  ]
}'
```

> **Tip**: The rendering spec belongs in **`visConfig.config`** with `chartType` set at the queryPresentation level — a bare top-level `config` is silently dropped, and `query.visConfig.chartType` alone does not produce a chart. `visConfig.config: {}` is fine for tables. A correctly-shaped `create` reliably one-shots a styled chart (no export/import needed); for advanced styling you can still build a reference dashboard in the UI and read it back via `omni documents get`. See [references/queryPresentations.md](references/queryPresentations.md) and [references/visConfig.md](references/visConfig.md) for complete config examples by chart type.

#### queryPresentation Structure

See [references/queryPresentations.md](references/queryPresentations.md) for the complete reference — parameter tables for `queryPresentation` and `query` objects, chart type examples, and caveats when reusing presentations from existing dashboards. See [references/visConfig.md](references/visConfig.md) for the full `visConfig` and `config` object reference — all accepted `chartType` values, config structure for every chart family (cartesian, KPI, pie, funnel, sankey, heatmap, map), and worked examples.

**Key points:**
- `prefersChart` must be `true` to render a chart (otherwise always shows table)
- A chart is defined by **two queryPresentation-level fields**: `chartType` (the enum value) and `visConfig` (`{ config, visType, fields }`). The rendering spec goes in **`visConfig.config`**.
- A bare top-level `config` on the queryPresentation is **silently dropped** — do not put the spec there. `query.visConfig.chartType` is only a hint and does not drive the tile on its own.
- `visType`: `"omni-kpi"` for KPI, `"basic"` for cartesian/pie/heatmap/boxplot, `"funnel"`/`"sankey"`/`"map"` for those families, `"omni-table"` for tables
- `chartType` must be a valid enum value — e.g. `column`/`columnStacked` (vertical), `bar`/`barStacked` (horizontal), `lineColor`, `area`, `pie`, `kpi`. **`barColor`/`areaColor`/`stackedBarColor` are NOT valid.**
- `fields` must be duplicated at both the `queryPresentation` and `query` levels
- `modelId` is inherited from the document — not needed inside `query`
- `automaticVis` is set from `prefersChart` and is harmless — it does not discard an explicit `chartType`/`visConfig.config`
- For the full enum, the `chartType → visType → configType` mapping, and per-family `config` shapes, see [references/visConfig.md](references/visConfig.md)

**To learn the exact structure for a chart type**, build a reference dashboard in the Omni UI and read it back:

```bash
omni documents get <documentId>
```

**When reusing queryPresentations from existing documents**, always strip `model_extension_id` from query objects (causes "Chart unavailable" errors) and filter to only the tiles you want.

### Rename Document

```bash
omni documents update <documentId> --name "Q1 Revenue Report (Updated)" --clear-existing-draft true
```

Pass `--clear-existing-draft true` if the document has an existing draft, otherwise the API returns 409 Conflict.

### Delete Document

```bash
omni documents delete <documentId>
```

Soft-deletes the document (moves to Trash).

### Move Document

```bash
omni documents move <documentId> "/Marketing/Reports" --scope organization
```

Use `"null"` as the folder path to move to root. `--scope` is optional — auto-computed from the destination folder.

### Duplicate Document

```bash
omni documents duplicate <documentId> "Copy of Q1 Revenue Report" --folder-path "/Marketing/Reports"
```

Only published documents can be duplicated. Draft documents return 404.

## Update Existing Dashboard

Update an existing **dashboard document** with **`omni documents put <identifier>`** — a **full replacement**: pass the complete desired state (all `queryPresentations`, not just your changes). Any tile you omit is removed. Workbook-only documents return 400. (`omni documents update` is a partial update for `name`/`description` only.)

1. **Read** the current state: `omni documents get <identifier>` (returns `queryPresentations`, `filterConfig`, `filterOrder`, `modelId`, `name`, …).
2. **Modify** the `queryPresentations` array (add/remove/edit tiles) and/or `filterConfig`/`filterOrder` — keep every tile you want to retain.
3. **Write it back** with a full body:
   ```bash
   omni documents put <identifier> --body '{
     "modelId": "...", "name": "...", "facetFilters": false, "refreshInterval": null,
     "filterConfig": {}, "filterOrder": [], "clearExistingDraft": true,
     "queryPresentations": [ ... ]
   }'
   ```
   To add tiles without losing any, include the existing tiles **plus** the new ones — that's how you build a dashboard up additively even though `put` replaces the whole document.
4. **Read back** and confirm each tile's `visConfig` persisted (non-empty `spec` for charts); a write that saved the query but dropped `visType`/`config`/`fields` is a failed partial write, not success.

Full field reference (`required`/`optional`), `clearExistingDraft`/409 handling, and the filter-error + partial-write + rollback playbook are in **[references/updating-dashboards.md](references/updating-dashboards.md)**.

## Updating a Dashboard's Model

> **First decide where a new field belongs.** Skill users are almost always **modelers or admins** who *can* write to the shared model — so choose the field's right home, not the lowest-friction path. In order:
> 1. **Can it be a calculation?** A table calculation is scoped to a **single query/tile** (computed on the result set). Prefer one for logic local to one query — but lean to a model field (→ #2/#3) when (a) the **query shape rules a calc out**, or (b) you're building **multiple queries at once** and the same logic spans them and can be expressed as a dimension/measure. **Window-shaped logic** (running total, moving average, % change) should almost always stay a calc — it runs post-query on the result set, not in-warehouse; only reach for an in-warehouse field when the window must span rows *outside* the result set. (See `omni-query`'s table-calculation guidance.)
> 2. **Reusable elsewhere?** If the field is likely to be used beyond this one dashboard, prefer adding it to a **branch on the shared model** and follow **`omni-model-builder`** to create, validate, and ship it.
> 3. **One-off for this dashboard (and not a calculation)?** Add it to the **workbook model** — see [Building a tile that queries a workbook-model field](#building-a-tile-that-queries-a-workbook-model-field) below for the `create` → `yaml-create` → `put` flow — but still follow **`omni-model-builder`'s field-level guidance** for correct syntax, and verify the query behaves as intended.
> 4. **Unsure?** Ask the creator where the field should live.
> 5. **Never write to the schema model** — it's auto-generated and read-only.
>
> **Whichever home you pick, if the field isn't in the *published* shared model yet** — it lives only on a model **branch** that hasn't merged, or only in the **workbook model** — the tile must go on a **branch-bound draft**, and you must stamp each tile's `query.modelId` with the document's workbook model or restricted-role users get a spurious "Invalid model" warning. See **[references/branch-bound-drafts.md](references/branch-bound-drafts.md)** for the recipes and the `modelId` fix.

Push custom dimensions and measures to a specific dashboard by writing to its workbook model. Each workbook has its own model that **extends** the shared model — so the ID you write YAML to is a model ID, not a separate "workbook ID". This is a two-step flow:

**Step 1 — get the document to find its workbook model ID:**

```bash
omni documents get <documentId>
# → use the top-level "modelId" field from the response — that IS the workbook model ID
```

> **Note**: The response does not contain a field called `workbook_id`. The top-level `modelId` is the workbook's own model (which extends the shared model) and is what you pass to `omni models yaml-create`.

**Step 2 — POST YAML to the workbook model with `mode: "extension"`:**

```bash
omni models yaml-create <workbookModelId> --body '{
  "fileName": "order_items.view",
  "yaml": "dimensions:\n  is_high_value:\n    sql: \"${sale_price} > 100\"\n    label: High Value Order\nmeasures:\n  high_value_count:\n    sql: \"${order_items.id}\"\n    aggregate_type: count_distinct\n    label: High Value Orders",
  "mode": "extension"
}'
```

> **Critical**: Always pass `"mode": "extension"` when editing an existing view in a workbook model. The default is `"combined"`, which treats your YAML body as the *complete* view definition and marks every field you didn't include as `ignored: true` — silently breaking queries that depend on fields from the shared base view. Extension mode layers your new dimensions and measures on top of the inherited view.

`fileName` must be `"model"`, `"relationships"`, or end with `.view` or `.topic`. The `yaml` value is a YAML string (not a JSON object). Writing to a workbook model skips git sync entirely — authorization is still checked against the underlying shared model's permissions.

### Building a tile that *queries* a workbook-model field

Two rules govern any tile whose query references a workbook-model field — both verified against a live instance:

- **The tile's `query.modelId` must be the workbook model.** A workbook field doesn't exist in the shared model, so a tile with `query.modelId` = the shared model **fails to resolve the field outright** (not a soft warning — the query errors). But `documents create` stamps the *shared* model onto every tile's `query.modelId`, regardless of the workbook model it just provisioned. So a one-shot `create` can't produce a working workbook-field tile; you must `put` the tile afterward with `query.modelId` set to the workbook model.
- **The field must exist before the `put` that references it,** and the workbook model itself only exists *after* `create`. So the order is fixed:
  1. **`documents create`** (empty, or with shared-field tiles) — provisions the workbook model.
  2. **`documents get <id>`** → the top-level `modelId` (the workbook model).
  3. **`yaml-create <workbookModelId>` `mode: "extension"`** → add the field (above).
  4. **`documents put <id>`** with each workbook-field tile's `query.modelId` = the workbook model (and the top-level `modelId` too).

> **On a branch-bound draft this differs:** a draft has its *own* workbook model (a distinct id), so the field must be written there, and that model extends the branch — letting one `query.modelId` resolve branch-only and workbook-model fields together. See **[references/branch-bound-drafts.md](references/branch-bound-drafts.md)**.

### Verify the Extension Worked

After writing, confirm the base view's fields are still available by querying one:

```bash
omni query run --body '{
  "query": {
    "modelId": "<workbookModelId>",
    "table": "order_items",
    "fields": ["order_items.id", "order_items.high_value_count"],
    "limit": 1,
    "join_paths_from_topic_name": "order_items"
  }
}'
```

If the response errors on a field that exists in the shared model (e.g. `order_items.id`), your write likely used combined mode and ignored the inherited fields. Re-run Step 2 with `"mode": "extension"`.

## Dashboard Filters

### Get Current Filters

```bash
omni dashboards get-filters <dashboardId>
```

### Update Filters

Filters can be updated via two approaches:

1. **`omni documents put <identifier>`** (recommended) — update filters as part of a full document update. Include `filterConfig` and `filterOrder` alongside `queryPresentations` and other required fields. See the [Update Existing Dashboard](#update-existing-dashboard) section.
2. **`omni dashboards update-filters <dashboardId>`** — partial filter update. Has been reported to return 405 or 500 in some configurations.

For **new dashboards**, the most reliable way is to include `filterConfig` and `filterOrder` in the initial `omni documents create` call. See [references/filterConfig.md](references/filterConfig.md) for complete examples of each filter type.

```bash
omni documents create --body '{
  "modelId": "your-model-id",
  "name": "Filtered Dashboard",
  "filterConfig": {
    "date_filter": {
      "type": "date",
      "label": "Date Range",
      "fieldName": "order_items.created_at",
      "kind": "TIME_FOR_INTERVAL_DURATION",
      "ui_type": "PAST",
      "left_side": "6 months ago",
      "right_side": "6 months"
    },
    "state_filter": {
      "type": "string",
      "label": "State",
      "kind": "EQUALS",
      "fieldName": "users.state",
      "values": []
    }
  },
  "filterOrder": ["date_filter", "state_filter"],
  "queryPresentations": [...]
}'
```

The keys in `filterConfig` (e.g., `"date_filter"`) are arbitrary IDs — they must match the entries in `filterOrder`. To learn the exact filter structure, read filters from an existing dashboard with `omni dashboards get-filters <dashboardId>`.

### Filter Types

**Date Range (relative)** — `type: "date"`, `kind: "TIME_FOR_INTERVAL_DURATION"`, requires `fieldName`

**Date Range (absolute)** — `type: "date"`, `kind: "WITHIN_RANGE"`, requires `fieldName`

**String Dropdown** — `type: "string"`, `kind: "EQUALS"`, requires `fieldName`, `values: []`

**Boolean Toggle** — `type: "boolean"`, requires `fieldName`

**Hidden Filter** — any filter with `"hidden": true` (applied but not visible)

> **Critical**: Every filter MUST include `fieldName` with the fully qualified field name (e.g., `"order_items.created_at"`). Without it, the filter won't bind to any column. For date filters, do NOT include a timeframe bracket in `fieldName`.

### Controls (separate from filters)

Controls change what fields or granularity tiles display. They go in a `controls` array (NOT in `filterConfig`), but their IDs are included in `filterOrder`.

**Time Frame Switcher** — `type: "FIELD_SELECTION"`, `kind: "TIMEFRAME"` with options array

**Field Switcher** — `type: "FIELD_SELECTION"`, `kind: "FIELD"` with options array

See [references/filterConfig.md](references/filterConfig.md) for complete filter and control examples.

## URL Patterns

After creating or finding content, always provide the user a direct link:

```
Dashboard: {OMNI_BASE_URL}/dashboards/{identifier}
Workbook:  {OMNI_BASE_URL}/w/{identifier}
```

A **draft** is linked the same way as any dashboard, using the *draft's own* `identifier` (from the `create-draft` response or `documents list-drafts`): `{OMNI_BASE_URL}/dashboards/{draftIdentifier}`.

The `identifier` comes from the document's `identifier` field in API responses (not `id`, which is null for workbooks).
Replace `{OMNI_BASE_URL}` with the actual base URL from the active profile or
environment, normalized without a trailing slash. Do not return the literal
placeholder string unless credentials are unavailable and you explicitly say the
URL is a template.

## Validation Loops

Every dashboard build or update must be validated **before and after** creation — broken tiles, bad field references, and misconfigured viz specs fail **silently** ("Chart unavailable" / "No data") with no API-level error. The full methodology — commands, the viz-spec consistency table, and the post-creation checklist — is in **[references/validation-and-testing.md](references/validation-and-testing.md)**. In brief:

1. **Validate the model** — `omni models validate <modelId>`; treat any `is_warning: false` issue as an error.
2. **Test every query first** — run each tile's query via `omni query run` before building (the single most important step). Check for no `error`, `summary.row_count > 0`, and include the same filters you'll use on the dashboard.
3. **Check viz-spec consistency** — `prefersChart: true`; spec in `visConfig.config` (not a top-level `config`); a valid `chartType` with matching `visType`/`configType`; correct `_dependentAxis`; the stack/color dimension in `query.pivots`. See [references/visConfig.md](references/visConfig.md).
4. **Verify after creation** — read back with `omni documents get`, run `omni documents get-queries` + `omni query run` per tile, and report each tile's status + row count. After one failed corrected update, report the blocker and stop.

See **[references/validation-and-testing.md](references/validation-and-testing.md)** for the complete steps, the consistency table, and the checklist.

## Recommended Build Workflows

### API-First (Full Programmatic Creation)

1. **Discover fields** — use `omni-model-explorer` to find topic + fields
2. **Validate model** — run `omni models validate <modelId>` and check for errors
3. **Test each query** — run every query you plan to include via `omni query run` (using `omni-query`) before building the dashboard. Include the same filters you plan to use in `filterConfig` as query-level filters to confirm they parse correctly. This catches field name typos, missing join paths, bad filter expressions, and permission errors before they become broken tiles.
4. **Validate viz specs** — check each tile's `visType`/`chartType`/`config`/`prefersChart` against the [consistency rules](#step-3-validate-viz-spec-consistency) before assembling the payload
5. **Create document** — single `omni documents create` with `queryPresentations` + `filterConfig` + `filterOrder` all in one call
6. **Verify the dashboard** — read it back with `omni documents get`, confirm all tiles are present, then run each tile's query via `omni documents get-queries` + `omni query run` to verify no broken tiles
7. **Share the link** — return `{OMNI_BASE_URL}/dashboards/{identifier}` to the user (only after verification passes)
8. **Refine in UI** — tile layout, chart styling, and advanced config are best done in the Omni UI

### Update Existing Dashboard

1. **Find the dashboard** — use `omni-content-explorer` or `omni documents list` to locate it
2. **Read its current state** — `omni documents get <documentId>` to get the full document including `queryPresentations`, `filterConfig`, etc.
3. **Modify** — add, remove, or edit entries in the `queryPresentations` array; update `filterConfig`/`filterOrder` as needed
4. **Validate changes** — run any new or modified queries via `omni query run` to confirm they work. Check modified viz specs against the [consistency rules](#step-3-validate-viz-spec-consistency).
5. **Write the update** — `omni documents put <identifier>` with the complete modified document and `clearExistingDraft: true`
6. **Verify the update** — read the document back with `omni documents get` and confirm the expected tiles are present. Run `omni documents get-queries` + `omni query run` on modified tiles to verify they execute without error.
7. **Share the link** — return `{OMNI_BASE_URL}/dashboards/{identifier}` to the user (only after verification passes)

### UI-First (Hybrid Approach)

1. **Prepare the Model** — use `omni-model-builder` for shared fields, or `update-model` for dashboard-specific fields
2. **Build in UI** — add tiles, choose viz types, arrange the grid, set filters
3. **Iterate via API** — update model fields, extract queries for reuse

## Dashboard Downloads

```bash
# Start async download
omni dashboards download <dashboardId> --body '{ "format": "pdf" }'

# Poll job
omni dashboards download-status <dashboardId> <jobId>
```

## Docs Reference

- [Documents API](https://docs.omni.co/api/documents.md) · [Update Document](https://docs.omni.co/api/documents/update-document) · [Dashboard Filters](https://docs.omni.co/api/dashboard-filters.md) · [Dashboard Downloads](https://docs.omni.co/api/dashboard-downloads.md) · [Query API](https://docs.omni.co/api/queries.md) · [Schedules API](https://docs.omni.co/api/schedules.md) · [Visualization Types](https://docs.omni.co/visualize-present/visualizations.md)
- **Skill references**: [queryPresentations.md](references/queryPresentations.md) · [visConfig.md](references/visConfig.md) · [filterConfig.md](references/filterConfig.md) · [branch-bound-drafts.md](references/branch-bound-drafts.md)

## Related Skills

- **omni-model-explorer** — understand available fields
- **omni-model-builder** — create shared model fields
- **omni-query** — test queries before adding to dashboards
- **omni-content-explorer** — find existing dashboards to learn from
- **omni-embed** — embed dashboards you've built in external apps
