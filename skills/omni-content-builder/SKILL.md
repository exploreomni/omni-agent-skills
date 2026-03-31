---
name: omni-content-builder
description: Create, update, and manage Omni Analytics documents and dashboards programmatically — document lifecycle, tiles, visualizations, filters, and layouts — using the REST API. Use this skill whenever someone wants to build a dashboard, create a workbook, add tiles or charts, configure dashboard filters, update an existing dashboard's model, set up a KPI view, create visualizations, lay out a dashboard, create a document, rename a workbook, delete a dashboard, move a document to a folder, duplicate a dashboard, or any variant of "build a dashboard for", "create a report showing", "add a chart to", "make a dashboard", "update the dashboard layout", "rename this document", "move to folder", or "delete this dashboard". Also use when modifying dashboard-level model customizations like workbook-specific joins or fields.
---

# Omni Content Builder

Create, update, and manage Omni documents and dashboards programmatically via the REST API — document lifecycle, workbook models, filters, and dashboard content.

> **Tip**: Use `omni-model-explorer` to understand available fields and `omni-content-explorer` to find existing dashboards to modify or learn from.

## Known Issues & Safe Defaults

- **Always test queries before creating a dashboard** — run each planned query via `POST /api/v1/query/run` first, including the filters you intend to use. This catches bad field names, missing joins, and malformed filter expressions before they become broken tiles.
- **Chart rendering**: Complex chart types may show "No chart available" in the Omni UI if `config`, `visType`, or `prefersChart` are misconfigured. Default to `chartType: "table"` for reliable rendering, and configure chart visualizations in the Omni UI.
- **Every query must include at least one measure** — a query with only dimensions produces empty/nonsense tiles (e.g., just months with no data).
- **Use `identifier` not `id`** for all document API calls — `.id` is null for workbook-type documents and will silently fail.
- **Boolean filters may be silently dropped** when a `pivots` array is present (reported Omni bug). If boolean filters aren't applying, remove the pivot and test again.
- **Dashboard updates are full replacements** — `PUT /api/v1/documents/{documentId}` replaces the entire document state. Always read the existing document first and modify from there, or you'll lose tiles you didn't include.

## Prerequisites

```bash
export OMNI_BASE_URL="https://yourorg.omniapp.co"
export OMNI_API_KEY="your-api-key"
```

## API Discovery

When unsure whether an endpoint or parameter exists, fetch the OpenAPI spec:

```bash
curl -L "$OMNI_BASE_URL/openapi.json" \
  -H "Authorization: Bearer $OMNI_API_KEY"
```

Use this to verify endpoints, available parameters, and request/response schemas before making calls.

## Dashboard Architecture

Omni dashboards are built from **documents** (workbooks). Each has:
- A **dashboard view** (the published, shareable layout)
- One or more **query tabs** (underlying queries)
- A **workbook model** (per-dashboard model customizations)

Documents can be created with full query and visualization configurations via `queryPresentations`. Fine-tuning tile layout is best done in the Omni UI.

## Document Management

### Create Document (Name Only)

```bash
curl -L -X POST "$OMNI_BASE_URL/api/v1/documents" \
  -H "Authorization: Bearer $OMNI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "modelId": "your-model-id",
    "name": "Q1 Revenue Report"
  }'
```

Returns the new document's `identifier`, `workbookId`, and `dashboardId`.

### Create Document with Queries and Visualizations

Use `queryPresentations` to create a document pre-populated with query tabs and visualization configurations.

