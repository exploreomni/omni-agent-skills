---
name: omni-content-builder
description: Create, update, and manage Omni Analytics documents and dashboards programmatically — document lifecycle, tiles, visualizations, filters, and layouts — using the REST API. Use this skill whenever someone wants to build a dashboard, create a workbook, add tiles or charts, configure dashboard filters, update an existing dashboard's model, set up a KPI view, create visualizations, lay out a dashboard, create a document, rename a workbook, delete a dashboard, move a document to a folder, duplicate a dashboard, or any variant of "build a dashboard for", "create a report showing", "add a chart to", "make a dashboard", "update the dashboard layout", "rename this document", "move to folder", or "delete this dashboard". Also use when modifying dashboard-level model customizations like workbook-specific joins or fields.
---

# Omni Content Builder

Create, update, and manage Omni documents and dashboards programmatically via the REST API — document lifecycle, workbook models, filters, and dashboard content.

> **Always check the official Omni docs first:** https://docs.omni.co/llms.txt
> This skill covers patterns not fully documented elsewhere — especially the `queryPresentations` format for creating dashboards with tiles.

> **Tip**: Use `omni-model-explorer` to understand available fields and `omni-content-explorer` to find existing dashboards to modify or learn from.

## Prerequisites

```bash
export OMNI_BASE_URL="https://yourorg.omniapp.co"
export OMNI_API_KEY="your-api-key"
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
        "name": "Total Revenue",
        "topicName": "order_items",
        "prefersChart": true,
        "visType": "omni-kpi",
        "fields": ["order_items.total_revenue"],
        "query": {
          "table": "order_items",
          "fields": ["order_items.total_revenue"],
          "join_paths_from_topic_name": "order_items",
          "visConfig": { "chartType": "kpi" }
        },
        "config": {
          "alignment": "left",
          "verticalAlignment": "top",
          "markdownConfig": [
            {
              "id": "kpi-1",
              "type": "number",
              "config": {
                "field": {
                  "row": "_first",
                  "field": { "name": "order_items.total_revenue", "pivotMap": {} },
                  "label": { "value": "Total Revenue" }
                },
                "descriptionBefore": ""
              }
            }
          ]
        }
      },
      {
        "name": "Monthly Revenue Trend",
        "description": "Revenue by month for the current quarter",
        "topicName": "order_items",
        "prefersChart": true,
        "visType": "basic",
        "fields": ["order_items.created_at[month]", "order_items.total_revenue"],
        "query": {
          "table": "order_items",
          "fields": [
            "order_items.created_at[month]",
            "order_items.total_revenue"
          ],
          "sorts": [
            { "column_name": "order_items.created_at[month]", "sort_descending": false }
          ],
          "filters": { "order_items.created_at": "this quarter" },
          "limit": 100,
          "join_paths_from_topic_name": "order_items",
          "visConfig": { "chartType": "lineColor" }
        },
        "config": {
          "x": { "field": { "name": "order_items.created_at[month]" } },
          "mark": { "type": "line" },
          "color": {},
          "series": [{ "field": { "name": "order_items.total_revenue" }, "yAxis": "y" }],
          "tooltip": [
            { "field": { "name": "order_items.created_at[month]" } },
            { "field": { "name": "order_items.total_revenue" } }
          ],
          "version": 0,
          "behaviors": { "stackMultiMark": false },
          "configType": "cartesian",
          "_dependentAxis": "y"
        }
      },
      {
        "name": "Revenue by Status",
        "topicName": "order_items",
        "prefersChart": true,
        "visType": "basic",
        "chartType": "barGrouped",
        "fields": ["order_items.status", "order_items.total_revenue"],
        "query": {
          "table": "order_items",
          "fields": [
            "order_items.status",
            "order_items.total_revenue"
          ],
          "sorts": [
            { "column_name": "order_items.total_revenue", "sort_descending": true }
          ],
          "limit": 10,
          "join_paths_from_topic_name": "order_items",
          "visConfig": { "chartType": "barColor" }
        },
        "config": {
          "y": { "field": { "name": "order_items.status" } },
          "mark": { "type": "bar" },
          "color": { "_stack": "group" },
          "series": [{ "field": { "name": "order_items.total_revenue" }, "xAxis": "x" }],
          "tooltip": [
            { "field": { "name": "order_items.status" } },
            { "field": { "name": "order_items.total_revenue" } }
          ],
          "version": 0,
          "behaviors": { "stackMultiMark": false },
          "configType": "cartesian",
          "_dependentAxis": "x"
        }
      }
    ]
  }'
```

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

The `config` object at the `queryPresentation` level defines the actual chart rendering. Its structure varies by chart type. The most reliable way to get the correct `config` for a given chart type is to **build the chart in the Omni UI and read it back**.

**KPI config shape:**
```json
{
  "alignment": "left",
  "verticalAlignment": "top",
  "markdownConfig": [
    {
      "id": "unique-id",
      "type": "number",
      "config": {
        "field": {
          "row": "_first",
          "field": { "name": "view.measure_name", "pivotMap": {} },
          "label": { "value": "Label Text" }
        },
        "descriptionBefore": ""
      }
    }
  ]
}
```

**Line chart config shape:**
```json
{
  "x": { "field": { "name": "view.date_field[month]" } },
  "mark": { "type": "line" },
  "color": {},
  "series": [{ "field": { "name": "view.measure_name" }, "yAxis": "y" }],
  "tooltip": [
    { "field": { "name": "view.date_field[month]" } },
    { "field": { "name": "view.measure_name" } }
  ],
  "version": 0,
  "behaviors": { "stackMultiMark": false },
  "configType": "cartesian",
  "_dependentAxis": "y"
}
```

