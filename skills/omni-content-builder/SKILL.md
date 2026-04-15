---
name: omni-content-builder
description: Create, update, and manage Omni Analytics documents and dashboards programmatically — document lifecycle, tiles, visualizations, filters, and layouts — using the Omni CLI. Use this skill whenever someone wants to build a dashboard, create a workbook, add tiles or charts, configure dashboard filters, update an existing dashboard's model, set up a KPI view, create visualizations, lay out a dashboard, create a document, rename a workbook, delete a dashboard, move a document to a folder, duplicate a dashboard, or any variant of "build a dashboard for", "create a report showing", "add a chart to", "make a dashboard", "update the dashboard layout", "rename this document", "move to folder", or "delete this dashboard". Also use when modifying dashboard-level model customizations like workbook-specific joins or fields.
---

# Omni Content Builder

Create, update, and manage Omni documents and dashboards programmatically via the Omni CLI — document lifecycle, workbook models, filters, and dashboard content.

> **Tip**: Use `omni-model-explorer` to understand available fields and `omni-content-explorer` to find existing dashboards to modify or learn from.

## Known Issues & Safe Defaults

- **Always run the full validation loop** — see [Validation Loops](#validation-loops) below. At minimum: validate the model, test every query via `omni query run`, check viz spec consistency, and verify the dashboard after creation by reading it back and executing its queries.
- **Chart rendering**: Complex chart types may show "No chart available" in the Omni UI if `config`, `visType`, or `prefersChart` are misconfigured. Default to `chartType: "table"` for reliable rendering, and configure chart visualizations in the Omni UI.
- **Every query must include at least one measure** — a query with only dimensions produces empty/nonsense tiles (e.g., just months with no data).
- **Use `identifier` not `id`** for all document API calls — `.id` is null for workbook-type documents and will silently fail.
- **Boolean filters may be silently dropped** when a `pivots` array is present (reported Omni bug). If boolean filters aren't applying, remove the pivot and test again.
- **Dashboard updates are full replacements** — `PUT /api/v1/documents/{documentId}` replaces the entire document state. Always read the existing document first and modify from there, or you'll lose tiles you didn't include.

## Prerequisites

```bash
# Verify the Omni CLI is installed — if not, ask the user to install it
# See: https://github.com/exploreomni/cli#readme
command -v omni >/dev/null || echo "ERROR: Omni CLI is not installed."
```

```bash
export OMNI_BASE_URL="https://yourorg.omniapp.co"
export OMNI_API_TOKEN="your-api-key"
```

## Discovering Commands

```bash
omni documents --help           # Document operations
omni dashboards --help          # Dashboard operations
omni models yaml-create --help  # Writing model YAML
```

## Dashboard Architecture

Omni dashboards are built from **documents** (workbooks). Each has:
- A **dashboard view** (the published, shareable layout)
- One or more **query tabs** (underlying queries)
- A **workbook model** (per-dashboard model customizations)

Documents can be created with full query and visualization configurations via `queryPresentations`. Fine-tuning tile layout is best done in the Omni UI.

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
      "visType": "basic",
      "fields": ["order_items.created_at[month]", "order_items.total_revenue"],
      "query": {
        "table": "order_items",
        "fields": ["order_items.created_at[month]", "order_items.total_revenue"],
        "sorts": [{ "column_name": "order_items.created_at[month]", "sort_descending": false }],
        "filters": { "order_items.created_at": "this quarter" },
        "limit": 100,
        "join_paths_from_topic_name": "order_items",
        "visConfig": { "chartType": "lineColor" }
      },
      "config": {}
    }
  ]
}'
```

> **Tip**: Default to `"config": {}` for reliable rendering — Omni will auto-generate chart config. For precise chart styling, build a reference dashboard in the UI and read it back via `GET /api/v1/documents/{documentId}`. See [references/queryPresentations.md](references/queryPresentations.md) for complete config examples by chart type (KPI, line, bar, area, pie, scatter, etc.).

#### queryPresentation Structure

See [references/queryPresentations.md](references/queryPresentations.md) for the complete reference — parameter tables for `queryPresentation` and `query` objects, chart type examples, and caveats when reusing presentations from existing dashboards. See [references/visConfig.md](references/visConfig.md) for the full `visConfig` and `config` object reference — all accepted `chartType` values, config structure for every chart family (cartesian, KPI, pie, funnel, sankey, heatmap, map), and worked examples.

**Key points:**
- `prefersChart` must be `true` to render a chart (otherwise always shows table)
- `visType`: `"omni-kpi"` for KPI tiles, `"basic"` for all other charts
- `visConfig` goes **inside** the `query` object (silently dropped if placed as sibling)
- `fields` must be duplicated at both the `queryPresentation` and `query` levels
- `modelId` is inherited from the document — not needed inside `query`
- Default to `"config": {}` for reliable rendering — Omni auto-generates chart config
- For full `visConfig` and `config` schema details, see [references/visConfig.md](references/visConfig.md)

**To learn the exact structure for a chart type**, build a reference dashboard in the Omni UI and read it back:

```bash
omni documents get <documentId>
```

**When reusing queryPresentations from existing documents**, always strip `model_extension_id` from query objects (causes "Chart unavailable" errors) and filter to only the tiles you want.

### Rename Document

```bash
omni documents update <documentId> --name "Q1 Revenue Report (Updated)" --clear-existing-draft
```

Pass `--clear-existing-draft` if the document has an existing draft, otherwise the API returns 409 Conflict.

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

Update the tiles, queries, filters, and visualizations on an existing dashboard using `PUT /api/v1/documents/{documentId}`. This is a **full replacement** — you must pass the complete desired state of the document, not just the fields you want to change.

> **Warning**: This endpoint only works with **dashboard documents**. Workbook-only documents are not supported and return 400.

> **Note**: This endpoint is documented at [docs.omni.co](https://docs.omni.co/api/documents/update-document) but may not appear in the OpenAPI spec at `/openapi.json` yet.

### Update Workflow

**Step 1 — Read the existing document** to get its current state:

```bash
omni documents get <documentId>
```

This returns the full document including `queryPresentations`, `filterConfig`, `filterOrder`, `modelId`, `name`, and other fields. Use this as your starting point.

**Step 2 — Modify the response** as needed:

- To **add a tile**: append a new entry to the `queryPresentations` array
- To **remove a tile**: remove it from the `queryPresentations` array
- To **edit a tile**: modify the relevant entry's `query`, `config`, `fields`, etc.
- To **update filters**: modify `filterConfig` and `filterOrder`

**Step 3 — PUT the updated document:**

```bash
# Note: Full document replacement via PUT is not yet available in the CLI.
# Use direct HTTP for now, or use omni documents update for partial updates (PATCH).
curl -L -X PUT "$OMNI_BASE_URL/api/v1/documents/{documentId}" \
  -H "Authorization: Bearer $OMNI_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "modelId": "your-model-id",
    "name": "Q1 Revenue Report",
    "facetFilters": false,
    "refreshInterval": null,
    "filterConfig": {},
    "filterOrder": [],
    "clearExistingDraft": true,
    "queryPresentations": [ ... ]
  }'