> **Doc gap**: The [create-document API docs](https://docs.omni.co/api/documents/create-document.md) mention queryPresentations but don't show the complete structure. This section documents the full format.

```bash
curl -L -X POST "$OMNI_BASE_URL/api/v1/documents" \
  -H "Authorization: Bearer $OMNI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
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

#### Key Parameters (not fully documented elsewhere)

| Parameter | Notes |
|-----------|-------|
| `modelId` | Use the **base shared model UUID**, not a branchId. Get this from the List Models API. |
| Field format | `table.field_name` or `table.field_name[week\|month\|day\|quarter\|year]` for time granularity |
| `sorts` | `column_name` must match the **exact field string** (e.g., `"order_items.created_at[month]"`), with `sort_descending` boolean |

#### queryPresentation Object Reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `name` | Yes | Tile/tab title |
| `topicName` | Recommended | Topic name for the query — set this whenever querying from a topic. Ensures correct join context in the dashboard. |
| `prefersChart` | Yes | **Must be `true` to render a chart.** Without this, Omni always shows the results table regardless of any other vis settings. |
| `visType` | Yes | Visualization renderer: `"omni-kpi"` for KPI tiles, `"basic"` for all standard charts (line, bar, area, scatter, pie, etc.). |
| `fields` | Yes | Duplicate of `query.fields` — must be present at this level too. |
| `config` | Yes | Chart-specific configuration object. Shape varies by chart type — read a reference dashboard to get the exact structure. |
| `chartType` | No | Optional chart subtype at the presentation level (e.g. `"barGrouped"`). |
| `description` | No | Tile description. |
| `query` | Yes | Query definition (see below). |

#### Query Object Reference

The `query` object within each query presentation uses the same structure as the [Query API](https://docs.omni.co/api/queries.md):

| Parameter | Required | Description |
|-----------|----------|-------------|
| `table` | Yes | Base view name |
| `fields` | Yes | Array of `view.field_name` references (supports timeframe brackets like `[month]`) |
| `sorts` | No | Array of `{ "column_name": "...", "sort_descending": bool }` |
| `filters` | No | Object of `{ "field_name": "expression" }` — supports `"last 90 days"`, `"this quarter"`, `">100"`, etc. |
| `limit` | No | Row limit (default 1000, max 50000) |
| `join_paths_from_topic_name` | Recommended | Topic name for join resolution — set this alongside `topicName` on the parent queryPresentation. |
| `pivots` | No | Array of field names to pivot on |

> **Note**: `modelId` is not needed inside the query object — it's inherited from the document's top-level `modelId`.

#### visConfig Object

`visConfig` belongs **inside the `query` object** — not at the `queryPresentation` level. When passed as a sibling of `query`, it is silently dropped by the API.

`visConfig` alone does **not** control chart rendering. It stores the chart type hint on the query, but the actual rendering is driven by `prefersChart`, `visType`, and `config` at the `queryPresentation` level.

**chartType values**:

| chartType | Visualization |
|-----------|--------------|
| `kpi` | KPI / single value |
| `lineColor` | Line chart |
| `barColor` | Bar chart |
| `areaColor` | Area chart |
| `stackedBarColor` | Stacked bar chart |
| `pie` | Pie / donut chart |
| `scatter` | Scatter plot |
| `heatmap` | Heatmap |
| `map` | Map visualization |
| `table` | Data table |

#### config Object

The `config` object at the `queryPresentation` level defines the actual chart rendering. Its structure varies by chart type — see [references/queryPresentations.md](references/queryPresentations.md) for complete config examples by chart type.

The most reliable way to get the correct `config` for a given chart type is to **build the chart in the Omni UI and read it back** via `GET /api/v1/documents/{documentId}`.

### Discovering the Full queryPresentation Structure from Existing Dashboards

The most reliable way to learn `config`, `visType`, and field names is to read an existing dashboard document:

**Step 1: Find a reference dashboard**

```bash
curl -L "$OMNI_BASE_URL/api/v1/documents" \
  -H "Authorization: Bearer $OMNI_API_KEY"
```

**Step 2: Get its full document**

```bash
curl -L "$OMNI_BASE_URL/api/v1/documents/{documentId}" \
  -H "Authorization: Bearer $OMNI_API_KEY"
```

Returns the complete `queryPresentations` array including `topicName`, `visConfig`, `config`, and the full `query` object for each tile — use this as the source of truth when recreating or templating dashboards.

> **Tip**: Build a reference dashboard in the Omni UI with the chart types and styling you want, then read it via `GET /api/v1/documents/{documentId}` to capture the exact `queryPresentations` structure to use as a template.

#### Caveats When Reusing queryPresentations

These apply when copying queryPresentations from an existing document (for both creating new dashboards and updating existing ones):

- **Strip `model_extension_id`** from each query object — these reference model extensions scoped to the source document and will cause "Chart unavailable" errors.
- **Filter to the tiles you want** — `GET /api/v1/documents/{id}` returns all queries including workbook-only tabs not shown on the dashboard. Only include the `queryPresentations` you want as visible tiles.
- **Queries without `topicName` are valid** — SQL-mode and tab-selector queries won't have a `topicName`. Do not add one.

### Rename Document

```bash
curl -L -X PATCH "$OMNI_BASE_URL/api/v1/documents/{documentId}" \
  -H "Authorization: Bearer $OMNI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Q1 Revenue Report (Updated)",
    "clearExistingDraft": true
  }'
