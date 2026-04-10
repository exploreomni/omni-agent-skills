# visConfig Reference

Complete reference for the `visConfig` object — accepted `chartType` values, the `config` object structure for each chart family, and worked examples for every supported visualization type.

## Table of Contents

- [Where visConfig Lives](#where-visconfig-lives) — placement inside the query object
- [chartType Values](#charttype-values) — all 35+ accepted values and mapping to config properties
- [Config Object: Cartesian Charts](#config-object-cartesian-charts) — line, bar, area, scatter, combo, heatmap, boxplot
- [Config Object: KPI](#config-object-kpi) — single value and multi-value tiles
- [Config Object: Pie / Donut](#config-object-pie--donut)
- [Config Object: Funnel](#config-object-funnel)
- [Config Object: Sankey](#config-object-sankey)
- [Config Object: Heatmap](#config-object-heatmap)
- [Config Object: Map](#config-object-map) — point maps with lat/lng
- [Config Object: Region Map](#config-object-region-map) — choropleth maps
- [Complete Examples](#complete-examples) — 17 worked examples covering every chart family
- [Discovering Config for Advanced Chart Types](#discovering-config-for-advanced-chart-types) — reading configs from the UI
- [resultConfig](#resultconfig) — column order, hidden columns, widths
- [aiConfig](#aiconfig) — AI-generated descriptions and subtitles
- [Common Mistakes](#common-mistakes) — symptoms and fixes
- [Safe Defaults](#safe-defaults) — fallback patterns when unsure

> **Important**: The `visConfig` schema is not fully documented in Omni's public API docs. The examples below are based on reading back visualizations from dashboards created in the Omni UI via `GET /api/v1/documents/{documentId}`. **Always verify config structure** by building a reference chart in the UI and reading it back before relying on these examples for advanced or uncommon chart types.

## Where visConfig Lives

`visConfig` belongs **inside the `query` object** — not at the `queryPresentation` level. When placed as a sibling of `query`, it is silently dropped.

```json
{
  "queryPresentations": [{
    "name": "My Tile",
    "prefersChart": true,
    "visType": "basic",
    "config": { ... },
    "query": {
      "table": "order_items",
      "fields": [...],
      "visConfig": {             
        "chartType": "lineColor"
      }
    }
  }]
}
```

`visConfig` alone does **not** control chart rendering. It stores the chart type hint on the query. The actual rendering is driven by three fields at the `queryPresentation` level:

| Field | Purpose |
|-------|---------|
| `prefersChart` | Must be `true` to render any chart (otherwise always shows table) |
| `visType` | Renderer: `"basic"` for standard charts, `"omni-kpi"` for KPI tiles, `"markdown"` for markdown tiles |
| `config` | Chart-specific rendering configuration (structure varies by chart type) |

## chartType Values

The `chartType` field on `visConfig` (inside `query`) and optionally on `queryPresentation` accepts these values:

### Standard Chart Types

| chartType | Category | Description |
|-----------|----------|-------------|
| `"table"` | Table | Data table (default) |
| `"kpi"` | KPI | Single value / big number |
| `"line"` | Cartesian | Line chart (auto color) |
| `"lineColor"` | Cartesian | Line chart with color encoding |
| `"area"` | Cartesian | Area chart (auto color) |
| `"areaStacked"` | Cartesian | Stacked area chart |
| `"areaStackedPercentage"` | Cartesian | 100% stacked area chart |
| `"bar"` | Cartesian | Bar chart (auto orientation) |
| `"barColor"` | Cartesian | Bar chart with color encoding |
| `"barGrouped"` | Cartesian | Grouped (side-by-side) bars |
| `"barStacked"` | Cartesian | Stacked bar chart |
| `"barStackedPercentage"` | Cartesian | 100% stacked bar chart |
| `"barLine"` | Cartesian | Combo bar + line chart |
| `"column"` | Cartesian | Vertical bar (alias) |
| `"columnGrouped"` | Cartesian | Grouped vertical bars |
| `"columnStacked"` | Cartesian | Stacked vertical bars |
| `"columnStackedPercentage"` | Cartesian | 100% stacked vertical bars |
| `"point"` | Cartesian | Scatter plot (auto) |
| `"pointColor"` | Cartesian | Scatter with color encoding |
| `"pointSize"` | Cartesian | Scatter with size encoding |
| `"pointSizeColor"` | Cartesian | Scatter with size + color encoding |
| `"pie"` | Radial | Pie / donut chart |
| `"funnel"` | Specialty | Funnel chart |
| `"sankey"` | Specialty | Sankey flow diagram |
| `"heatmap"` | Grid | Heatmap |
| `"boxplot"` | Statistical | Box-and-whisker plot |
| `"map"` | Geo | Point map (lat/lng) |
| `"regionMap"` | Geo | Choropleth / filled region map |
| `"summaryValue"` | KPI | Summary value display |
| `"singleRecord"` | Detail | Single record viewer |
| `"markdown"` | Text | Markdown content tile |
| `"omni-ai-summary-markdown"` | Text | AI-generated summary tile |
| `"auto"` | Auto | Let Omni choose the best chart type |
| `null` | Default | No chart type specified (renders as table) |

### Mapping: visConfig.chartType to config Properties

| visConfig.chartType | visType | mark.type | configType | _dependentAxis |
|---------------------|---------|-----------|------------|----------------|
| `"table"` | `"basic"` | n/a | n/a | n/a |
| `"kpi"` | `"omni-kpi"` | n/a | n/a | n/a |
| `"lineColor"` | `"basic"` | `"line"` | `"cartesian"` | `"y"` |
| `"barColor"` (horizontal) | `"basic"` | `"bar"` | `"cartesian"` | `"x"` |
| `"barColor"` (vertical) | `"basic"` | `"bar"` | `"cartesian"` | `"y"` |
| `"barGrouped"` | `"basic"` | `"bar"` | `"cartesian"` | `"y"` or `"x"` |
| `"barStacked"` | `"basic"` | `"bar"` | `"cartesian"` | `"y"` |
| `"barStackedPercentage"` | `"basic"` | `"bar"` | `"cartesian"` | `"y"` |
| `"barLine"` | `"basic"` | mixed | `"cartesian"` | `"y"` |
| `"areaColor"` | `"basic"` | `"area"` | `"cartesian"` | `"y"` |
| `"areaStacked"` | `"basic"` | `"area"` | `"cartesian"` | `"y"` |
| `"areaStackedPercentage"` | `"basic"` | `"area"` | `"cartesian"` | `"y"` |
| `"point"` / `"pointColor"` | `"basic"` | `"point"` | `"cartesian"` | `"y"` |
| `"pointSize"` / `"pointSizeColor"` | `"basic"` | `"point"` | `"cartesian"` | `"y"` |
| `"pie"` | `"basic"` | n/a | `"pie"` | n/a |
| `"funnel"` | `"basic"` | n/a | `"funnel"` | n/a |
| `"sankey"` | `"basic"` | n/a | `"sankey"` | n/a |
| `"heatmap"` | `"basic"` | `"rect"` | `"cartesian"` | n/a |
| `"boxplot"` | `"basic"` | `"boxplot"` | `"cartesian"` | `"y"` |
| `"map"` | `"basic"` | n/a | `"map"` | n/a |
| `"regionMap"` | `"basic"` | n/a | `"regionMap"` | n/a |

## Config Object: Cartesian Charts

All line, bar, area, scatter, and combo charts use the cartesian config structure. This is the most common config type.

### Cartesian Config Fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `configType` | Yes | string | Always `"cartesian"` |
| `version` | Yes | number | Always `0` |
| `x` | Conditional | object | X-axis field. Required for vertical charts. |
| `y` | Conditional | object | Y-axis field. Required for horizontal bar charts. |
| `mark` | Yes | object | Mark type definition |
| `mark.type` | Yes | string | `"line"`, `"bar"`, `"area"`, `"point"`, `"rect"`, `"boxplot"` |
| `color` | Yes | object | Color and stacking configuration |
| `series` | Yes | array | Measure field definitions with axis binding |
| `tooltip` | Yes | array | Fields shown on hover |
| `behaviors` | Yes | object | Interaction behaviors |
| `behaviors.stackMultiMark` | Yes | boolean | `true` for stacked charts, `false` for grouped |
| `_dependentAxis` | Yes | string | `"y"` for vertical charts, `"x"` for horizontal bars |

### Axis Fields (`x` and `y`)

```json
"x": {
  "field": { "name": "order_items.created_at[month]" }
}
```

Optional axis properties:

| Property | Type | Description |
|----------|------|-------------|
| `field.name` | string | Fully qualified field name |
| `label` | string | Custom axis label (overrides field name) |
| `showLabel` | boolean | Show/hide axis label |
| `showGridLines` | boolean | Show/hide grid lines |
| `tickFormat` | string | Number/date format string |
| `scale` | object | Scale configuration (e.g., `{ "type": "log" }` for log scale) |
| `domain` | array | Fixed axis domain `[min, max]` |

### Color Object

| Pattern | Usage | Example |
|---------|-------|---------|
| `{}` | Single series, auto color | `"color": {}` |
| `{ "_stack": "group" }` | Grouped (side-by-side) | Bar charts with multiple categories |
| `{ "_stack": "stack", "field": { "name": "..." } }` | Stacked | Stacked bar/area with pivot field |
| `{ "_stack": "normalize", "field": { "name": "..." } }` | 100% stacked | Percentage stacked charts |
| `{ "field": { "name": "..." } }` | Color by field | Scatter/line colored by dimension |

### Series Array

Each entry maps a measure to an axis:

```json
"series": [
  {
    "field": { "name": "order_items.total_revenue" },
    "yAxis": "y"
  }
]
```

Series entry properties:

| Property | Type | Description |
|----------|------|-------------|
| `field.name` | string | Fully qualified measure field name |
| `yAxis` | string | `"y"` for vertical charts (measure on y-axis) |
| `xAxis` | string | `"x"` for horizontal bar charts (measure on x-axis) |
| `label` | string | Custom series label |
| `color` | string | Hex color override (e.g., `"#1f77b4"`) |
| `mark` | object | Per-series mark override (e.g., `{ "type": "line" }` for combo charts) |
| `yAxis2` | string | `"y2"` to place series on secondary y-axis |

### Tooltip Array

Include all dimension and measure fields that should appear on hover:

```json
"tooltip": [
  { "field": { "name": "order_items.created_at[month]" } },
  { "field": { "name": "order_items.total_revenue" } }
]
```

## Config Object: KPI

KPI tiles use `visType: "omni-kpi"` and have a unique config structure.

### KPI Config Fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `alignment` | No | string | Horizontal: `"left"`, `"center"`, `"right"` |
| `verticalAlignment` | No | string | Vertical: `"top"`, `"center"`, `"bottom"` |
| `markdownConfig` | Yes | array | Array of KPI value entries |

### markdownConfig Entry

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `id` | Yes | string | Unique ID (e.g., `"kpi-1"`) |
| `type` | Yes | string | `"number"` for numeric values |
| `config.field.row` | Yes | string | Always `"_first"` |
| `config.field.field.name` | Yes | string | Fully qualified field name |
| `config.field.field.pivotMap` | Yes | object | Empty `{}` unless using pivots |
| `config.field.label.value` | Yes | string | Display label |
| `config.descriptionBefore` | No | string | Text above the number |
| `config.descriptionAfter` | No | string | Text below the number |
| `config.comparison` | No | object | Comparison/sparkline configuration |

## Config Object: Pie / Donut

Pie charts use `configType: "pie"`.

### Pie Config Fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `configType` | Yes | string | `"pie"` |
| `version` | Yes | number | `0` |
| `dimension` | Yes | object | Category field |
| `measure` | Yes | object | Value field |
| `tooltip` | Yes | array | Fields for hover tooltip |
| `innerRadius` | No | number | `0` for pie, `0.3`–`0.7` for donut |
| `showLabels` | No | boolean | Show slice labels |
| `showLegend` | No | boolean | Show legend |

## Config Object: Funnel

Funnel charts use `configType: "funnel"`.

### Funnel Config Fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `configType` | Yes | string | `"funnel"` |
| `version` | Yes | number | `0` |
| `dimension` | Yes | object | Stage field (categorical) |
| `measure` | Yes | object | Value field (numeric) |
| `tooltip` | Yes | array | Fields for hover tooltip |

## Config Object: Sankey

Sankey diagrams use `configType: "sankey"`.

### Sankey Config Fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `configType` | Yes | string | `"sankey"` |
| `version` | Yes | number | `0` |
| `source` | Yes | object | Source dimension field |
| `target` | Yes | object | Target dimension field |
| `value` | Yes | object | Flow value measure field |

## Config Object: Heatmap

Heatmaps use cartesian config with `mark.type: "rect"`.

### Heatmap Config Fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `configType` | Yes | string | `"cartesian"` |
| `version` | Yes | number | `0` |
| `x` | Yes | object | X-axis dimension field |
| `y` | Yes | object | Y-axis dimension field |
| `mark` | Yes | object | `{ "type": "rect" }` |
| `color` | Yes | object | Color scale field (the measure) |
| `tooltip` | Yes | array | Fields for hover |

## Config Object: Map

Point maps use `configType: "map"`.

### Map Config Fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `configType` | Yes | string | `"map"` |
| `version` | Yes | number | `0` |
| `latitude` | Yes | object | Latitude field |
| `longitude` | Yes | object | Longitude field |
| `size` | No | object | Measure field for point sizing |
| `color` | No | object | Measure or dimension field for coloring |
| `tooltip` | Yes | array | Fields for hover |

## Config Object: Region Map

Region/choropleth maps use `configType: "regionMap"`.

### Region Map Config Fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `configType` | Yes | string | `"regionMap"` |
| `version` | Yes | number | `0` |
| `region` | Yes | object | Geographic dimension field (state, country, etc.) |
| `color` | Yes | object | Measure field for color intensity |
| `tooltip` | Yes | array | Fields for hover |

---

## Complete Examples

### Line Chart

```json
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
    "filters": { "order_items.created_at": "last 6 months" },
    "limit": 100,
    "join_paths_from_topic_name": "order_items",
    "visConfig": { "chartType": "lineColor" }
  },
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
    "version": 0,
    "behaviors": { "stackMultiMark": false },
    "configType": "cartesian",
    "_dependentAxis": "y"
  }
}
```

### Multi-Series Line Chart

```json
{
  "name": "Revenue vs Orders Over Time",
  "topicName": "order_items",
  "prefersChart": true,
  "visType": "basic",
  "fields": ["order_items.created_at[month]", "order_items.total_revenue", "order_items.count"],
  "query": {
    "table": "order_items",
    "fields": ["order_items.created_at[month]", "order_items.total_revenue", "order_items.count"],
    "sorts": [{ "column_name": "order_items.created_at[month]", "sort_descending": false }],
    "limit": 100,
    "join_paths_from_topic_name": "order_items",
    "visConfig": { "chartType": "lineColor" }
  },
  "config": {
    "x": { "field": { "name": "order_items.created_at[month]" } },
    "mark": { "type": "line" },
    "color": {},
    "series": [
      { "field": { "name": "order_items.total_revenue" }, "yAxis": "y" },
      { "field": { "name": "order_items.count" }, "yAxis": "y" }
    ],
    "tooltip": [
      { "field": { "name": "order_items.created_at[month]" } },
      { "field": { "name": "order_items.total_revenue" } },
      { "field": { "name": "order_items.count" } }
    ],
    "version": 0,
    "behaviors": { "stackMultiMark": false },
    "configType": "cartesian",
    "_dependentAxis": "y"
  }
}
```

### Bar Chart (Vertical)

```json
{
  "name": "Revenue by Category",
  "topicName": "order_items",
  "prefersChart": true,
  "visType": "basic",
  "chartType": "barGrouped",
  "fields": ["products.category", "order_items.total_revenue"],
  "query": {
    "table": "order_items",
    "fields": ["products.category", "order_items.total_revenue"],
    "sorts": [{ "column_name": "order_items.total_revenue", "sort_descending": true }],
    "limit": 10,
    "join_paths_from_topic_name": "order_items",
    "visConfig": { "chartType": "barColor" }
  },
  "config": {
    "x": { "field": { "name": "products.category" } },
    "mark": { "type": "bar" },
    "color": { "_stack": "group" },
    "series": [
      { "field": { "name": "order_items.total_revenue" }, "yAxis": "y" }
    ],
    "tooltip": [
      { "field": { "name": "products.category" } },
      { "field": { "name": "order_items.total_revenue" } }
    ],
    "version": 0,
    "behaviors": { "stackMultiMark": false },
    "configType": "cartesian",
    "_dependentAxis": "y"
  }
}
```

### Bar Chart (Horizontal)

Dimension on y-axis, measure on x-axis. Note `_dependentAxis: "x"` and `series[].xAxis`.

```json
{
  "name": "Top 10 Products by Revenue",
  "topicName": "order_items",
  "prefersChart": true,
  "visType": "basic",
  "chartType": "barGrouped",
  "fields": ["products.name", "order_items.total_revenue"],
  "query": {
    "table": "order_items",
    "fields": ["products.name", "order_items.total_revenue"],
    "sorts": [{ "column_name": "order_items.total_revenue", "sort_descending": true }],
    "limit": 10,
    "join_paths_from_topic_name": "order_items",
    "visConfig": { "chartType": "barColor" }
  },
  "config": {
    "y": { "field": { "name": "products.name" } },
    "mark": { "type": "bar" },
    "color": { "_stack": "group" },
    "series": [
      { "field": { "name": "order_items.total_revenue" }, "xAxis": "x" }
    ],
    "tooltip": [
      { "field": { "name": "products.name" } },
      { "field": { "name": "order_items.total_revenue" } }
    ],
    "version": 0,
    "behaviors": { "stackMultiMark": false },
    "configType": "cartesian",
    "_dependentAxis": "x"
  }
}
```

### Stacked Bar Chart

Uses `_stack: "stack"` with a pivot field for color breakdown.

```json
{
  "name": "Monthly Revenue by Status",
  "topicName": "order_items",
  "prefersChart": true,
  "visType": "basic",
  "fields": ["order_items.created_at[month]", "order_items.status", "order_items.total_revenue"],
  "query": {
    "table": "order_items",
    "fields": ["order_items.created_at[month]", "order_items.status", "order_items.total_revenue"],
    "sorts": [{ "column_name": "order_items.created_at[month]", "sort_descending": false }],
    "pivots": ["order_items.status"],
    "limit": 100,
    "join_paths_from_topic_name": "order_items",
    "visConfig": { "chartType": "stackedBarColor" }
  },
  "config": {
    "x": { "field": { "name": "order_items.created_at[month]" } },
    "mark": { "type": "bar" },
    "color": { "_stack": "stack", "field": { "name": "order_items.status" } },
    "series": [
      { "field": { "name": "order_items.total_revenue" }, "yAxis": "y" }
    ],
    "tooltip": [
      { "field": { "name": "order_items.created_at[month]" } },
      { "field": { "name": "order_items.status" } },
      { "field": { "name": "order_items.total_revenue" } }
    ],
    "version": 0,
    "behaviors": { "stackMultiMark": false },
    "configType": "cartesian",
    "_dependentAxis": "y"
  }
}
```

### 100% Stacked Bar Chart

Uses `_stack: "normalize"` instead of `"stack"`.

```json
{
  "name": "Revenue Share by Status",
  "topicName": "order_items",
  "prefersChart": true,
  "visType": "basic",
  "fields": ["order_items.created_at[month]", "order_items.status", "order_items.total_revenue"],
  "query": {
    "table": "order_items",
    "fields": ["order_items.created_at[month]", "order_items.status", "order_items.total_revenue"],
    "sorts": [{ "column_name": "order_items.created_at[month]", "sort_descending": false }],
    "pivots": ["order_items.status"],
    "limit": 100,
    "join_paths_from_topic_name": "order_items",
    "visConfig": { "chartType": "barStackedPercentage" }
  },
  "config": {
    "x": { "field": { "name": "order_items.created_at[month]" } },
    "mark": { "type": "bar" },
    "color": { "_stack": "normalize", "field": { "name": "order_items.status" } },
    "series": [
      { "field": { "name": "order_items.total_revenue" }, "yAxis": "y" }
    ],
    "tooltip": [
      { "field": { "name": "order_items.created_at[month]" } },
      { "field": { "name": "order_items.status" } },
      { "field": { "name": "order_items.total_revenue" } }
    ],
    "version": 0,
    "behaviors": { "stackMultiMark": false },
    "configType": "cartesian",
    "_dependentAxis": "y"
  }
}
```

### Combo Chart (Bar + Line)

Uses different `mark` types per series. One series renders as bar, another as line.

```json
{
  "name": "Revenue (Bar) vs Order Count (Line)",
  "topicName": "order_items",
  "prefersChart": true,
  "visType": "basic",
  "chartType": "barLine",
  "fields": ["order_items.created_at[month]", "order_items.total_revenue", "order_items.count"],
  "query": {
    "table": "order_items",
    "fields": ["order_items.created_at[month]", "order_items.total_revenue", "order_items.count"],
    "sorts": [{ "column_name": "order_items.created_at[month]", "sort_descending": false }],
    "limit": 100,
    "join_paths_from_topic_name": "order_items",
    "visConfig": { "chartType": "barLine" }
  },
  "config": {
    "x": { "field": { "name": "order_items.created_at[month]" } },
    "mark": { "type": "bar" },
    "color": {},
    "series": [
      { "field": { "name": "order_items.total_revenue" }, "yAxis": "y", "mark": { "type": "bar" } },
      { "field": { "name": "order_items.count" }, "yAxis": "y2", "mark": { "type": "line" } }
    ],
    "tooltip": [
      { "field": { "name": "order_items.created_at[month]" } },
      { "field": { "name": "order_items.total_revenue" } },
      { "field": { "name": "order_items.count" } }
    ],
    "version": 0,
    "behaviors": { "stackMultiMark": false },
    "configType": "cartesian",
    "_dependentAxis": "y"
  }
}
```

### Area Chart

```json
{
  "name": "Revenue Over Time (Area)",
  "topicName": "order_items",
  "prefersChart": true,
  "visType": "basic",
  "fields": ["order_items.created_at[month]", "order_items.total_revenue"],
  "query": {
    "table": "order_items",
    "fields": ["order_items.created_at[month]", "order_items.total_revenue"],
    "sorts": [{ "column_name": "order_items.created_at[month]", "sort_descending": false }],
    "limit": 100,
    "join_paths_from_topic_name": "order_items",
    "visConfig": { "chartType": "areaColor" }
  },
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
    "version": 0,
    "behaviors": { "stackMultiMark": false },
    "configType": "cartesian",
    "_dependentAxis": "y"
  }
}
```

### Stacked Area Chart

```json
{
  "name": "Revenue by Status (Stacked Area)",
  "topicName": "order_items",
  "prefersChart": true,
  "visType": "basic",
  "fields": ["order_items.created_at[month]", "order_items.status", "order_items.total_revenue"],
  "query": {
    "table": "order_items",
    "fields": ["order_items.created_at[month]", "order_items.status", "order_items.total_revenue"],
    "sorts": [{ "column_name": "order_items.created_at[month]", "sort_descending": false }],
    "pivots": ["order_items.status"],
    "limit": 100,
    "join_paths_from_topic_name": "order_items",
    "visConfig": { "chartType": "areaStacked" }
  },
  "config": {
    "x": { "field": { "name": "order_items.created_at[month]" } },
    "mark": { "type": "area" },
    "color": { "_stack": "stack", "field": { "name": "order_items.status" } },
    "series": [
      { "field": { "name": "order_items.total_revenue" }, "yAxis": "y" }
    ],
    "tooltip": [
      { "field": { "name": "order_items.created_at[month]" } },
      { "field": { "name": "order_items.status" } },
      { "field": { "name": "order_items.total_revenue" } }
    ],
    "version": 0,
    "behaviors": { "stackMultiMark": false },
    "configType": "cartesian",
    "_dependentAxis": "y"
  }
}
```

### Scatter Plot

```json
{
  "name": "Price vs Quantity",
  "topicName": "order_items",
  "prefersChart": true,
  "visType": "basic",
  "fields": ["order_items.average_sale_price", "order_items.count", "products.category"],
  "query": {
    "table": "order_items",
    "fields": ["order_items.average_sale_price", "order_items.count", "products.category"],
    "limit": 500,
    "join_paths_from_topic_name": "order_items",
    "visConfig": { "chartType": "pointColor" }
  },
  "config": {
    "x": { "field": { "name": "order_items.average_sale_price" } },
    "mark": { "type": "point" },
    "color": { "field": { "name": "products.category" } },
    "series": [
      { "field": { "name": "order_items.count" }, "yAxis": "y" }
    ],
    "tooltip": [
      { "field": { "name": "order_items.average_sale_price" } },
      { "field": { "name": "order_items.count" } },
      { "field": { "name": "products.category" } }
    ],
    "version": 0,
    "behaviors": { "stackMultiMark": false },
    "configType": "cartesian",
    "_dependentAxis": "y"
  }
}
```

### Scatter Plot with Size Encoding

```json
{
  "name": "Revenue vs Count by Category (Bubble)",
  "topicName": "order_items",
  "prefersChart": true,
  "visType": "basic",
  "fields": ["order_items.average_sale_price", "order_items.count", "order_items.total_revenue", "products.category"],
  "query": {
    "table": "order_items",
    "fields": ["order_items.average_sale_price", "order_items.count", "order_items.total_revenue", "products.category"],
    "limit": 500,
    "join_paths_from_topic_name": "order_items",
    "visConfig": { "chartType": "pointSizeColor" }
  },
  "config": {
    "x": { "field": { "name": "order_items.average_sale_price" } },
    "mark": { "type": "point" },
    "color": { "field": { "name": "products.category" } },
    "size": { "field": { "name": "order_items.total_revenue" } },
    "series": [
      { "field": { "name": "order_items.count" }, "yAxis": "y" }
    ],
    "tooltip": [
      { "field": { "name": "order_items.average_sale_price" } },
      { "field": { "name": "order_items.count" } },
      { "field": { "name": "order_items.total_revenue" } },
      { "field": { "name": "products.category" } }
    ],
    "version": 0,
    "behaviors": { "stackMultiMark": false },
    "configType": "cartesian",
    "_dependentAxis": "y"
  }
}
```

### KPI (Single Value)

```json
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
}
```

### KPI (Multiple Values)

```json
{
  "name": "Key Metrics",
  "topicName": "order_items",
  "prefersChart": true,
  "visType": "omni-kpi",
  "fields": ["order_items.total_revenue", "order_items.count", "order_items.average_sale_price"],
  "query": {
    "table": "order_items",
    "fields": ["order_items.total_revenue", "order_items.count", "order_items.average_sale_price"],
    "join_paths_from_topic_name": "order_items",
    "visConfig": { "chartType": "kpi" }
  },
  "config": {
    "alignment": "center",
    "verticalAlignment": "center",
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
      },
      {
        "id": "kpi-aov",
        "type": "number",
        "config": {
          "field": {
            "row": "_first",
            "field": { "name": "order_items.average_sale_price", "pivotMap": {} },
            "label": { "value": "Avg Sale Price" }
          },
          "descriptionBefore": ""
        }
      }
    ]
  }
}
```

### Pie Chart

```json
{
  "name": "Revenue by Category",
  "topicName": "order_items",
  "prefersChart": true,
  "visType": "basic",
  "fields": ["products.category", "order_items.total_revenue"],
  "query": {
    "table": "order_items",
    "fields": ["products.category", "order_items.total_revenue"],
    "sorts": [{ "column_name": "order_items.total_revenue", "sort_descending": true }],
    "limit": 10,
    "join_paths_from_topic_name": "order_items",
    "visConfig": { "chartType": "pie" }
  },
  "config": {
    "configType": "pie",
    "version": 0,
    "dimension": { "field": { "name": "products.category" } },
    "measure": { "field": { "name": "order_items.total_revenue" } },
    "tooltip": [
      { "field": { "name": "products.category" } },
      { "field": { "name": "order_items.total_revenue" } }
    ]
  }
}
```

### Donut Chart

Same as pie but with `innerRadius` set.

```json
{
  "name": "Revenue by Category (Donut)",
  "topicName": "order_items",
  "prefersChart": true,
  "visType": "basic",
  "fields": ["products.category", "order_items.total_revenue"],
  "query": {
    "table": "order_items",
    "fields": ["products.category", "order_items.total_revenue"],
    "sorts": [{ "column_name": "order_items.total_revenue", "sort_descending": true }],
    "limit": 10,
    "join_paths_from_topic_name": "order_items",
    "visConfig": { "chartType": "pie" }
  },
  "config": {
    "configType": "pie",
    "version": 0,
    "dimension": { "field": { "name": "products.category" } },
    "measure": { "field": { "name": "order_items.total_revenue" } },
    "innerRadius": 0.5,
    "tooltip": [
      { "field": { "name": "products.category" } },
      { "field": { "name": "order_items.total_revenue" } }
    ]
  }
}
```

### Funnel Chart

```json
{
  "name": "Conversion Funnel",
  "topicName": "funnel_stages",
  "prefersChart": true,
  "visType": "basic",
  "fields": ["funnel_stages.stage_name", "funnel_stages.user_count"],
  "query": {
    "table": "funnel_stages",
    "fields": ["funnel_stages.stage_name", "funnel_stages.user_count"],
    "sorts": [{ "column_name": "funnel_stages.stage_order", "sort_descending": false }],
    "limit": 20,
    "join_paths_from_topic_name": "funnel_stages",
    "visConfig": { "chartType": "funnel" }
  },
  "config": {
    "configType": "funnel",
    "version": 0,
    "dimension": { "field": { "name": "funnel_stages.stage_name" } },
    "measure": { "field": { "name": "funnel_stages.user_count" } },
    "tooltip": [
      { "field": { "name": "funnel_stages.stage_name" } },
      { "field": { "name": "funnel_stages.user_count" } }
    ]
  }
}
```

### Heatmap

```json
{
  "name": "Orders by Day of Week and Hour",
  "topicName": "order_items",
  "prefersChart": true,
  "visType": "basic",
  "fields": ["order_items.created_day_of_week", "order_items.created_hour", "order_items.count"],
  "query": {
    "table": "order_items",
    "fields": ["order_items.created_day_of_week", "order_items.created_hour", "order_items.count"],
    "limit": 500,
    "join_paths_from_topic_name": "order_items",
    "visConfig": { "chartType": "heatmap" }
  },
  "config": {
    "x": { "field": { "name": "order_items.created_hour" } },
    "y": { "field": { "name": "order_items.created_day_of_week" } },
    "mark": { "type": "rect" },
    "color": { "field": { "name": "order_items.count" } },
    "tooltip": [
      { "field": { "name": "order_items.created_day_of_week" } },
      { "field": { "name": "order_items.created_hour" } },
      { "field": { "name": "order_items.count" } }
    ],
    "version": 0,
    "configType": "cartesian"
  }
}
```

### Table (No Chart)

```json
{
  "name": "Order Details",
  "topicName": "order_items",
  "prefersChart": false,
  "visType": "basic",
  "fields": ["order_items.status", "order_items.count", "order_items.total_revenue"],
  "query": {
    "table": "order_items",
    "fields": ["order_items.status", "order_items.count", "order_items.total_revenue"],
    "sorts": [{ "column_name": "order_items.total_revenue", "sort_descending": true }],
    "limit": 100,
    "join_paths_from_topic_name": "order_items",
    "visConfig": { "chartType": "table" }
  },
  "config": {}
}
```

---

## Discovering Config for Advanced Chart Types

For chart types not fully documented here (sankey, boxplot, map, regionMap, singleRecord), the most reliable approach is to build the chart in the Omni UI and read it back:

```bash
# Step 1: Build the visualization in the Omni UI
# Step 2: Read the document to capture its config
omni documents get <documentId>
```

The response includes the complete `queryPresentations` array with `visConfig`, `config`, and all rendering parameters — use this as the source of truth.

> **Tip**: Build one reference dashboard in the UI with every chart type you need. Read it back once, and use those configs as templates for all future programmatic dashboard creation.

## resultConfig

The `resultConfig` object is an optional field on `queryPresentation` that controls result display settings independent of visualization. It is not well-documented in the public API, but commonly includes:

| Field | Type | Description |
|-------|------|-------------|
| `columnOrder` | array | Ordered list of field names controlling column display order in tables |
| `hiddenColumns` | array | Field names to hide from the table view |
| `columnWidths` | object | Map of field name to pixel width |

## aiConfig

The `aiConfig` object enables AI-generated descriptions and subtitles on tiles:

```json
"aiConfig": {
  "description": {
    "enabled": true,
    "aiContext": "Summarize this data focusing on trends"
  },
  "subTitle": {
    "enabled": true,
    "aiContext": "One-line summary of the key takeaway"
  }
}
```

## Common Mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| `visConfig` placed outside `query` | Chart renders as table | Move `visConfig` inside the `query` object |
| `prefersChart` is `false` or missing | Always shows table | Set `prefersChart: true` |
| `visType` wrong for chart type | "No chart available" | Use `"omni-kpi"` for KPI, `"basic"` for everything else |
| `_dependentAxis` mismatched | Chart axes inverted or broken | `"y"` for vertical, `"x"` for horizontal bars |
| `series[].yAxis` vs `xAxis` wrong | Measures don't render | Use `yAxis: "y"` for vertical, `xAxis: "x"` for horizontal |
| Missing `fields` at presentation level | Tile may not render | Duplicate `query.fields` at the `queryPresentation` level |
| Missing measure in query | Empty tile with no error | Every query must include at least one measure |
| `mark.type` doesn't match chartType | Unexpected rendering | See mapping table above |
| `behaviors.stackMultiMark` wrong | Stacking behavior incorrect | `true` for stacked, `false` for grouped |
| `config: {}` with `prefersChart: true` | Omni auto-generates config | Safe default — Omni picks the best chart |

## Safe Defaults

When unsure about config structure, use these safe patterns:

**Safest**: Let Omni auto-generate the config:
```json
{
  "prefersChart": true,
  "visType": "basic",
  "config": {},
  "query": {
    "visConfig": { "chartType": "lineColor" }
  }
}
```

**Table fallback**: Always works:
```json
{
  "prefersChart": false,
  "visType": "basic",
  "config": {},
  "query": {
    "visConfig": { "chartType": "table" }
  }
}
```

> **Recommendation**: For new or unfamiliar chart types, start with `"config": {}` and let Omni auto-generate the rendering config. Then read the document back with `omni documents get` to capture the full config for future use as a template.