```

The `queryPresentations` array uses the same structure as document creation — see above.

### Required Fields

| Parameter | Type | Description |
|-----------|------|-------------|
| `modelId` | string | Model ID for query transformation |
| `name` | string | Document name (1–254 characters) |
| `facetFilters` | boolean | Enable facet filters on the dashboard |
| `refreshInterval` | integer or null | Auto-refresh interval in seconds (min 60), or `null` to disable |
| `filterConfig` | object | Dashboard filter configuration — pass `{}` for no filters |
| `filterOrder` | array | Ordered filter IDs — pass `[]` for no filters |
| `queryPresentations` | array | At least one query presentation required (same structure as document creation) |

### Optional Fields

| Parameter | Type | Description |
|-----------|------|-------------|
| `clearExistingDraft` | boolean | Discard existing draft before updating. **Required when the published document has a draft** — otherwise returns 409 Conflict. |
| `documentMetadata` | object | Presentation settings including filter collapsibility |

### Caveats

- **Full replacement**: Every `queryPresentation` you include becomes a tile. Any tile you omit from the array is removed. Always start from the existing document's `queryPresentations` and modify from there.
- **Draft conflict**: Published documents with existing drafts return 409 unless `clearExistingDraft: true` is set.
- See also [Caveats When Reusing queryPresentations](#caveats-when-reusing-querypresentations) (e.g., stripping `model_extension_id`).

## Updating a Dashboard's Model

Push custom dimensions and measures to a specific dashboard by writing to its workbook model. This is a two-step flow:

**Step 1 — get the document to find its `workbook_id`:**

```bash
omni documents get <documentId>
# → response includes "workbook_id"
```

**Step 2 — POST YAML to the workbook model:**

```bash
omni models yaml-create <workbookId> --body '{
  "fileName": "order_items.view",
  "yaml": "views:\n  order_items:\n    dimensions:\n      is_high_value:\n        sql: \"${sale_price} > 100\"\n        label: High Value Order\n    measures:\n      high_value_count:\n        sql: \"${order_items.id}\"\n        aggregate_type: count_distinct\n        label: High Value Orders"
}'
```

`fileName` must be `"model"`, `"relationships"`, or end with `.view` or `.topic`. The `yaml` value is a YAML string (not a JSON object). Writing to a workbook model skips git sync entirely — authorization is still checked against the underlying shared model's permissions.

## Dashboard Filters

### Get Current Filters

```bash
omni dashboards get-filters <dashboardId>
```

### Update Filters

Filters can be updated via two approaches:

1. **`PUT /api/v1/documents/{documentId}`** (recommended) — update filters as part of a full document update. Include `filterConfig` and `filterOrder` alongside `queryPresentations` and other required fields. See the [Update Existing Dashboard](#update-existing-dashboard) section.
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

The `identifier` comes from the document's `identifier` field in API responses (not `id`, which is null for workbooks).

## Validation Loops

Every dashboard build or update must include validation before and after creation. Broken tiles, bad field references, and misconfigured viz specs are silent failures — the dashboard renders but tiles show "Chart unavailable" or "No data" with no API-level error.

### Step 1: Validate the Model

Before building any queries, confirm the underlying model is healthy:

```bash
omni models validate <modelId>
```

Check the response for errors (not just warnings). If `is_warning` is `false` on any issue, the field or join may be broken and queries referencing it will fail silently on the dashboard.

### Step 2: Test Every Query via Execution

Run each planned query through `omni query run` **before** including it in a dashboard. This is the single most important validation step.

```bash
omni query run --body '{
  "query": {
    "modelId": "your-model-id",
    "table": "order_items",
    "fields": ["order_items.created_at[month]", "order_items.total_revenue"],
    "filters": { "order_items.created_at": "last 90 days" },
    "limit": 10,
    "join_paths_from_topic_name": "order_items"
  }
}'
```

**What to check in the response:**
- **No error field** — if the response contains an `error` key, the query is broken. Fix before proceeding.
- **`summary.row_count` > 0** — a query that returns zero rows will render as an empty tile. This may be correct (no data for the filter range) but is worth flagging.
- **Include your dashboard filters** — pass the same filters you plan to use in `filterConfig` as query-level filters here. This catches bad filter expressions (e.g., wrong field name, unsupported syntax) before they become dashboard-level problems.
- **Long-running queries** — if the response includes `remaining_job_ids`, poll with `omni query wait --job-ids <ids>` until complete, then check the final result for errors.

Do this for **every** query you plan to include as a tile. A dashboard with 5 tiles needs 5 validated queries.

### Step 3: Validate Viz Spec Consistency

Before assembling `queryPresentations`, check each tile's viz configuration against these rules. Mismatches cause "No chart available" or silent fallback to table rendering.

**Required consistency checks:**

| Rule | What to check |
|------|---------------|
| `prefersChart` must be `true` for charts | If `false` or omitted, Omni renders a table regardless of other viz settings |
| `visType` must match chart category | `"omni-kpi"` for KPI tiles, `"basic"` for all other chart types (line, bar, area, scatter, pie, table) |
| `visConfig.chartType` must be valid | Must be one of: `table`, `kpi`, `lineColor`, `barColor`, `areaColor`, `stackedBarColor`, `pie`, `scatter`, `heatmap`, `map` |
| `config` fields must match chart type | Cartesian charts (line, bar, area, scatter) require `mark`, `series`, `tooltip`, `version`, `behaviors`, `configType: "cartesian"`, `_dependentAxis` |
| `_dependentAxis` must match orientation | `"y"` for vertical charts (line, vertical bar, area, scatter), `"x"` for horizontal bar charts |
| `mark.type` must match `visConfig.chartType` | `lineColor` → `"line"`, `barColor`/`stackedBarColor` → `"bar"`, `areaColor` → `"area"`, `scatter` → `"point"` |
| `series[].yAxis` or `series[].xAxis` | Must use `yAxis: "y"` for vertical charts, `xAxis: "x"` for horizontal bars |
| KPI tiles need `markdownConfig` | `config.markdownConfig` array with at least one entry referencing a field from the query |
| `fields` must be duplicated | The `fields` array must appear at both the `queryPresentation` level AND inside the `query` object |
| Every query must have a measure | Queries with only dimensions produce empty/broken tiles |

> **Tip**: When unsure about a viz config, default to `"prefersChart": false` with `"config": {}` to render as a table. Tables always work. Configure charts in the Omni UI afterward.

### Step 4: Post-Creation Verification

After creating or updating a dashboard, always read it back and verify the tiles work:

**4a. Read back the document:**

```bash
omni documents get <documentIdentifier>
```

Check that:
- The response includes all expected `queryPresentations` (count matches what you sent)
- No `queryPresentations` entries have null or missing `query` objects
- The `identifier` is present (you'll need it for the share link)

**4b. Execute the dashboard's queries to verify they run:**

```bash
# Extract the queries powering the dashboard tiles
omni documents get-queries <documentIdentifier>
```

This returns the query objects for each tile. Run each one to confirm they execute without errors:

```bash
# For each query returned, execute it
omni query run --body '{
  "query": <query-object-from-get-queries>,
  "resultType": "csv"
}'
```

Using `"resultType": "csv"` makes it easy to spot-check that the data looks reasonable (correct columns, non-empty rows, expected value ranges).

**What to check:**
- Every tile's query executes without error
- `summary.row_count` > 0 for tiles that should show data
- No unexpected `remaining_job_ids` (which might indicate query timeout issues)

**4c. If any query fails:** The dashboard has a broken tile. Either update the document to fix the query (via `PUT /api/v1/documents/{documentId}`) or flag the issue to the user before sharing the link.

### Validation Checklist Summary

| Phase | Check | Tool |
|-------|-------|------|
| Pre-build | Model has no errors | `omni models validate <modelId>` |
| Pre-build | Each query executes successfully | `omni query run` per query |
| Pre-build | Each query returns rows | Check `summary.row_count` |
| Pre-build | Filters parse correctly | Include filters in `omni query run` |
| Pre-build | Viz specs are internally consistent | Manual check against rules above |
| Post-build | Document has all expected tiles | `omni documents get` and count `queryPresentations` |
| Post-build | All tile queries execute on the dashboard | `omni documents get-queries` + `omni query run` each |
| Post-build | Data looks correct | Spot-check CSV output for reasonableness |

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
5. **PUT the update** — `PUT /api/v1/documents/{documentId}` with the complete modified document and `clearExistingDraft: true`
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
- **Skill references**: [queryPresentations.md](references/queryPresentations.md) · [visConfig.md](references/visConfig.md) · [filterConfig.md](references/filterConfig.md)

## Related Skills

- **omni-model-explorer** — understand available fields
- **omni-model-builder** — create shared model fields
- **omni-query** — test queries before adding to dashboards
- **omni-content-explorer** — find existing dashboards to learn from
- **omni-embed** — embed dashboards you've built in external apps
