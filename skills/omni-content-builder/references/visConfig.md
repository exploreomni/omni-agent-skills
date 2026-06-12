# visConfig Reference

Complete reference for a tile's visualization config — the v2 `visConfig` envelope, accepted `chartType` values, the inner `config` object structure for each chart family, and worked examples.

## Table of Contents

- [Where the visualization config lives](#where-the-visualization-config-lives) — the #1 gotcha
- [chartType Values](#charttype-values) — the authoritative enum
- [chartType → visType → configType mapping](#charttype--vistype--configtype-mapping)
- [Config Object: Cartesian Charts](#config-object-cartesian-charts) — line, column, bar, area, scatter, combo
- [Config Object: KPI](#config-object-kpi)
- [Config Object: Pie / Donut](#config-object-pie--donut)
- [Config Object: Heatmap](#config-object-heatmap)
- [Config Object: Boxplot](#config-object-boxplot)
- [Config Object: Funnel](#config-object-funnel)
- [Config Object: Sankey](#config-object-sankey)
- [Config Object: Map / Region Map](#config-object-map--region-map)
- [Complete Examples](#complete-examples)
- [Discovering Config for Advanced Chart Types](#discovering-config-for-advanced-chart-types)
- [resultConfig](#resultconfig)
- [aiConfig](#aiconfig)
- [Common Mistakes](#common-mistakes)
- [Safe Defaults](#safe-defaults)

> **Important**: The visualization config schema is not fully documented in Omni's public API docs. The structures below are derived from Omni's visualization type definitions and confirmed by reading dashboards back via `omni documents v2-get`. For uncommon chart types, **always verify** by building a reference chart in the UI and reading it back before relying on these examples.

## Where the visualization config lives

A chart tile is driven by **one queryPresentation-level field**: the `visConfig` envelope. `chartType` and `fields` sit at its outer level; the renderer (`visType`) and the rendering spec are nested inside, with the spec **under `config`**:

```json
{
  "name": "My Tile",
  "type": "query",
  "prefersChart": true,
  "automaticVis": false,
  "visConfig": {
    "chartType": "columnStacked",
    "fields": ["..."],
    "version": 0,
    "visConfig": {
      "visType": "basic",
      "config": { "configType": "cartesian", "_dependentAxis": "y", "...": "spec" }
    }
  },
  "query": { "...": "full required-field set — see queryPresentations.md" }
}
```

Set `prefersChart: true` to default the tile to chart (vs. table) view, and `automaticVis: false` so the renderer uses your explicit spec instead of deriving one. (On create, the server seed tile can flip tile `"1"`'s `automaticVis` back to `true` — read back and re-patch if it matters.)

> **Read-back is flat — writes must be nested.** `v2-get` returns the inner vis config **flat**: the spec keys spread beside `visType`, with no `config` key. A patch that sends that flat shape back **silently keeps only `visType`** and drops the rest (verified live: flat-sent `markdownConfig`/`alignment` dropped; `config`-nested persisted). This is the most damaging *silent* failure in the v2 API — misplaced presentation-level keys 400 loudly. Never round-trip a GET tile unchanged; re-nest the inner spec under `config` first.

**Failure modes:**

| What you send | What happens |
|--------------|--------------|
| Inner spec **flat** inside `visConfig.visConfig` (no `config` key) | **Silently dropped** — only `visType` persists; the tile auto-renders or goes blank. |
| `chartType` / `config` / `fields` at the presentation top level (v1 shape) | **400** "Unrecognized key". |
| `modelId` / `model_extension_id` inside `query` (or the v1 `query.visConfig` hint) | **Silently ignored/rewritten** — tile queries are server-anchored to the workbook model. Omit them. |
| `query` missing required collection fields (`sorts`, `filters`, `calculations`, …) | **400** listing each missing field. |
| `barColor` / `areaColor` / `stackedBarColor` | Rejected — not in the `chartType` enum. |

**Verify after writing:** read the document back (`omni documents v2-get <identifier>` or `v2-get-draft`) and confirm the tile's `visConfig.chartType` is set and the flat inner `visConfig` contains more than just `visType`. If only `visType` survived, the write sent the flat shape — re-nest under `config` and retry.

## chartType Values

These are the supported `chartType` values for building tiles with a structured inner `config`. Feature-flagged, deprecated, and non-config-driven viz types — e.g. the raw Vega code editor and interactive spreadsheets — are intentionally omitted. A stacked **column** is vertical; a stacked **bar** is horizontal.

| chartType | Family | Description |
|-----------|--------|-------------|
| `"auto"` | Auto | Let Omni choose the chart type |
| `"table"` | Table | Data table |
| `"kpi"` | KPI | Single value / big number |
| `"line"` | Cartesian | Line chart |
| `"lineColor"` | Cartesian | Line chart with color (series) encoding |
| `"column"` | Cartesian | Vertical bars |
| `"columnGrouped"` | Cartesian | Grouped vertical bars |
| `"columnStacked"` | Cartesian | Stacked vertical bars |
| `"columnStackedPercentage"` | Cartesian | 100% stacked vertical bars |
| `"bar"` | Cartesian | Horizontal bars |
| `"barGrouped"` | Cartesian | Grouped horizontal bars |
| `"barStacked"` | Cartesian | Stacked horizontal bars |
| `"barStackedPercentage"` | Cartesian | 100% stacked horizontal bars |
| `"barLine"` | Cartesian | Combo bar + line |
| `"area"` | Cartesian | Area chart |
| `"areaStacked"` | Cartesian | Stacked area chart |
| `"areaStackedPercentage"` | Cartesian | 100% stacked area chart |
| `"point"` | Cartesian | Scatter plot |
| `"pointColor"` | Cartesian | Scatter with color encoding |
| `"pointSize"` | Cartesian | Scatter with size encoding |
| `"pointSizeColor"` | Cartesian | Bubble (size + color) |
| `"boxplot"` | Cartesian/boxplot | Box-and-whisker plot |
| `"heatmap"` | Heatmap | Heatmap grid |
| `"pie"` | Polar | Pie / donut |
| `"funnel"` | Funnel | Funnel chart |
| `"sankey"` | Sankey | Sankey flow diagram |
| `"map"` | Map | Point map (lat/lng) |
| `"regionMap"` | Map | Choropleth / region map |
| `"markdown"` | Text | Markdown content tile |
| `"omni-ai-summary-markdown"` | Text | AI-generated summary tile |
| `"singleRecord"` | Detail | Single record viewer |

> **Not valid** (common mistakes): `barColor`, `areaColor`, `stackedBarColor`, `scatter`, `rect`. Use `column`/`bar`, `area`, `columnStacked`/`barStacked`, `point`, and `heatmap` respectively.

## chartType → visType → configType mapping

`visType` is the renderer. `configType` is the discriminator **inside the inner `config`** (`visConfig.visConfig.config` on write) — and it only exists for the `"basic"` renderer (cartesian, polar, heatmap, boxplot). Funnel/sankey/map/etc. have their own `visType` and **no `configType`**.

| chartType | visType | configType | mark.type | _dependentAxis |
|-----------|---------|------------|-----------|----------------|
| `table` | `omni-table` | — | — | — |
| `kpi` | `omni-kpi` | — | — | — |
| `line`, `lineColor` | `basic` | `cartesian` | `line` | `y` |
| `column`, `columnGrouped`, `columnStacked`, `columnStackedPercentage` | `basic` | `cartesian` | `bar` | `y` |
| `bar`, `barGrouped`, `barStacked`, `barStackedPercentage` | `basic` | `cartesian` | `bar` | `x` |
| `area`, `areaStacked`, `areaStackedPercentage` | `basic` | `cartesian` | `area` | `y` |
| `point`, `pointColor`, `pointSize`, `pointSizeColor` | `basic` | `cartesian` | `point` | `y` |
| `barLine` | `basic` | `cartesian` | per-series | `y` |
| `pie` | `basic` | `polar` | — | — |
| `heatmap` | `basic` | `heatmap` | — | — |
| `boxplot` | `basic` | `boxplot` | — | — |
| `funnel` | `funnel` | — | — | — |
| `sankey` | `sankey` | — | — | — |
| `map` | `map` | — | — | — |
| `regionMap` | `map` | — | — | — |
| `markdown` | `omni-markdown` | — | — | — |
| `singleRecord` | `single-record` | — | — | — |

## Config Object: Cartesian Charts

Line, column, bar, area, scatter, and combo charts use the cartesian config (`configType: "cartesian"`). This is the most common config type.

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `configType` | Yes | string | Always `"cartesian"` |
| `_dependentAxis` | Yes | string | `"y"` for vertical charts (line, area, **column**, scatter); `"x"` for horizontal **bar** charts |
| `x` | Conditional | object | Independent (category) axis field; used when `_dependentAxis: "y"` |
| `y` | Conditional | object | Independent (category) axis field; used when `_dependentAxis: "x"` (horizontal bars) |
| `mark` | Yes | object | `{ "type": "line" \| "bar" \| "area" \| "point" }` (both column and bar use `"bar"`) |
| `color` | Yes | object | Color/stacking config (see below) |
| `series` | Yes | array | Measure fields, each with `"yAxis": "y"` (vertical) or `"xAxis": "x"` (horizontal) |
| `tooltip` | Yes | array | Fields shown on hover |
| `behaviors.stackMultiMark` | No | boolean | `true` for stacked, `false` for grouped/overlay |
| `size` | No | object | Field for bubble sizing (`pointSize` / `pointSizeColor`) |

### Axis fields (`x` / `y`)

```json
"x": { "field": { "name": "order_items.created_at[month]" } }
```

Optional axis properties: `label`, `showLabel`, `showGridLines`, `tickFormat`, `scale` (e.g. `{ "type": "log" }`), `domain` (`[min, max]`).

### color object — controls stacking and series color

| Pattern | Usage |
|---------|-------|
| `{}` | Single series, auto color |
| `{ "_stack": "group", "field": { "name": "..." } }` | Grouped (side-by-side) — `chartType` `*Grouped` |
| `{ "_stack": "stack", "field": { "name": "..." } }` | Stacked — `chartType` `*Stacked` |
| `{ "_stack": "normalize", "field": { "name": "..." } }` | 100% stacked — `chartType` `*StackedPercentage` |
| `{ "field": { "name": "..." } }` | Color by dimension (no stacking) — e.g. multi-series line/scatter |

The `color.field` is the dimension that splits the series; it must also be in `query.pivots` for stacked/grouped charts.

### series array

```json
"series": [
  { "field": { "name": "order_items.total_revenue" }, "yAxis": "y" }
]
```

Per-entry properties: `field.name`, `yAxis` (`"y"`/`"y2"`) or `xAxis` (`"x"`/`"x2"`), `label`, `color` (hex override), `mark` (per-series mark for combo charts), `dataLabel`.

## Config Object: KPI

KPI tiles use `chartType: "kpi"`, `visType: "omni-kpi"`, and **no `configType`**.

| Field | Required | Description |
|-------|----------|-------------|
| `alignment` | No | Horizontal: `"left"`, `"center"`, `"right"` |
| `verticalAlignment` | No | Vertical: `"top"`, `"center"`, `"bottom"` |
| `markdownConfig` | Yes | Array of KPI section entries |

Each `markdownConfig` entry: `{ id, type, config, lastModified? }` where `type` is `"number"` (also `comparison`, `sparkline`, `progress`, `text`, `image`). For a number: `config.field = { row: "_first", field: { name, pivotMap: {} }, label: { value } }`, plus optional `config.descriptionBefore` / `descriptionAfter`.

## Config Object: Pie / Donut

`chartType: "pie"`, `visType: "basic"`, `config.configType: "polar"`.

| Field | Required | Description |
|-------|----------|-------------|
| `configType` | Yes | `"polar"` |
| `theta` | Yes | The measure field that sizes each slice (`{ "field": { "name": "..." } }`) |
| `color` | Recommended | The dimension that defines the slices (`{ "field": { "name": "..." } }`) |
| `pastry` | No | `"pie"` (default) or `"donut"` |
| `innerRadiusPercent` | No | `0`–`100`, donut hole size |
| `tooltip` | No | Fields for hover |

## Config Object: Heatmap

`chartType: "heatmap"`, `visType: "basic"`, `config.configType: "heatmap"`.

| Field | Required | Description |
|-------|----------|-------------|
| `configType` | Yes | `"heatmap"` |
| `x` | Yes | X-axis dimension field |
| `y` | Yes | Y-axis dimension field |
| `color` | Yes | The measure field that drives cell intensity |
| `tooltip` | No | Fields for hover |

## Config Object: Boxplot

`chartType: "boxplot"`, `visType: "basic"`, `config.configType: "boxplot"`. Fields: `x` or `y` (category), `color`, `dataLabel`, `tooltip`.

## Config Object: Funnel

`chartType: "funnel"`, `visType: "funnel"`, **no `configType`**.

| Field | Required | Description |
|-------|----------|-------------|
| `value` | Yes | The measure field (segment size), `{field:{name}}` |
| `color` | Recommended | Dimension that defines/labels segments, `{field:{name}}` |
| `orient` | No | `"vertical"` (default) / `"horizontal"` — note the key is `orient`, not `orientation` |
| `funnelAlign` | No | `"center"` / `"left"` / `"right"` / `"top"` / `"bottom"` |
| `sort` | No | `"descending"` (default) / `"ascending"` / `"none"` |
| `dataLabel`, `tooltip` | No | Labels / hover |

> In a wide, short dashboard tile a funnel can collapse to an unreadable sliver. Set `orient: "vertical"`, `funnelAlign: "center"`, `sort: "descending"`, and `dataLabel: { "enabled": true, "position": "inside" }` so it draws a clean funnel regardless of tile aspect.

## Config Object: Sankey

`chartType: "sankey"`, `visType: "sankey"`, **no `configType`**. Fields: `source`, `target` (node dimensions), `value` (flow measure), `color`, `tooltip`.

## Config Object: Map / Region Map

**Point map** — `chartType: "map"`, `visType: "map"`, no `configType`. Key fields: `latitudeFieldName`, `longitudeFieldName` (plain field-name strings), plus optional `markType` (`"circle"`/`"heatmap"`), `markRadius`, `color`, `size`, `tooltip`, `zoom`, `center`.

**Region / choropleth map** — `chartType: "regionMap"`, `visType: "map"` (the Mapbox renderer), no `configType`.

| Field | Required | Description |
|-------|----------|-------------|
| `regionType` | Yes | `"us-states"` or `"countries"` (not `"US"`) |
| `regionFieldName` | Yes | Dimension holding the region names/codes (plain string) |
| `sourceProperty` | Yes | Which layer property your values match. US states: `"NAME"` (full names) or `"CODE"` (2-letter). Countries: `"iso_3166_1"` (2-letter), `"iso_3166_1_alpha_3"` (3-letter), or `"name_en"`. **A mismatch renders the base map with no shading.** |
| `color` | Yes | The measure, `{field:{name}}` |
| `center`, `zoom` | Recommended | Viewport (e.g. `[-98.35, 39.5]` / `3` for the US). Without it the map fits to data and may zoom into a single locality. |

> Map specs are best captured by building one in the UI and reading it back (`omni documents v2-get`, re-nesting the flat inner spec under `config`).

---

## Complete Examples

**Convention:** the first example shows a complete tile in the v2 envelope. Every example after it shows **only the `visConfig` envelope** — drop it into a tile alongside `name`, `type: "query"`, `topicName`, `prefersChart: true`, `automaticVis: false`, and a `query` with the full required-field set (see [queryPresentations.md](queryPresentations.md)).

### Line Chart (complete tile)

```json
{
  "name": "Monthly Revenue Trend",
  "type": "query",
  "topicName": "order_items",
  "prefersChart": true,
  "automaticVis": false,
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
        "behaviors": { "stackMultiMark": false },
        "configType": "cartesian",
        "_dependentAxis": "y"
      }
    }
  },
  "query": {
    "table": "order_items",
    "fields": ["order_items.created_at[month]", "order_items.total_revenue"],
    "sorts": [{ "column_name": "order_items.created_at[month]", "sort_descending": false }],
    "filters": { "order_items.created_at": "last 6 months" },
    "limit": 100,
    "join_paths_from_topic_name": "order_items",
    "calculations": [], "column_totals": {}, "row_totals": {},
    "fill_fields": [], "pivots": [], "userEditedSQL": ""
  }
}
```

### Column Chart (Vertical Bars)

```json
"visConfig": {
  "chartType": "column",
  "fields": ["products.category", "order_items.total_revenue"],
  "version": 0,
  "visConfig": {
    "visType": "basic",
    "config": {
      "x": { "field": { "name": "products.category" } },
      "mark": { "type": "bar" },
      "color": {},
      "series": [{ "field": { "name": "order_items.total_revenue" }, "yAxis": "y" }],
      "tooltip": [
        { "field": { "name": "products.category" } },
        { "field": { "name": "order_items.total_revenue" } }
      ],
      "behaviors": { "stackMultiMark": false },
      "configType": "cartesian",
      "_dependentAxis": "y"
    }
  }
}
```

### Bar Chart (Horizontal Bars)

Dimension on y-axis, measure on x-axis. Note `_dependentAxis: "x"` and `series[].xAxis`.

```json
"visConfig": {
  "chartType": "bar",
  "fields": ["products.name", "order_items.total_revenue"],
  "version": 0,
  "visConfig": {
    "visType": "basic",
    "config": {
      "y": { "field": { "name": "products.name" } },
      "mark": { "type": "bar" },
      "color": {},
      "series": [{ "field": { "name": "order_items.total_revenue" }, "xAxis": "x" }],
      "tooltip": [
        { "field": { "name": "products.name" } },
        { "field": { "name": "order_items.total_revenue" } }
      ],
      "behaviors": { "stackMultiMark": false },
      "configType": "cartesian",
      "_dependentAxis": "x"
    }
  }
}
```

### Stacked Column Chart (Vertical)

`_stack: "stack"` with a **pivoted** color dimension — the query must include `"pivots": ["order_items.status"]`. For horizontal, use `chartType: "barStacked"` with `_dependentAxis: "x"` and `series[].xAxis: "x"`. For 100% stacking, use `columnStackedPercentage` with `color._stack: "normalize"`.

```json
"visConfig": {
  "chartType": "columnStacked",
  "fields": ["order_items.created_at[quarter]", "order_items.status", "order_items.distinct_order_count"],
  "version": 0,
  "visConfig": {
    "visType": "basic",
    "config": {
      "x": { "field": { "name": "order_items.created_at[quarter]" } },
      "mark": { "type": "bar" },
      "color": { "_stack": "stack", "field": { "name": "order_items.status" } },
      "series": [{ "field": { "name": "order_items.distinct_order_count" }, "yAxis": "y" }],
      "tooltip": [
        { "field": { "name": "order_items.created_at[quarter]" } },
        { "field": { "name": "order_items.status" } },
        { "field": { "name": "order_items.distinct_order_count" } }
      ],
      "behaviors": { "stackMultiMark": true },
      "configType": "cartesian",
      "_dependentAxis": "y"
    }
  }
}
```

### Stacked Area Chart

Same as the stacked column but `chartType: "areaStacked"` and `mark.type: "area"`.

### Combo Chart (Bar + Line)

`chartType: "barLine"`; each series carries its own `mark`, and the line series uses the secondary axis `yAxis: "y2"`.

```json
"visConfig": {
  "chartType": "barLine",
  "fields": ["order_items.created_at[month]", "order_items.total_revenue", "order_items.count"],
  "version": 0,
  "visConfig": {
    "visType": "basic",
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
      "behaviors": { "stackMultiMark": false },
      "configType": "cartesian",
      "_dependentAxis": "y"
    }
  }
}
```

### Scatter / Bubble

`chartType: "pointColor"` (color by dimension) or `"pointSizeColor"` (add `size`). `mark.type: "point"`.

```json
"visConfig": {
  "chartType": "pointSizeColor",
  "fields": ["order_items.average_sale_price", "order_items.count", "order_items.total_revenue", "products.category"],
  "version": 0,
  "visConfig": {
    "visType": "basic",
    "config": {
      "x": { "field": { "name": "order_items.average_sale_price" } },
      "mark": { "type": "point" },
      "color": { "field": { "name": "products.category" } },
      "size": { "field": { "name": "order_items.total_revenue" } },
      "series": [{ "field": { "name": "order_items.count" }, "yAxis": "y" }],
      "tooltip": [
        { "field": { "name": "order_items.average_sale_price" } },
        { "field": { "name": "order_items.count" } },
        { "field": { "name": "order_items.total_revenue" } },
        { "field": { "name": "products.category" } }
      ],
      "behaviors": { "stackMultiMark": false },
      "configType": "cartesian",
      "_dependentAxis": "y"
    }
  }
}
```

### KPI (Single Value)

```json
"visConfig": {
  "chartType": "kpi",
  "fields": ["order_items.total_revenue"],
  "version": 0,
  "visConfig": {
    "visType": "omni-kpi",
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
}
```

### Pie / Donut

```json
"visConfig": {
  "chartType": "pie",
  "fields": ["products.category", "order_items.total_revenue"],
  "version": 0,
  "visConfig": {
    "visType": "basic",
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
  }
}
```

For a donut, set `"pastry": "donut"` and optionally `"innerRadiusPercent": 50`.

### Heatmap

```json
"visConfig": {
  "chartType": "heatmap",
  "fields": ["order_items.created_day_of_week", "order_items.created_hour", "order_items.count"],
  "version": 0,
  "visConfig": {
    "visType": "basic",
    "config": {
      "configType": "heatmap",
      "x": { "field": { "name": "order_items.created_hour" } },
      "y": { "field": { "name": "order_items.created_day_of_week" } },
      "color": { "field": { "name": "order_items.count" } },
      "tooltip": [
        { "field": { "name": "order_items.created_day_of_week" } },
        { "field": { "name": "order_items.created_hour" } },
        { "field": { "name": "order_items.count" } }
      ]
    }
  }
}
```

### Table (No Chart)

Set `prefersChart: false` on the tile; the inner `config` is an empty object.

```json
"visConfig": {
  "chartType": "table",
  "fields": ["order_items.status", "order_items.count", "order_items.total_revenue"],
  "version": 0,
  "visConfig": { "visType": "omni-table", "config": {} }
}
```

---

## Discovering Config for Advanced Chart Types

For families not fully covered here (funnel, sankey, boxplot, map, regionMap, singleRecord), build the chart in the Omni UI and read it back:

```bash
omni documents v2-get <identifier>
```

Each tile's `visConfig` shows the persisted `chartType`, `fields`, and inner `visConfig` — with the rendering spec **flattened beside `visType`** (no `config` key). To reuse it as a template, move every inner key except `visType` under a `config` key.

> **Tip**: Build one reference dashboard in the UI with every chart type you need, read it back once, and reuse those (re-nested) `config` objects as templates.

## resultConfig

Optional field on `queryPresentation` controlling result display independent of the visualization. Commonly includes `columnOrder` (array), `hiddenColumns` (array), `columnWidths` (object of field → pixel width).

### Table display & conditional formatting

- **Fill the tile**: set `resultConfig.tableType: "stretch"` — the default `"spreadsheet"` hugs the left and leaves whitespace.
- **Conditional formatting** lives in `resultConfig.conditionalFormatters` (an array):

```jsonc
"conditionalFormatters": [
  { "id": "…", "type": "scale",  "selection": { "type": "field", "field": "…" },
    "format": { "range": ["#f00","#ff0","#0f0"], "domain": { "min": 0, "mid": 50, "max": 100 } } },
  { "id": "…", "type": "single", "selection": { "type": "field", "field": "…" },
    "rule":   { "type": "greater-than", "value": 1000, "valueType": "number" },
    "format": { "backgroundColor": "#fee", "color": "#900", "fontWeight": "bold" } }
]
```

`selection.type` may be `field`, `row`, or `cellRange`. **To keep conditional formatting from being dropped**, set the tile to `visType: "omni-table"` with `automaticVis: false` (otherwise a later write can regenerate a default table config and discard your formatters). The omni-table viz also needs `prefersChart: true` to apply `resultConfig`.

## aiConfig

Enables AI-generated descriptions/subtitles on tiles:

```json
"aiConfig": {
  "description": { "enabled": true, "aiContext": "Summarize this data focusing on trends" },
  "subTitle": { "enabled": true, "aiContext": "One-line summary of the key takeaway" }
}
```

## Common Mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| Inner spec sent **flat** (no `config` key inside `visConfig.visConfig`) | Spec **silently dropped** — only `visType` persists; tile auto-renders or goes blank | Nest the spec under `visConfig.visConfig.config`; never round-trip the flat GET shape |
| `chartType` / `config` / `fields` at the presentation top level (v1 shape) | **400** "Unrecognized key" | Move them into the `visConfig` envelope |
| `modelId` / `model_extension_id` (or v1 `visConfig` hint) in the tile query | Silently ignored/rewritten | Remove — tile queries are server-anchored to the workbook model |
| Query missing required collection fields | **400** listing each missing field | Include `sorts`, `filters`, `calculations`, `column_totals`, `row_totals`, `fill_fields`, `pivots`, `userEditedSQL` (empty fine) plus `table`, `fields`, and always send `limit`, `join_paths_from_topic_name` |
| `barColor` / `areaColor` / `stackedBarColor` | Request rejected (invalid enum) | Use `column`/`bar`, `area`, `columnStacked`/`barStacked` |
| `configType: "pie"` / `"funnel"` / `"map"` | Wrong/missing config | Pie → `configType: "polar"`; funnel/sankey/map have **no** `configType` (use the right `visType`) |
| `prefersChart` is `false` or missing | Always shows table | Set `prefersChart: true` |
| `_dependentAxis` mismatched | Axes inverted / column vs bar wrong | `"y"` for vertical (column/line/area), `"x"` for horizontal bars |
| `series[].yAxis` vs `xAxis` wrong | Measures don't render | `yAxis: "y"` for vertical, `xAxis: "x"` for horizontal |
| Stack dimension not pivoted | Single un-split series | Add the `color.field` dimension to `query.pivots` |
| Missing measure in query | Empty tile, no error | Every query must include at least one measure |
| `regionMap` not shading | "No chart available" / blank map | Use `visType: "map"`, `regionType: "us-states"`/`"countries"`, a `sourceProperty` matching your field's values (`"NAME"`/`"CODE"`/iso codes), and `center`/`zoom` |
| `chartType: "auto"` with empty config | "No chart available" | `auto` can't persist a render; populate a concrete spec (or build in UI and read back) |
| `aiContext`/`markdown` on AI-summary tile | Renders blank/wrong | Use `ai_context` + `showWarning` (snake_case) |

## Text & AI tiles

- **Markdown** (`chartType: "markdown"`, `visType: "omni-markdown"`): `config: { markdown: "...", version: 1 }`. The markdown body is **mustache-templated against the tile's query** — loop rows with `{{#result}} … {{view_name.field_name.value_static}} … {{/result}}` and reference single values like `{{result._first.view_name.field_name.value_static}}` or `{{result._total.first.view_name.field_name.value_static}}`. Keep a real query on the tile so the template has data.
  - **Use `.value_static` for a clean value**, not `.value`. `.value_static` is the formatted display string; `.value` is an interactive drill element (a clickable component, not plain text).
  - Result rows are keyed by **field name** — there is **no positional column token** (you must name the field, not "column 1").
  - **Set `automaticVis: false` and `prefersChart: false` on the tile**, or the published renderer ignores your markdown and tries to auto-derive a chart from the query → the tile renders **blank** with no error. Tell-tale: `{{result…}}` tokens resolve when tested but the whole tile is white.
  - **The HTML sanitizer allows `style`, `className`, and `data-*` attributes plus `<style>` blocks**, so you can ship scoped CSS inside a markdown tile. (A sandboxed `<iframe>` with `allow-scripts` is also available for arbitrary JS if CSS isn't enough.)
  - **`{{controls.<id>.summary}}`** injects a dashboard control's current selection (its friendly label) into the body — the basis of dynamic captions and the metric-switch pattern below. Only **dashboard** controls resolve here, not tile-embedded `query.controls`. See [controls.md](controls.md).
- **AI summary** (`chartType: "omni-ai-summary-markdown"`, `visType: "omni-ai-summary-markdown"`): `config: { ai_context: "...", showWarning: true }` (snake_case `ai_context`, **not** `aiContext`; no `markdown`/`version`). Requires a query — the AI summarizes its results.

### Sizing markdown tiles (heights) — they clip easily

Markdown/text tiles clip far more readily than chart tiles. What actually governs it:

- **Grid `h` is ~4–5px per unit.** Empirical reference points for a markdown tile with the default `style: "tile"` chrome: a **single line of text ≈ h:7–8**, **two lines ≈ h:11**, a **28–32px KPI value ≈ h:16–18**.
- **`style: "tile"` eats ~16px** of vertical space (`--tile-margin` padding on every side). The usable content height ≈ tile height − that chrome, so small tiles clip even when the text "should" fit — **budget +3–4 h-units over the bare text height**.
- **Keep the markdown tight.** A `<style>` block followed by **blank lines** renders as empty paragraphs at the *top* of the tile, pushing the visible content down so it looks bottom-anchored or clipped. Put `<style>` and the content on adjacent lines with no blank lines between blocks.
- **Vertical-center only when there's room.** `<div style="height:100%; display:flex; align-items:center; justify-content:center">` centers cleanly — but only once the tile clears chrome + content. At minimal heights it still clips; there, use natural top-flow with small padding instead.
- **When a tile clips, add height, not padding.** The content area is simply smaller than what's rendering; +2–3 h-units fixes it where padding tweaks won't.

### A markdown KPI card that follows a metric picker

A markdown tile can present a styled KPI whose value **and** label track a `FIELD_SELECTION` switcher — without a table calc. The trick is a **multi-measure query + a CSS attribute-selector switch**:

1. Query returns **all** candidate measures as columns (one `limit 1` row).
2. Render one hidden `<span data-m="<Label>">` per measure, each reading `{{result._first.<view>.<field>.value_static}}`.
3. Put the control's selection on a wrapper via `data-sel="{{controls.<id>.summary}}"`, and add one CSS rule per metric that reveals the matching span.

```html
<style>
.kpival .m{display:none;font-size:32px;font-weight:700;}
.kpicard[data-sel="Total Revenue"] .m[data-m="Total Revenue"],
.kpicard[data-sel="Total Margin"]  .m[data-m="Total Margin"]{display:block;}
</style>
<div class="kpicard" data-sel="{{controls.kpi_metric_1.summary}}">
  <div class="kpilabel">{{controls.kpi_metric_1.summary}}</div>
  <div class="kpival">
    <span class="m" data-m="Total Revenue">{{result._first.ecomm__order_items.total_revenue.value_static}}</span>
    <span class="m" data-m="Total Margin">{{result._first.ecomm__order_items.total_margin.value_static}}</span>
  </div>
</div>
```

The control's option **labels must match** the `data-m`/`data-sel` strings (`.summary` returns the label). This switches in the presentation layer — the control never mutates the query — so it sidesteps the interactive-control scoping limitation. Place the switcher in-tile (see [containers.md](containers.md)).

> **Why a table calc can't do this.** A table calc — including a cell reference like `=A1` — binds to a **field name at author time** (stored as `{type:'field', field_name:…}`). A field picker swaps *which field* is in the query, so the calc keeps pointing at the original field and does not follow the switch. Use the CSS pattern above (or a templated-filter + CASE measure) instead.

## Safe Defaults

**Table fallback (always works):**
```json
{
  "prefersChart": false,
  "automaticVis": false,
  "visConfig": { "chartType": "table", "fields": ["..."], "version": 0, "visConfig": { "visType": "omni-table", "config": {} } },
  "query": { "...": "full required-field set" }
}
```

An empty inner `config: {}` is fine for tables.

> **`chartType: "auto"` is not a persistable render** — a tile saved with `auto` + an empty `config` shows "No chart available", because `auto` only resolves to a concrete chart at render time from live results. To create an auto-styled tile, populate a concrete `chartType` + inner `config` (build it in the UI and read it back if unsure).

> **Recommendation**: For an unfamiliar chart type, build it once in the UI, read it back with `omni documents v2-get`, and reuse the inner vis config — re-nested under `config` — as your template. That is the most reliable path to a correct config.