**Bar chart config shape** (horizontal — dimension on y-axis):
```json
{
  "y": { "field": { "name": "view.dimension_name" } },
  "mark": { "type": "bar" },
  "color": { "_stack": "group" },
  "series": [{ "field": { "name": "view.measure_name" }, "xAxis": "x" }],
  "tooltip": [
    { "field": { "name": "view.dimension_name" } },
    { "field": { "name": "view.measure_name" } }
  ],
  "version": 0,
  "behaviors": { "stackMultiMark": false },
  "configType": "cartesian",
  "_dependentAxis": "x"
}
```

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

Returns the complete `queryPresentations` array including `prefersChart`, `visType`, `config`, `topicName`, and the full `query` object for each tile — use this as the source of truth when recreating or templating dashboards.

> **Note**: The `/queries` endpoint (`GET /documents/{documentId}/queries`) only returns the inner `query` object and omits presentation-level fields like `topicName`. Prefer `get-dashboard-document` when you need the full structure to pass to `create-document`.

> **Tip**: Build a reference dashboard in the Omni UI with the chart types and styling you want, then read it via `get-dashboard-document` to capture the exact `queryPresentations` structure to use as a template.

#### Caveats when using queryPresentations from an existing document

- **Filter to the tiles you want**: `get-dashboard-document` returns all queries including workbook-only tabs not shown on the dashboard. Pass only the `queryPresentations` you want as visible tiles — every entry you include will become a visible tile in the new document.
- **Strip `model_extension_id`**: Some queries contain a `model_extension_id` that references a model extension scoped to the source document. These IDs are not valid in a new document and will cause "Chart unavailable" errors. Remove `model_extension_id` from each query object before posting.
- **Queries without a topic are expected**: SQL-mode queries and tab-selector queries (`visType: "spreadsheet-tab"`) will not have a `topicName` — this is correct, do not add one.

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

```bash
curl -L -X PUT "$OMNI_BASE_URL/api/v1/dashboards/{dashboardId}/filters" \
  -H "Authorization: Bearer $OMNI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "filters": {
      "order_items.created_at": {
        "type": "date",
        "label": "Date Range",
        "kind": "TIME_FOR_INTERVAL_DURATION",
        "ui_type": "PAST",
        "left_side": "6 months ago",
        "right_side": "6 months"
      },
      "users.state": {
        "type": "string",
        "label": "State",
        "kind": "EQUALS",
        "values": []
      }
    }
  }'
```

### Filter Types

**Date Range** — `type: "date"`, `kind: "TIME_FOR_INTERVAL_DURATION"`

**String Dropdown** — `type: "string"`, `kind: "EQUALS"`, `values: []`

**Boolean Toggle** — `type: "boolean"`, `is_negative: false`

**Hidden Filter** — any filter with `"hidden": true` (applied but not visible)

**Date Granularity Picker** — `type: "FIELD_SELECTION"`, `kind: "TIMEFRAME"` with options array

## Recommended Build Workflows

### API-First (Full Programmatic Creation)

1. **Prepare the Model** — use `omni-model-builder` for shared fields, or `models/{workbookId}/yaml` for dashboard-specific fields
2. **Read a Reference Dashboard** — use `GET /api/v1/documents/{id}` on a dashboard built in the UI to capture the full `queryPresentations` structure: `prefersChart`, `visType`, `config`, field names, filter syntax
3. **Create Document with queryPresentations** — create the document with all queries, `prefersChart`, `visType`, and `config` in a single API call
4. **Set Up Filters** — add dashboard-level filters via the filters API
5. **Refine in UI** — adjust tile layout, fine-tune styling as needed

### UI-First (Hybrid Approach)

1. **Prepare the Model** — use `omni-model-builder` for shared fields, or `models/{workbookId}/yaml` for dashboard-specific fields
2. **Set Up Filters** — date range + granularity picker + key entity pickers + hidden business logic filters
3. **Build Layout in UI** — add tiles, choose viz types, arrange the grid
4. **Iterate via API** — update filters, modify model fields, extract queries

## Dashboard Downloads

```bash
# Start async download
curl -L -X POST "$OMNI_BASE_URL/api/v1/dashboards/{dashboardId}/download" \
  -H "Authorization: Bearer $OMNI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "format": "pdf" }'

# Poll job
curl -L "$OMNI_BASE_URL/api/v1/jobs/{jobId}/status" \
  -H "Authorization: Bearer $OMNI_API_KEY"
```

## Docs Reference

- [Documents API](https://docs.omni.co/api/documents.md) · [Dashboard Filters](https://docs.omni.co/api/dashboard-filters.md) · [Dashboard Downloads](https://docs.omni.co/api/dashboard-downloads.md) · [Query API](https://docs.omni.co/api/queries.md) · [Schedules API](https://docs.omni.co/api/schedules.md) · [Visualization Types](https://docs.omni.co/visualize-present/visualizations.md)

## Related Skills

- **omni-model-explorer** — understand available fields
- **omni-model-builder** — create shared model fields
- **omni-query** — test queries before adding to dashboards
- **omni-content-explorer** — find existing dashboards to learn from
- **omni-embed** — embed dashboards you've built in external apps