```

Set `clearExistingDraft: true` if the document has an existing draft, otherwise the API returns 409 Conflict.

### Delete Document

```bash
curl -L -X DELETE "$OMNI_BASE_URL/api/v1/documents/{documentId}" \
  -H "Authorization: Bearer $OMNI_API_KEY"
```

Soft-deletes the document (moves to Trash).

### Move Document

```bash
curl -L -X PUT "$OMNI_BASE_URL/api/v1/documents/{documentId}/move" \
  -H "Authorization: Bearer $OMNI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "folderPath": "/Marketing/Reports",
    "scope": "organization"
  }'
```

Use `"folderPath": null` to move to root. `scope` is optional — auto-computed from the destination folder.

### Duplicate Document

```bash
curl -L -X POST "$OMNI_BASE_URL/api/v1/documents/{documentId}/duplicate" \
  -H "Authorization: Bearer $OMNI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Copy of Q1 Revenue Report",
    "folderPath": "/Marketing/Reports"
  }'
```

Only published documents can be duplicated. Draft documents return 404.

## Update Existing Dashboard

Update the tiles, queries, filters, and visualizations on an existing dashboard using `PUT /api/v1/documents/{documentId}`. This is a **full replacement** — you must pass the complete desired state of the document, not just the fields you want to change.

> **Warning**: This endpoint only works with **dashboard documents**. Workbook-only documents are not supported and return 400.

> **Note**: This endpoint is documented at [docs.omni.co](https://docs.omni.co/api/documents/update-document) but may not appear in the OpenAPI spec at `/openapi.json` yet.

### Update Workflow

**Step 1 — Read the existing document** to get its current state:

```bash
curl -L "$OMNI_BASE_URL/api/v1/documents/{documentId}" \
  -H "Authorization: Bearer $OMNI_API_KEY"
```

This returns the full document including `queryPresentations`, `filterConfig`, `filterOrder`, `modelId`, `name`, and other fields. Use this as your starting point.

**Step 2 — Modify the response** as needed:

- To **add a tile**: append a new entry to the `queryPresentations` array
- To **remove a tile**: remove it from the `queryPresentations` array
- To **edit a tile**: modify the relevant entry's `query`, `config`, `fields`, etc.
- To **update filters**: modify `filterConfig` and `filterOrder`

**Step 3 — PUT the updated document:**

```bash
curl -L -X PUT "$OMNI_BASE_URL/api/v1/documents/{documentId}" \
  -H "Authorization: Bearer $OMNI_API_KEY" \
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
curl -L "$OMNI_BASE_URL/api/v1/documents/{documentId}" \
  -H "Authorization: Bearer $OMNI_API_KEY"
# → response includes "workbook_id"
```

**Step 2 — POST YAML to the workbook model:**

```bash
curl -L -X POST "$OMNI_BASE_URL/api/unstable/models/{workbookId}/yaml" \
  -H "Authorization: Bearer $OMNI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "fileName": "order_items.view",
    "yaml": "views:\n  order_items:\n    dimensions:\n      is_high_value:\n        sql: \"${sale_price} > 100\"\n        label: High Value Order\n    measures:\n      high_value_count:\n        sql: \"${order_items.id}\"\n        aggregate_type: count_distinct\n        label: High Value Orders"
  }'
```

`fileName` must be `"model"`, `"relationships"`, or end with `.view` or `.topic`. The `yaml` value is a YAML string (not a JSON object). Writing to a workbook model skips git sync entirely — authorization is still checked against the underlying shared model's permissions.

## Dashboard Filters

### Get Current Filters

```bash
curl -L "$OMNI_BASE_URL/api/v1/dashboards/{dashboardId}/filters" \
  -H "Authorization: Bearer $OMNI_API_KEY"
