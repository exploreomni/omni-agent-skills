# Pie, heatmap, boxplot, funnel, sankey and map configs

The inner `config` shapes for the chart families that are not cartesian: pie and donut (`configType: "polar"`), heatmap, boxplot, funnel, sankey, point map and region map. The envelope, the `chartType` enum and the cartesian shapes are in [visConfig.md](visConfig.md). For these families, always confirm the inner field names by reading back an existing dashboard that uses the chart (`omni documents v2-get` returns the inner spec in the shape you write).

## Table of Contents

- [Config Object: Pie / Donut](#config-object-pie--donut)
- [Config Object: Heatmap](#config-object-heatmap)
- [Config Object: Boxplot](#config-object-boxplot)
- [Config Object: Funnel](#config-object-funnel)
- [Config Object: Sankey](#config-object-sankey)
- [Config Object: Map / Region Map](#config-object-map--region-map)
- [Complete example: Pie / Donut](#complete-example-pie--donut)
- [Complete example: Heatmap](#complete-example-heatmap)

## Config Object: Pie / Donut

`chartType: "pie"`, `visType: "basic"`, `config.configType: "polar"`.

| Field | Required | Description |
|-------|----------|-------------|
| `configType` | Yes | `"polar"` |
| `theta` | Yes | The measure field that sizes each slice (`{ "field": { "name": "..." } }`) |
| `color` | Recommended | The dimension that defines the slices (`{ "field": { "name": "..." } }`) |
| `pastry` | No | `"pie"` (default) or `"donut"` |
| `innerRadiusPercent` | No | `0`–`100`, donut hole size = ring thinness. `66` ≈ thin ring, `~40` chunky, `0` = solid pie. |
| `outerRadiusPercent` | No | `0`–`100`. **Defaults to 90 — but auto-shrinks to `90 × 0.7 ≈ 63` whenever `dataLabel.enabled`** (reserves label room). If labels are on and the donut looks small, set this explicitly (e.g. `80`). |
| `dataLabel` | No | `{ enabled: true, field: { name } }`. `field` sets **what the slice label shows** — point it at the `color` dimension to label slices by category; omit `field` and it shows the `theta` value. |
| `dataLabelPercentage` | No | `{ enabled: true, decimals: 1 }` — **appends the auto share** → `"Category (23.4%)"`. Separator is hardcoded parentheses (no dash). `percent` = ECharts' share of the `theta` total. |
| `dataLabelPosition` | No | `"inside"` / `"outside"` — a **top-level polar key**, not `dataLabel.position`. |
| `tooltip` | No | Fields for hover |

> **No legend sizing.** The pie config exposes no legend-size control — the only legend option is `color.legendPosition`, lowercase: `right`, `left`, `top`, `bottom`, or `none` to hide it. A larger/custom legend requires a markdown tile.
> **"Category — xx.y%" slice labels (value + share):** `dataLabel: { enabled: true, field: { name: "<the color dim>" } }` + `dataLabelPercentage: { enabled: true, decimals: 1 }`; keep `theta` as the raw count. The label renders the `dataLabel.field` value with the share appended in parentheses — `"Category (23.4%)"` — when `dataLabelPercentage.enabled`. (Verify by building it once in the UI and reading it back with `omni documents v2-get`.)

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

> **Funnel and sankey still nest their spec under `config`:** `visConfig.visConfig = { visType: "funnel", config: { value, color, orient, … } }`. They only leave out the `configType` field inside `config`, which exists only for the `"basic"` renderer.

| Field | Required | Description |
|-------|----------|-------------|
| `value` | Yes | The measure field (segment size), `{field:{name}}` |
| `color` | Recommended | Dimension that defines/labels segments, `{field:{name}}` |
| `orient` | No | `"vertical"` (default) / `"horizontal"` — note the key is `orient`, not `orientation` |
| `funnelAlign` | No | `"center"` / `"left"` / `"right"` / `"top"` / `"bottom"` |
| `sort` | No | `"descending"` (default) / `"ascending"` / `"none"` |
| `dataLabel`, `tooltip` | No | Labels / hover |

> In a wide, short dashboard tile a funnel can collapse to an unreadable sliver. Set `orient: "vertical"`, `funnelAlign: "center"`, `sort: "descending"`, and `dataLabel: { "enabled": true, "position": "inside" }` so it draws a clean funnel regardless of tile aspect.

> **Funnel from multiple measures (stage = a measure, not a dimension).** The funnel needs a stage *dimension* + one measure, so a wide query of N separate measures (e.g. `units_sold`, `shipped_items`, `delivered_items`) won't funnel directly. Reshape it to long form with the query's **`transposed_measures`** (an array of those measure names — see `omni-query` → *Transpose measures into rows*): the result gains synthetic `measure_name` (renders as each measure's friendly label) + `measure_value` columns. Then set the funnel `color: { field: { name: "measure_name" } }` and `value: { field: { name: "measure_value" } }` with `sort: "descending"`.

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

> To capture a map spec, read back an existing dashboard with a map tile (`omni documents v2-get`) and reuse its config.

> **Point maps auto-fit to the data's bounding box.** Set `center`/`zoom` to frame a region, but the map won't zoom *tighter* than the extent of your points — e.g. a US map of distribution centers spanning LA↔NY caps at a coast-to-coast frame; pushing `zoom` higher clips the edge points rather than enlarging the country. Tune `zoom` to taste (≈3.6–3.8 for the contiguous US) and accept that the data spread sets the floor.

---

## Complete example: Pie / Donut

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

## Complete example: Heatmap

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
