# queryPresentations Reference

Complete reference for queryPresentation objects — parameter tables, the visualization-config structure, chart type examples, and caveats for reusing presentations from existing dashboards.

Every chart `queryPresentation` requires: `name`, `prefersChart: true`, `chartType`, `visConfig`, `fields`, and `query`. The `visConfig.config` shape varies by chart family — the examples below show the exact structure for each.

## Table of Contents

- [Where the visualization config lives](#where-the-visualization-config-lives-read-this-first) — the #1 gotcha
- [Key Parameters](#key-parameters)
- [queryPresentation Object Parameters](#querypresentation-object-parameters)
- [Query Object Parameters](#query-object-parameters)
- [chartType values (summary)](#charttype-values-summary)
- [Discovering the Full Structure from Existing Dashboards](#discovering-the-full-structure-from-existing-dashboards)
- [Caveats When Reusing queryPresentations](#caveats-when-reusing-querypresentations)
- [Chart Type Examples](#chart-type-examples)
- [Cartesian Config Fields](#cartesian-config-fields-visconfigconfig)
- [Quick Reference: chartType → visType → config](#quick-reference-charttype--vistype--config)

## Where the visualization config lives (read this first)

This is the single most common source of "my chart renders as a table / as the wrong chart type" bugs. Get this right and everything else follows.

A chart is defined by **two queryPresentation-level fields**:

| Field | Where | Purpose |
|-------|-------|---------|
| `chartType` | top level of the queryPresentation | The chart type — must be a valid enum value (see [visConfig.md](visConfig.md)). |
| `visConfig` | top level of the queryPresentation | An object `{ config, visType, fields }` holding the rendering spec. The spec goes in `visConfig.config`. |

> **The rendering spec belongs in `visConfig.config` — NOT in a top-level `config` key.** A bare top-level `config` on the queryPresentation is **silently dropped** by the create/update endpoints. Likewise, putting only `visConfig.chartType` inside the `query` object is **not enough** — that is just a hint on the query and does not, by itself, produce the chart. The tile is driven by the queryPresentation-level `chartType` + `visConfig`.

### Canonical structure

```json
{
  "name": "My Tile",
  "topicName": "order_items",
  "prefersChart": true,
  "chartType": "columnStacked",
  "visConfig": {
    "config": { "configType": "cartesian", "_dependentAxis": "y", "...": "family-specific spec" },
    "visType": "basic",
    "fields": ["order_items.created_at[month]", "order_items.status", "order_items.total_revenue"]
  },
  "fields": ["order_items.created_at[month]", "order_items.status", "order_items.total_revenue"],
  "query": {
    "table": "order_items",
    "fields": ["order_items.created_at[month]", "order_items.status", "order_items.total_revenue"],
    "join_paths_from_topic_name": "order_items",
    "visConfig": { "chartType": "columnStacked" }
  }
}
```

> **About `automaticVis`:** the create/update endpoints set the stored `automaticVis` from `prefersChart` (`prefersChart: true` → `automaticVis: true`). This is harmless: `automaticVis` only governs whether the tile *defaults* to the chart view vs. the data table — it does **not** discard the explicit `chartType`/`visConfig.config` you provided. A tile created with `automaticVis: true` and an explicit `columnStacked` spec still renders as a stacked column chart.

## Key Parameters

| Parameter | Notes |
|-----------|-------|
| `modelId` | Use the **base shared model UUID**, not a branchId. Get this from the List Models API. (Top level of the document, not the queryPresentation.) |
| Field format | `table.field_name` or `table.field_name[week\|month\|day\|quarter\|year]` for time granularity |
| `sorts` | `column_name` must match the **exact field string** (e.g., `"order_items.created_at[month]"`), with `sort_descending` boolean |

## queryPresentation Object Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `name` | Yes | Tile/tab title |
| `topicName` | Recommended | Topic name for the query — set this whenever querying from a topic. Ensures correct join context in the dashboard. |
| `prefersChart` | Yes (charts) | **Must be `true` to render a chart.** Without it, Omni always shows the results table regardless of any other vis settings. |
| `chartType` | Yes (charts) | The chart type enum value (e.g. `"columnStacked"`, `"lineColor"`, `"pie"`, `"kpi"`). See the full list in [visConfig.md](visConfig.md). |
| `visConfig` | Yes (charts) | `{ config, visType, fields }`. `config` is the rendering spec (shape varies by family); `visType` is the renderer; `fields` mirrors the query fields. |
| `fields` | Yes | Duplicate of `query.fields` — must be present at this level too. |
| `description` | No | Tile description. |
| `query` | Yes | Query definition (see below). |

> *(charts)* in the Required column means the field is required **for chart tiles**; a plain table tile can omit it (`prefersChart: false`, `visConfig.config: {}`).

### visConfig object

| Field | Required | Description |
|-------|----------|-------------|
| `config` | Yes (charts) | The chart rendering spec. Cartesian families carry `configType: "cartesian"`; see per-family shapes in [visConfig.md](visConfig.md). |
| `visType` | Yes (charts) | Renderer: `"basic"` for cartesian/pie/heatmap/boxplot, `"omni-kpi"` for KPI, `"funnel"`, `"sankey"`, `"map"` (point **and** region/choropleth maps), `"omni-table"` for tables. |
| `fields` | Recommended | The fields the visualization uses; mirror `query.fields`. |

## Query Object Parameters

The `query` object within each query presentation uses the same structure as the [Query API](https://docs.omni.co/api/queries.md):

| Parameter | Required | Description |
|-----------|----------|-------------|
| `table` | Yes | The topic's **base view** (not a joined view) |
| `fields` | Yes | Array of `view.field_name` references (supports timeframe brackets like `[month]`) |
| `sorts` | No | Array of `{ "column_name": "...", "sort_descending": bool }` |
| `filters` | No | Object of `{ "field_name": "expression" }` — supports `"last 90 days"`, `"this quarter"`, `">100"`, etc. |
| `limit` | No | Row limit (default 1000, max 50000) |
| `join_paths_from_topic_name` | Strongly recommended | The topic name — resolves joins from the topic's base view so joined-view fields work. Set alongside `topicName` on the parent queryPresentation. |
| `pivots` | No | Array of field names to pivot on. A color/stack dimension (e.g. for a stacked chart) must be pivoted. |
| `visConfig` | No | Optional `{ "chartType": "..." }` hint stored on the query. Does **not** drive the tile by itself — set `chartType` + `visConfig` at the queryPresentation level for that. |

> **Note**: `modelId` is not needed inside the query object — it's inherited from the document's top-level `modelId`.

> **Querying a topic — base view + join path.** Set `table` to the topic's **base view**, pass `join_paths_from_topic_name: <topic>`, and set `topicName` on the parent queryPresentation. Joined-view fields (e.g. `users.state` on an `order_items` topic) resolve through the topic's join map — keep `table` at the base view, not the joined view. For the full mechanics, the omit-it failure mode, and verifying with `omni models get-topic` (`base_view_name`/`join_via_map`), see **`omni-query`**'s *Build queries on a topic*. (For *choosing* which topic, or when to extend/create one, see `omni-query` and `omni-model-builder`.)

## chartType values (summary)

A stacked **column** is vertical; a stacked **bar** is horizontal — Omni distinguishes the two. See [visConfig.md](visConfig.md) for the full supported list and the `chartType → visType → configType` mapping.

| chartType | Visualization |
|-----------|--------------|
| `kpi` | KPI / single value |
| `line`, `lineColor` | Line chart |
| `column`, `columnGrouped`, `columnStacked`, `columnStackedPercentage` | Vertical bars (column) |
| `bar`, `barGrouped`, `barStacked`, `barStackedPercentage` | Horizontal bars |
| `area`, `areaStacked`, `areaStackedPercentage` | Area chart |
| `point`, `pointColor`, `pointSize`, `pointSizeColor` | Scatter / bubble |
| `barLine` | Combo bar + line |
| `pie` | Pie / donut chart |
| `funnel` | Funnel chart |
| `sankey` | Sankey flow diagram |
| `heatmap` | Heatmap |
| `boxplot` | Box-and-whisker plot |
| `map` | Point map (lat/lng) |
| `regionMap` | Choropleth / filled region map |
| `table` | Data table |

> **Not valid**: `barColor`, `areaColor`, `stackedBarColor`, `scatter`, `lineColor`-style names for bar/area. Earlier versions of this doc used `barColor`/`areaColor`/`stackedBarColor` — those are **not** in Omni's `chartType` enum and will be rejected. Use `column`/`bar`, `area`, and `columnStacked`/`barStacked` respectively. (`lineColor`, `pointColor`, `pointSize`, `pointSizeColor` *are* valid.)

## Discovering the Full Structure from Existing Dashboards

The most reliable way to learn the exact `config` for a chart family (especially the less common ones) is to build it once in the Omni UI and read it back:

```bash
omni documents get <documentId>
```

Returns the complete `queryPresentations` array including `topicName`, `visConfig` (with `config`, `visType`, `fields`), and the full `query` object for each tile — use this as the source of truth when recreating or templating dashboards.

## Caveats When Reusing queryPresentations

These apply when copying queryPresentations from an existing document (for both creating new dashboards and updating existing ones):

- **Strip `model_extension_id`** from each query object — these reference model extensions scoped to the source document and will cause "Chart unavailable" errors.
- **Filter to the tiles you want** — `omni documents get` returns all queries including workbook-only tabs not shown on the dashboard. Only include the `queryPresentations` you want as visible tiles.
- **Queries without `topicName` are valid** — SQL-mode and tab-selector queries won't have a `topicName`. Do not add one.
- **Do not save known-broken query-level filters** — if `omni query run` rejects a tile query filter with a server-side parsing error, validate the unfiltered base query once. Do not save the broken filter into the tile; either use a verified dashboard-level `filterConfig` fallback or leave the dashboard unchanged and report the blocker.
- **Bound server-side filter failures** — if updating an existing document fails with a server-side filter or document validation error, stop after one corrected retry. The stored dashboard can contain filter state that the write path cannot validate; repeated filter rewrites, import/export attempts, or draft probing are usually wasted work.
- **Check readback for dropped presentation fields** — after creating or updating a dashboard, read it back (`omni documents get` or `omni unstable documents-export`) and verify each tile still has `visConfig.config` populated (not `{}`) and `visConfig.chartType` set. If only the query persisted and the spec was dropped, the payload almost certainly put the spec in a top-level `config` instead of `visConfig.config` — fix the shape and retry.

## Chart Type Examples

All cartesian examples below share the same shape: `chartType` + `visConfig: { config, visType, fields }` at the queryPresentation level, with the spec in `visConfig.config`.

### Table (Safe Default)

The simplest and most reliable tile. Use when unsure about chart config.

```json
{
  "name": "Orders by Status",
  "topicName": "order_items",
  "prefersChart": false,
  "chartType": "table",
  "visConfig": { "config": {}, "visType": "omni-table", "fields": ["order_items.status", "order_items.count", "order_items.total_revenue"] },
  "fields": ["order_items.status", "order_items.count", "order_items.total_revenue"],
  "query": {
    "table": "order_items",
    "fields": ["order_items.status", "order_items.count", "order_items.total_revenue"],
    "sorts": [{ "column_name": "order_items.total_revenue", "sort_descending": true }],
    "limit": 100,
    "join_paths_from_topic_name": "order_items",
    "visConfig": { "chartType": "table" }
  }
}
```

Key differences from chart types: `prefersChart` is `false`, and `visConfig.config` is an empty object `{}`.

### KPI (Single Value)

Displays one or more big numbers. Uses `visType: "omni-kpi"` and `chartType: "kpi"`. No `configType`.

```json
{
  "name": "Total Revenue",
  "topicName": "order_items",
  "prefersChart": true,
  "chartType": "kpi",
  "visConfig": {
    "visType": "omni-kpi",
    "fields": ["order_items.total_revenue"],
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
  "fields": ["order_items.total_revenue"],
  "query": {
    "table": "order_items",
    "fields": ["order_items.total_revenue"],
    "join_paths_from_topic_name": "order_items",
    "visConfig": { "chartType": "kpi" }
  }
}
```

### KPI with multiple values

Add more entries to `markdownConfig`, each with a unique `id`:

```json
"markdownConfig": [
  {
    "id": "kpi-revenue",
    "type": "number",
    "config": {
      "field": {
        "row": "_first",
        "field": { "name": "order_items.total_revenue", "pivotMap": {} },
        "label": { "value": "Revenue" }
      },
      "descriptionBefore": ""
    }
  },
  {
    "id": "kpi-orders",
    "type": "number",
    "config": {
      "field": {
        "row": "_first",
        "field": { "name": "order_items.count", "pivotMap": {} },
        "label": { "value": "Orders" }
      },
      "descriptionBefore": ""
    }
  }
]
```

### KPI config fields

| Field | Required | Description |
|-------|----------|-------------|
| `alignment` | No | Horizontal: `"left"`, `"center"`, `"right"` |
| `verticalAlignment` | No | Vertical: `"top"`, `"center"`, `"bottom"` |
| `markdownConfig` | Yes | Array of KPI value entries |
| `markdownConfig[].id` | Yes | Unique string ID for this entry |
| `markdownConfig[].type` | Yes | `"number"` for a numeric value (other types: `comparison`, `sparkline`, `progress`, `text`, `image`) |
| `markdownConfig[].config.field.row` | Yes | Always `"_first"` |
| `markdownConfig[].config.field.field.name` | Yes | Fully qualified field name (e.g., `"order_items.total_revenue"`) |
| `markdownConfig[].config.field.field.pivotMap` | Yes | Empty object `{}` unless using pivots |
| `markdownConfig[].config.field.label.value` | Yes | Display label for the KPI |
| `markdownConfig[].config.descriptionBefore` | No | Text shown above the number |

### Line Chart

Time-series or continuous data. `visType: "basic"`, cartesian config, `_dependentAxis: "y"`.

```json
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
      "series": [
        { "field": { "name": "order_items.total_revenue" }, "yAxis": "y" }
      ],
      "tooltip": [
        { "field": { "name": "order_items.created_at[month]" } },
        { "field": { "name": "order_items.total_revenue" } }
      ],
      "behaviors": { "stackMultiMark": false },
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
```

### Line chart with multiple series

Add more entries to `series` (in `visConfig.config`) and include them in `tooltip`:

```json
"series": [
  { "field": { "name": "order_items.total_revenue" }, "yAxis": "y" },
  { "field": { "name": "order_items.count" }, "yAxis": "y" }
],
"tooltip": [
  { "field": { "name": "order_items.created_at[month]" } },
  { "field": { "name": "order_items.total_revenue" } },
  { "field": { "name": "order_items.count" } }
]
```

### Column Chart (Vertical Bars)

Dimension on x-axis, measure on y-axis. `chartType: "column"`, `_dependentAxis: "y"`, `series[].yAxis: "y"`.

```json
{
  "name": "Revenue by Category",
  "topicName": "order_items",
  "prefersChart": true,
  "chartType": "column",
  "visConfig": {
    "visType": "basic",
    "fields": ["products.category", "order_items.total_revenue"],
    "config": {
      "x": { "field": { "name": "products.category" } },
      "mark": { "type": "bar" },
      "color": {},
      "series": [
        { "field": { "name": "order_items.total_revenue" }, "yAxis": "y" }
      ],
      "tooltip": [
        { "field": { "name": "products.category" } },
        { "field": { "name": "order_items.total_revenue" } }
      ],
      "behaviors": { "stackMultiMark": false },
      "configType": "cartesian",
      "_dependentAxis": "y"
    }
  },
  "fields": ["products.category", "order_items.total_revenue"],
  "query": {
    "table": "order_items",
    "fields": ["products.category", "order_items.total_revenue"],
    "sorts": [{ "column_name": "order_items.total_revenue", "sort_descending": true }],
    "limit": 10,
    "join_paths_from_topic_name": "order_items",
    "visConfig": { "chartType": "column" }
  }
}
```

### Bar Chart (Horizontal Bars)

Dimension on y-axis, measure on x-axis. `chartType: "bar"`, `_dependentAxis: "x"`, `series[].xAxis: "x"`. Good for ranked lists (Top N).

```json
{
  "name": "Top 10 Products by Revenue",
  "topicName": "order_items",
  "prefersChart": true,
  "chartType": "bar",
  "visConfig": {
    "visType": "basic",
    "fields": ["products.name", "order_items.total_revenue"],
    "config": {
      "y": { "field": { "name": "products.name" } },
      "mark": { "type": "bar" },
      "color": {},
      "series": [
        { "field": { "name": "order_items.total_revenue" }, "xAxis": "x" }
      ],
      "tooltip": [
        { "field": { "name": "products.name" } },
        { "field": { "name": "order_items.total_revenue" } }
      ],
      "behaviors": { "stackMultiMark": false },
      "configType": "cartesian",
      "_dependentAxis": "x"
    }
  },
  "fields": ["products.name", "order_items.total_revenue"],
  "query": {
    "table": "order_items",
    "fields": ["products.name", "order_items.total_revenue"],
    "sorts": [{ "column_name": "order_items.total_revenue", "sort_descending": true }],
    "limit": 10,
    "join_paths_from_topic_name": "order_items",
    "visConfig": { "chartType": "bar" }
  }
}
```

### Area Chart

Same as a line chart but with `mark.type: "area"` and `chartType: "area"`.

```json
{
  "name": "Revenue Over Time (Area)",
  "topicName": "order_items",
  "prefersChart": true,
  "chartType": "area",
  "visConfig": {
    "visType": "basic",
    "fields": ["order_items.created_at[month]", "order_items.total_revenue"],
    "config": {
      "x": { "field": { "name": "order_items.created_at[month]" } },
      "mark": { "type": "area" },
      "color": {},
      "series": [
        { "field": { "name": "order_items.total_revenue" }, "yAxis": "y" }
      ],
      "tooltip": [
        { "field": { "name": "order_items.created_at[month]" } },
        { "field": { "name": "order_items.total_revenue" } }
      ],
      "behaviors": { "stackMultiMark": false },
      "configType": "cartesian",
      "_dependentAxis": "y"
    }
  },
  "fields": ["order_items.created_at[month]", "order_items.total_revenue"],
  "query": {
    "table": "order_items",
    "fields": ["order_items.created_at[month]", "order_items.total_revenue"],
    "sorts": [{ "column_name": "order_items.created_at[month]", "sort_descending": false }],
    "limit": 100,
    "join_paths_from_topic_name": "order_items",
    "visConfig": { "chartType": "area" }
  }
}
```

### Stacked Column Chart (Vertical)

A category/time dimension on x, a measure on y, and a **pivoted** dimension that becomes the stack. `chartType: "columnStacked"`, `color._stack: "stack"` with the pivoted field, `_dependentAxis: "y"`. (For a horizontal stacked **bar**, use `chartType: "barStacked"` with `_dependentAxis: "x"` and `series[].xAxis: "x"`. For 100% stacking, use `columnStackedPercentage` / `barStackedPercentage` with `color._stack: "normalize"`.)

```json
{
  "name": "Distinct Orders by Status, Quarterly",
  "topicName": "order_items",
  "prefersChart": true,
  "chartType": "columnStacked",
  "visConfig": {
    "visType": "basic",
    "fields": ["order_items.created_at[quarter]", "order_items.status", "order_items.distinct_order_count"],
    "config": {
      "x": { "field": { "name": "order_items.created_at[quarter]" } },
      "mark": { "type": "bar" },
      "color": { "_stack": "stack", "field": { "name": "order_items.status" } },
      "series": [
        { "field": { "name": "order_items.distinct_order_count" }, "yAxis": "y" }
      ],
      "tooltip": [
        { "field": { "name": "order_items.created_at[quarter]" } },
        { "field": { "name": "order_items.status" } },
        { "field": { "name": "order_items.distinct_order_count" } }
      ],
      "behaviors": { "stackMultiMark": true },
      "configType": "cartesian",
      "_dependentAxis": "y"
    }
  },
  "fields": ["order_items.created_at[quarter]", "order_items.status", "order_items.distinct_order_count"],
  "query": {
    "table": "order_items",
    "fields": ["order_items.created_at[quarter]", "order_items.status", "order_items.distinct_order_count"],
    "sorts": [{ "column_name": "order_items.created_at[quarter]", "sort_descending": false }],
    "pivots": ["order_items.status"],
    "limit": 50,
    "join_paths_from_topic_name": "order_items",
    "visConfig": { "chartType": "columnStacked" }
  }
}
```

### Pie / Donut

`chartType: "pie"`, `visType: "basic"`, `config.configType: "polar"`. The category is `theta`; for a donut set `pastry: "donut"` (and optionally `innerRadiusPercent`).

```json
{
  "name": "Revenue by Category",
  "topicName": "order_items",
  "prefersChart": true,
  "chartType": "pie",
  "visConfig": {
    "visType": "basic",
    "fields": ["products.category", "order_items.total_revenue"],
    "config": {
      "configType": "polar",
      "theta": { "field": { "name": "order_items.total_revenue" } },
      "color": { "field": { "name": "products.category" } },
      "pastry": "pie",
      "tooltip": [
        { "field": { "name": "products.category" } },
        { "field": { "name": "order_items.total_revenue" } }
      ]
    }
  },
  "fields": ["products.category", "order_items.total_revenue"],
  "query": {
    "table": "order_items",
    "fields": ["products.category", "order_items.total_revenue"],
    "sorts": [{ "column_name": "order_items.total_revenue", "sort_descending": true }],
    "limit": 10,
    "join_paths_from_topic_name": "order_items",
    "visConfig": { "chartType": "pie" }
  }
}
```

## Cartesian Config Fields (`visConfig.config`)

All line, column/bar, area, scatter, and combo charts use this structure:

| Field | Required | Description |
|-------|----------|-------------|
| `configType` | Yes | Always `"cartesian"` for these families. |
| `_dependentAxis` | Yes | `"y"` for vertical charts (line, area, **column**, scatter); `"x"` for horizontal **bar** charts. Controls orientation. |
| `x` | Conditional | Independent (category) axis field. Used when `_dependentAxis` is `"y"`. |
| `y` | Conditional | Independent (category) axis field. Used when `_dependentAxis` is `"x"` (horizontal bars). |
| `mark.type` | Yes | `"line"`, `"bar"` (for both column and bar), `"area"`, or `"point"` (scatter). |
| `color` | Yes | Stacking / color encoding. `{}` = single series; `{ "_stack": "group" }` = grouped; `{ "_stack": "stack", "field": {...} }` = stacked; `{ "_stack": "normalize", "field": {...} }` = 100% stacked; `{ "field": {...} }` = color by dimension. The `_stack` value must match the `chartType` suffix. |
| `series` | Yes | Measure fields. Each has `"yAxis": "y"` (vertical) or `"xAxis": "x"` (horizontal). Per-series `mark` overrides enable combo charts. |
| `tooltip` | Yes | Fields shown on hover — include all dimensions and measures. |
| `behaviors.stackMultiMark` | No | `true` for stacked, `false` for grouped/overlay. |
| `size` | No | Field for bubble size (scatter `pointSize`/`pointSizeColor`). |

## Quick Reference: chartType → visType → config

| Chart | `chartType` | `visType` | `configType` | `mark.type` | `_dependentAxis` |
|-------|-------------|-----------|--------------|-------------|------------------|
| Table | `"table"` | `"omni-table"` | — | — | — |
| KPI | `"kpi"` | `"omni-kpi"` | — | — | — |
| Line | `"line"` / `"lineColor"` | `"basic"` | `"cartesian"` | `"line"` | `"y"` |
| Column (vert) | `"column"` / `"columnGrouped"` / `"columnStacked"` / `"columnStackedPercentage"` | `"basic"` | `"cartesian"` | `"bar"` | `"y"` |
| Bar (horiz) | `"bar"` / `"barGrouped"` / `"barStacked"` / `"barStackedPercentage"` | `"basic"` | `"cartesian"` | `"bar"` | `"x"` |
| Area | `"area"` / `"areaStacked"` / `"areaStackedPercentage"` | `"basic"` | `"cartesian"` | `"area"` | `"y"` |
| Scatter | `"point"` / `"pointColor"` / `"pointSize"` / `"pointSizeColor"` | `"basic"` | `"cartesian"` | `"point"` | `"y"` |
| Combo | `"barLine"` | `"basic"` | `"cartesian"` | per-series | `"y"` |
| Pie / Donut | `"pie"` | `"basic"` | `"polar"` | — | — |
| Heatmap | `"heatmap"` | `"basic"` | `"heatmap"` | — | — |
| Boxplot | `"boxplot"` | `"basic"` | `"boxplot"` | — | — |
| Funnel | `"funnel"` | `"funnel"` | — | — | — |
| Sankey | `"sankey"` | `"sankey"` | — | — | — |
| Point map | `"map"` | `"map"` | — | — | — |
| Region map | `"regionMap"` | `"map"` | — | — | — |

> For funnel, sankey, map, region map, heatmap, and boxplot, the inner `config` field names are best confirmed by building the chart once in the Omni UI and reading it back (`omni documents get`) — see [visConfig.md](visConfig.md) for the known shapes.