```

### Update Filters

Filters can be updated via two approaches:

1. **`PUT /api/v1/documents/{documentId}`** (recommended) — update filters as part of a full document update. Include `filterConfig` and `filterOrder` alongside `queryPresentations` and other required fields. See the [Update Existing Dashboard](#update-existing-dashboard) section.
2. **`PATCH /api/v1/dashboards/{id}/filters`** — partial filter update. Has been reported to return 405 or 500 in some configurations.

For **new dashboards**, the most reliable way is to include `filterConfig` and `filterOrder` in the initial `POST /api/v1/documents` call. See [references/filterConfig.md](references/filterConfig.md) for complete examples of each filter type.

```bash
curl -L -X POST "$OMNI_BASE_URL/api/v1/documents" \
  -H "Authorization: Bearer $OMNI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
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

The keys in `filterConfig` (e.g., `"date_filter"`) are arbitrary IDs — they must match the entries in `filterOrder`. To learn the exact filter structure, read filters from an existing dashboard with `GET /api/v1/dashboards/{dashboardId}/filters`.

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

## Recommended Build Workflows

### API-First (Full Programmatic Creation)

1. **Discover fields** — use `omni-model-explorer` to find topic + fields
2. **Test each query** — run every query you plan to include via `POST /api/v1/query/run` (using `omni-query`) before building the dashboard. Include the same filters you plan to use in `filterConfig` as query-level filters to confirm they parse correctly. This catches field name typos, missing join paths, bad filter expressions, and permission errors before they become broken tiles.
3. **Create document** — single `POST /api/v1/documents` with `queryPresentations` + `filterConfig` + `filterOrder` all in one call
4. **Share the link** — return `{OMNI_BASE_URL}/dashboards/{identifier}` to the user
5. **Refine in UI** — tile layout, chart styling, and advanced config are best done in the Omni UI

### Update Existing Dashboard

1. **Find the dashboard** — use `omni-content-explorer` or `GET /api/v1/documents` to locate it
2. **Read its current state** — `GET /api/v1/documents/{documentId}` to get the full document including `queryPresentations`, `filterConfig`, etc.
3. **Modify** — add, remove, or edit entries in the `queryPresentations` array; update `filterConfig`/`filterOrder` as needed
4. **PUT the update** — `PUT /api/v1/documents/{documentId}` with the complete modified document and `clearExistingDraft: true`
5. **Share the link** — return `{OMNI_BASE_URL}/dashboards/{identifier}` to the user

### UI-First (Hybrid Approach)

1. **Prepare the Model** — use `omni-model-builder` for shared fields, or `update-model` for dashboard-specific fields
2. **Build in UI** — add tiles, choose viz types, arrange the grid, set filters
3. **Iterate via API** — update model fields, extract queries for reuse

## Dashboard Downloads

```bash
# Start async download
curl -L -X POST "$OMNI_BASE_URL/api/v1/dashboards/{dashboardId}/download" \
  -H "Authorization: Bearer $OMNI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "format": "pdf" }'

# Poll job
curl -L "$OMNI_BASE_URL/api/v1/dashboards/{dashboardId}/download/{jobId}/status" \
  -H "Authorization: Bearer $OMNI_API_KEY"
```

## Docs Reference

- [Documents API](https://docs.omni.co/api/documents.md) · [Update Document](https://docs.omni.co/api/documents/update-document) · [Dashboard Filters](https://docs.omni.co/api/dashboard-filters.md) · [Dashboard Downloads](https://docs.omni.co/api/dashboard-downloads.md) · [Query API](https://docs.omni.co/api/queries.md) · [Schedules API](https://docs.omni.co/api/schedules.md) · [Visualization Types](https://docs.omni.co/visualize-present/visualizations.md)

## Related Skills

- **omni-model-explorer** — understand available fields
- **omni-model-builder** — create shared model fields
- **omni-query** — test queries before adding to dashboards
- **omni-content-explorer** — find existing dashboards to learn from
- **omni-embed** — embed dashboards you've built in external apps
