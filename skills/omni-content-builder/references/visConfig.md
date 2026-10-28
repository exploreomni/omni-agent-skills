# visConfig Reference

Complete reference for a tile's visualization config — the v2 `visConfig` envelope, accepted `chartType` values, the inner `config` object structure for each chart family, and worked examples.

## Table of Contents

- [Where the visualization config lives](#where-the-visualization-config-lives)
- [chartType Values](#charttype-values) — the authoritative enum
- [chartType → visType → configType mapping](#charttype--vistype--configtype-mapping)
- [Config Object: Cartesian Charts](#config-object-cartesian-charts) — line, column, bar, area, scatter, combo
- [Layer-compiled cartesian charts](#layer-compiled-cartesian-charts-the-layers-editor) — the layers editor: what it writes, Measure values, creating and moving tiles, the editor's words and their keys, what a layer can carry, a catalog of rendered shapes, gotchas that change
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

> **Important**: The visualization config schema is not fully documented in Omni's public API docs. The cartesian structures below (axis, color, series, mark) are derived from Omni's visualization parser schema and cross-checked by reading dashboards back via `omni documents v2-get`. For uncommon chart types (funnel, sankey, map, boxplot, single-record), **always verify** by reading back an existing dashboard that uses the chart type before relying on these examples.

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

> **Reads return the shape you write.** `v2-get` / `v2-get-draft` return the inner config as `{ visType, config }`, so a tile read back can be written back unchanged, including for restores, duplicates, and moves. A spec sent flat beside `visType` is also accepted and moved under `config`. Misplaced *presentation*-level keys (`chartType` / `config` / `fields` at the tile top level) return a 400.

**Failure modes:**

| What you send | What happens |
|--------------|--------------|
| Inner spec **flat** beside `visType` | Accepted and moved under `config` on write. |
| `chartType` / `config` / `fields` at the presentation top level (v1 shape) | **400** "Unrecognized key". |
| `modelId` / `model_extension_id` inside `query` (or the v1 `query.visConfig` hint) | **Silently ignored/rewritten** — tile queries are server-anchored to the workbook model. Omit them. |
| `query` missing required collection fields (`sorts`, `filters`, `calculations`, …) | **400** listing each missing field. |
| `barColor` / `areaColor` / `stackedBarColor` | Rejected — not in the `chartType` enum. |

**Verify after writing:** read the document back (`omni documents v2-get <identifier>` or `v2-get-draft`) and confirm the tile's `visConfig.chartType` is set and `visConfig.visConfig.config` is non-empty.

## chartType Values

These are the supported `chartType` values for building tiles with a structured inner `config`. Three enum values are not authored through this skill: `code` (the raw Vega editor, `visType: "vegalite"`), `omni-spreadsheet`, and the deprecated `summaryValue`. A stacked **column** is vertical; a stacked **bar** is horizontal.

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
| `"svgMap"` | Map | SVG region map (`visType: "svg-map"`) |
| `"treemap"` | Treemap | Treemap (`visType: "treemap"`) |
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
| `svgMap` | `svg-map` | — | — | — |
| `treemap` | `treemap` | — | — | — |
| `markdown` | `omni-markdown` | — | — | — |
| `singleRecord` | `single-record` | — | — | — |

## Config Object: Cartesian Charts

Line, column, bar, area, scatter, and combo charts use the cartesian config (`configType: "cartesian"`). This is the most common config type.

The shapes in this section are read by the **classic** compiler, which is what a config gets unless it carries `behaviors.useLayerCompiler: true`. Charts built in the UI's X/Y chart editor are now **layer-compiled** and store their encodings per layer — see [Layer-compiled cartesian charts](#layer-compiled-cartesian-charts-the-layers-editor) for that shape, how it differs, and how to move a tile between the two.

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
| `behaviors.useLayerCompiler` | No | boolean | `true` routes the config to the layer compiler and the layers editor; absent or `false` keeps the classic compiler. See [Layer-compiled cartesian charts](#layer-compiled-cartesian-charts-the-layers-editor) |
| `size` | No | object | Field for bubble sizing (`pointSize` / `pointSizeColor`) |

### Axis fields (`x` / `y`)

There are **two distinct uses** of `x`/`y` in a cartesian config, and the axis-styling object lives at different depths in each:

- The **independent (dimension) axis** carries the field mapping *and* its styling: `{ "field": {...}, "axis": { …styling… } }`. For a vertical chart that's `x`; for a horizontal bar it's `y`.
- The **dependent (value) axis** carries **only styling** (no field — measures live in `series`): `{ "axis": { …styling… }, … }`. For a vertical chart that's `y`; for a horizontal bar it's `x`.

```json
"x": { "field": { "name": "order_items.created_at[month]" } },
"y": { "axis": { "domain": { "zero": false }, "title": { "value": "Revenue ($)" } } }
```

> **The styling object is always nested one level down, under `axis`.** Putting `domain`/`title`/`scale` directly on `x`/`y` (e.g. `y.domain`, `y.min`) is **silently ignored** — the #1 axis-config mistake. The correct path is `<axisName>.axis.<prop>`.

#### `axis` styling properties (all optional)

| Property | Shape | Notes |
|----------|-------|-------|
| `domain` | `{ "min": num, "max": num, "zero": bool }` | **Object, not an array.** Zoom/range the value axis. `min`/`max` are **raw data values** — for a percentage field use decimals (`0.6` = 60%); for currency use raw numbers (`1000000` = $1M). |
| `title` | `{ "value": "string", "format": {…} }` | Axis title text. **Set `"value": ""` to remove** a title (e.g. drop a redundant dimension-axis title so long category labels get room to wrap instead of truncating). |
| `scale` | `{ "type": "linear" \| "log" \| "pow" \| "sqrt" \| "symlog" }` | `log` takes optional `base`; `pow` takes `exponent`; `symlog` takes `constant`. **`scale` is distinct from `domain`** — don't put min/max here. |
| `label` | `{ "format": { "angle": num, "format": "string", "fontSize": num, … } }` | Tick-label rotation and number/date format. (Not `tickFormat`.) |
| `grid` | `{ "enabled": bool, "line": { "color", "dash": [n], "opacity", "width" } }` | Gridline visibility/style. |
| `showLabels` / `showTicks` / `showAxisLine` | `bool` | Toggle tick labels, tick marks, the axis line. (Not `showLabel`/`showGridLines`.) |
| `tickCount` | `num` \| `{ "interval": "month", "step": 1 }` | Tick density. |
| `sort` | `{ "field": "string", "order": "ascending" \| "descending" }` | Category-axis sort. |
| `referenceLine` | `{ "enabled": true, "value": num, "label": "string", "line": { "color", "dash": [4,4] } }` | **Native target/threshold/goal line** — see [Reference lines](#reference-lines-trend-lines-moving-averages). |

**"Unpin from Zero"** (the UI checkbox) = `<valueAxis>.axis.domain.zero: false`. Omni pins value axes to zero by default, so a near-constant series (e.g. gross margin ~52–54%) looks dead flat until you set this. For a **horizontal bar** the value axis is `x`, so zoom it with `x.axis.domain` (e.g. `{ "min": 0.50, "max": 0.65, "zero": false }`).

> **For BAR charts, `zero: false` alone does nothing — a bar is anchored at 0 by nature.** To zoom a clustered bar chart (all bars nearly the same length, e.g. sell-through 88–95%), set an **explicit `domain.{min,max}`**; `zero:false` only matters for line/area/point. **Caveat:** a hard-coded `domain` can make bars *vanish* if the underlying values later move outside `[min,max]` — when the data changes (or a filter changes the values), re-fit the domain, or the bars render off-canvas.

### color object — controls stacking and series color

| Pattern | Usage |
|---------|-------|
| `{}` | Single series, auto color |
| `{ "_stack": "group", "field": { "name": "..." } }` | Grouped (side-by-side) — `chartType` `*Grouped` |
| `{ "_stack": "stack", "field": { "name": "..." } }` | Stacked — `chartType` `*Stacked` |
| `{ "_stack": "stack_percentage", "field": { "name": "..." } }` | 100% stacked — `chartType` `*StackedPercentage` |
| `{ "field": { "name": "..." } }` | Color by dimension (no stacking) — e.g. multi-series line/scatter |

> **`_stack` enum is `group` / `stack` / `stack_percentage` / `overlay`.** 100% stacking is **`stack_percentage`**, *not* `"normalize"`.

The `color.field` is the dimension that splits the series; it must also be in `query.pivots` for stacked/grouped charts.

**Custom colors on the `color` object** (all optional; omit to use Omni's curated defaults):

| Property | Shape | Notes |
|----------|-------|-------|
| `values` | `{ "<dimValue>": "#hex", … }` | **Pin specific dimension values to specific colors** (e.g. `{ "Complete": "#1FAE7E", "Cancelled": "#E5484D" }`). |
| `else` | `"#hex"` | Fallback color for values not in `values`. |
| `range` | `["#hex", …]` | Custom palette array. **Only applies when `_scheme: "custom"`.** |
| `_scheme` | `"string"` | Named palette, or `"custom"` to use `range`. |
| `reverse` | `bool` | Reverse the palette direction. |
| `stackSort` | `{ "by": "label" \| "size" \| "sum", "order": "ascending" \| "descending" }` | Order of stacked segments. |
| `ignoreModeledColors` | `bool` | Ignore colors defined on the model field. |

### series array

```json
"series": [
  { "field": { "name": "order_items.total_revenue" }, "yAxis": "y" }
]
```

Per-entry properties:

| Property | Shape | Notes |
|----------|-------|-------|
| `field` | `{ "name": "view.field" }` | The measure to plot. |
| `yAxis` / `xAxis` | `"y"` \| `"y2"` / `"x"` \| `"x2"` | Primary vs secondary axis. Use `y2`/`x2` for a series on a different scale/unit (combo charts). |
| `mark` | `{ "type": "...", "_mark_color": "#hex", "line": {…} }` | Per-series mark (combo charts) **and per-series solid color** — see below. |
| `dataLabel` | `{ "enabled": true, "position": "...", "minValue": num, "useSparseLabelAlgorithm": bool }` | Value labels on points. |
| `title` | `{ "value": "string" }` | **Series legend/tooltip label.** This is the legend label, **not `series[].label`** — there is no `label` property on a series; the renderer reads `series[].title.value`, falling back to the measure's field label when unset. So a series with only `label` silently shows the field label in the legend. |
| `regression` | `{ "enabled": true, "method": "..." }` | Native trend line — see below. |
| `movingAverage` | `{ "enabled": true, "window": {…} }` | Native moving average — see below. |
| `totals` | `{ "enabled": true, … }` | Stacked-total labels (`simpleTotals`). |

> **Per-series solid color is `series[].mark._mark_color` (a hex string), not `series[].color`.** `series[].color` exists but is a per-*layer* dimension-encoding slot that is **ignored on the standard render path** — setting a hex there does nothing. To force one solid color on a series, set `mark._mark_color` and add `manual: true` (the `manual` flag marks the color as user-set so the auto-styler won't overwrite it on the next render).
>
> ```json
> "series": [{ "field": { "name": "order_items.total_revenue" }, "yAxis": "y",
>              "mark": { "type": "bar", "_mark_color": "#1FAE7E" }, "manual": true }]
> ```
>
> For coloring by a **dimension value** instead (e.g. status → color), use `config.color.values` (above), not a per-series color.

### Reference lines, trend lines, moving averages

These are **native cartesian features** — reach for them before modeling extra fields or building separate tiles.

- **Reference line** (target / threshold / goal) — on the **value axis's** `axis` object:
  ```json
  "y": { "axis": { "referenceLine": { "enabled": true, "value": 100000,
                    "label": "Target", "line": { "color": "#888", "dash": [4, 4] } } } }
  ```
- **Regression / trend line** — per series. `method`: `"linear"`, `"log"`, `"exp"`, `"pow"`, `"quad"`, `"poly"`:
  ```json
  "series": [{ "field": { "name": "order_items.total_revenue" }, "yAxis": "y",
               "regression": { "enabled": true, "method": "linear" } }]
  ```
- **Moving average** — per series. `window.type`: `"lagging"` or `"center"`:
  ```json
  "series": [{ "field": { "name": "order_items.total_revenue" }, "yAxis": "y",
               "movingAverage": { "enabled": true, "window": { "period": 7, "type": "lagging" } } }]
  ```

### Dashed / styled lines (e.g. a dotted projection or forecast overlay)

A line/area series mark takes a `line` style object — `dash` makes it dotted. This is the clean way to render a **projection/forecast overlay** as a second, visually-distinct series on the same chart (rather than a separate tile): plot the actual measure as a solid line and the projected measure as a dashed one.

```json
"series": [
  { "field": { "name": "order_items.total_revenue" },     "yAxis": "y",
    "mark": { "type": "line", "line": { "width": 2 } } },
  { "field": { "name": "order_items.projected_revenue" }, "yAxis": "y",
    "mark": { "type": "line", "_mark_color": "#888",
              "line": { "dash": [5, 4], "point": false } } }
]
```

`line` properties: `dash` (`[on, off]` px), `color`, `width`, `opacity`, `interpolate` (e.g. `"monotone"`, `"step"`), `point` (show/hide markers).

**Projection as a ghost *column* (not a line).** The same run-rate calc works on a `barLine`/`column` chart: add the projected measure as a **second bar series** that **overlays** the actual at the same x (both from baseline 0; the ghost peeks above the shorter actual). Draw order = series-array order, so list the projected bar **first** (behind) and the solid actual **second** (front); give the ghost a translucent fill (e.g. 8-digit hex `"#94A3B8A6"` slate to match the gray "projected" convention) so only its run-rate *cap* shows above the actual partial bar.
- **Two same-mark bar series default to STACK — you must force overlay** (classic compiler; on a layer chart they overlay and cannot be stacked without a Measure values fold, see [Layer-compiled cartesian charts](#layer-compiled-cartesian-charts-the-layers-editor)). `behaviors.stackMultiMark:false` is *not* enough: when an axis has ≥2 series of the same stackable mark (bar/area) and no explicit stack, the compiler defaults to `STACK`, so the ghost stacks *on top of* the actual (gray top = actual + projected) instead of overlapping. Set **`config.color._stack: "overlay"`** (enum: `group`/`stack`/`stack_percentage`/`overlay`) — the compiler returns that explicit value before falling through to the same-mark STACK default, and `OVERLAY` skips the stacking-field encodings so both bars draw from zero. Tell-tale of the bug: the dependent axis auto-scales to ~`actual+projected` instead of ~`projected`.
- **Watch the anchor branch.** A run-rate projection table-calc (the `OMNI_OFFSET_MULTI`/`OMNI_FX_ROW`/`COUNT_A` "is-this-the-last-row" pattern) is typically non-null on the **last *two*** rows: the current month gets the projected value, and the **second-to-last** gets its *actual* value as an anchor — necessary so a projection **line** visibly connects from the last complete point. For a **column** overlay that anchor paints an unwanted ghost cap on the prior month. Strip it: the calc's outer `CASE` has the shape `CASE(isLastRow, projection, CASE(isSecondToLast, actual, null))` — replace `operand[2]` (the inner anchor `CASE`) with a `null` literal so only the current month projects.
- A run-rate projection needs a date-extent measure (`max(timestamp)` cast through the session timezone, like `last_order_date`/`last_session_date`) **on the topic's own base view** — it can't reach a `max-date` measure on a view the topic doesn't join. **Select that measure into the query and hide it** (`resultConfig.hiddenColumns`), keeping it out of `visConfig.fields`/`series` so it isn't plotted — then the calc references a *selected* field. **Do NOT hand-set `allow_refs_to_unselected_fields:true`** to reference it while unselected — it's an **AI-SQL-gen-only marker**, not a hand-authoring knob: the SQL runs, but the calc shows `#ERROR — No such field … in query` and is **uneditable in the workbook formula editor** (the observable tell — set it, then open the tile's formula editor). Selecting the date **measure** does *not* change grain (it's an aggregate, not a `GROUP BY` key — confirm row count is unchanged); selecting a **dimension** or a new-join field *would* change grain/fan out, so reframe carefully.

### Small multiples (faceting)

Split one chart into per-category panels with `config.facet`:

```json
"facet": { "column": { "field": { "name": "products.category" } }, "wrap": true, "wrapColumns": 3 }
```

Use `column` and/or `row`; `wrap: true` + `wrapColumns` controls trellis wrapping. Scales/axes default to shared.

## Layer-compiled cartesian charts (the layers editor)

Omni renders a cartesian config through one of two compilers, and the config decides which:

| | Classic compiler | Layer compiler ("layers", the new X/Y chart builder) |
|---|---|---|
| Selected by | `behaviors.useLayerCompiler` absent or `false` | `behaviors.useLayerCompiler: true` |
| Editor shown in the workbook | **X-Axis / Left-Axis / Right-Axis / Color and legend** panel | **Setup / Style** tabs with a "New X/Y chart builder" banner; each measure is a layer with its own **Mark**, **Color** and **Label** |
| Who writes it | Every recipe in this file unless it says otherwise; any config saved before layers | Every X/Y chart created in the UI since layers went on; the "Test the new chart editor" and "Upgrade charts" actions |

Both compilers read the same envelope (`visConfig.chartType` / `fields` / `visConfig.visType: "basic"` / `config`), the same `configType: "cartesian"`, `_dependentAxis`, `x`, `y` / `y2`, `series[]` and `tooltip`. What differs is where the encodings live and how layers combine. Layers are documented at [docs.omni.co/visualize-present/visualizations/layers](https://docs.omni.co/visualize-present/visualizations/layers).

**A config without the flag stays on the classic compiler.** Nothing about the GA of layers changes what an API-created tile gets: a cartesian config sent through `v2-create` or a draft patch opens in the classic editor and renders through the classic compiler until `behaviors.useLayerCompiler: true` is in its config. Confirm which one a tile is on by opening its workbook tab, clicking **Options** above the chart, and looking for the banner, or by reading the tile back and checking `behaviors.useLayerCompiler`.

### What the layer editor writes

A chart built in the layers editor reads back in this shape (a bar colored by a dimension, stacked):

```json
"config": {
  "_dependentAxis": "y",
  "behaviors": { "stackMultiMark": false, "useLayerCompiler": true },
  "configType": "cartesian",
  "x": { "field": { "name": "order_items.created_at[month]" }, "axis": { "label": { "autoLayout": true } } },
  "series": [
    { "field": { "name": "order_items.total_revenue" }, "yAxis": "y",
      "mark": { "type": "bar" },
      "color": { "field": { "name": "order_items.status" }, "_stack": "stack" } }
  ],
  "colorFields": { "order_items.status": { "values": { "Complete": "#296228" } } },
  "tooltip": [ { "field": { "name": "order_items.created_at[month]" } },
               { "field": { "name": "order_items.status" } },
               { "field": { "name": "order_items.total_revenue" } } ],
  "version": 0,
  "y2": null
}
```

Differences from the classic shape, each confirmed by building the chart in the UI and reading the tile back with `omni documents v2-get`:

| Where | Layer compiler | Classic compiler |
|---|---|---|
| Mark | `series[].mark.type` on every layer; the editor writes no root `mark` | Root `mark.type`, with `series[].mark` only for combo overrides |
| Color by a dimension | `series[].color.field` on the layer that uses it; the dimension is still in `query.pivots` | Root `color.field` |
| Stacking | `series[].color._stack` on the layer (`stack` / `group` / `overlay` / `stack_percentage`). A bar layer with a color field and no `_stack` rendered stacked; a layer the editor had set to **Overlay** keeps `"_stack": "overlay"` | Root `color._stack` |
| Solid layer color | `series[].mark._mark_color` + `series[].manual: true` — the same keys as classic; the layer's **Color: Single color** swatch writes exactly this | Same |
| Per-value colors | Root **`colorFields`**: `{ "<view.field>": { "values": { "<value>": "#hex" } } }`, keyed by the color field's name, so every layer colored by that field shares it. The layer keeps only `color.field` and `color._stack` | `color.values` on the root `color` |
| Data labels | `series[].dataLabel: { "enabled": true, "field": { "name": "<the layer's measure>" }, "useSparseLabelAlgorithm": true }` | `series[].dataLabel` |
| Zero line aligned across the two value axes (**Align with other axis** in the axis options) | Root **`alignAxisZeros: true`**; needs a series on `y` and one on `y2` | Not available |
| Legend label | `series[].title.value` | Same |
| Axis styling | Under `<axis>.axis` as before (`title`, `domain`, `label`, …); `y2.axis.domain` and `y.axis.title` both took effect on a layer chart | Same |
| Right axis | `series[].yAxis: "y2"` (or `xAxis: "x2"` for horizontal bars) | Same |
| `chartType` | **Not maintained by the layer editor.** A tab auto-charted as a line and then switched to stacked bars still reads back `chartType: "lineColor"`. Read the layers from `series[].mark.type`; when you author one, still set `chartType` to the matching enum value | Tracks the chart |
| Written but not required | `x.axis.label.autoLayout: true`, `y2: null`, `version: 0`, `series[].manual: true` on layers added through the editor. A hand-written config without them rendered the same | — |

### Measure values: several measures in one layer

Layers do **not** stack across layers. Two bar layers on the same axis draw over each other (the taller one hides the shorter), and a root `color._stack: "stack"` does not change that. To stack or group several measures, put them in **one** layer through the Measure values fold, which is what the editor does when it draws measures together and what the upgrade actions do to a classic multi-measure chart:

```json
"config": {
  "_dependentAxis": "y",
  "behaviors": { "useLayerCompiler": true },
  "configType": "cartesian",
  "x": { "field": { "name": "order_items.created_at[month]" } },
  "foldedFields": [
    { "field": { "name": "order_items.total_revenue" } },
    { "field": { "name": "order_items.total_margin" } }
  ],
  "series": [
    { "field": { "name": "omni__field_value" }, "yAxis": "y",
      "mark": { "type": "bar" },
      "color": { "field": { "name": "omni__field_name" }, "_stack": "stack",
                 "axis": { "title": { "value": "Series" } } } }
  ],
  "tooltip": [ { "field": { "name": "order_items.created_at[month]" } },
               { "field": { "name": "order_items.total_revenue" } },
               { "field": { "name": "order_items.total_margin" } } ]
}
```

- `foldedFields` (root) lists the measures the layer draws, in legend order. They stay in `query.fields` and `visConfig.fields` as usual.
- The layer's `field.name` is the synthetic **`omni__field_value`** ("Measure values"); its `color.field.name` is **`omni__field_name`** ("Measure names"). `{ "name": … }` is enough — the full field objects the upgrade dialog writes (`label`, `isMeasure`, …) are not needed.
- `color._stack` on this layer is the stacking of the measures: `stack`, `group`, `overlay` or `stack_percentage`.
- A measure that should be its own layer (a line on the right axis beside stacked bars) is a separate `series` entry and must be left out of `foldedFields`.

### Creating a layer-compiled chart through the API

Take any cartesian recipe in this file, add `"useLayerCompiler": true` to `behaviors`, put the per-layer encodings on the series, and fold measures that share an axis and a mark. Bars on the left axis, a line on the right, zeros aligned:

```json
"visConfig": {
  "chartType": "barLine",
  "fields": ["order_items.created_at[month]", "order_items.total_revenue", "order_items.count"],
  "version": 0,
  "visConfig": {
    "visType": "basic",
    "config": {
      "x": { "field": { "name": "order_items.created_at[month]" } },
      "series": [
        { "field": { "name": "order_items.total_revenue" }, "yAxis": "y",  "mark": { "type": "bar" } },
        { "field": { "name": "order_items.count" },         "yAxis": "y2", "mark": { "type": "line" } }
      ],
      "tooltip": [
        { "field": { "name": "order_items.created_at[month]" } },
        { "field": { "name": "order_items.total_revenue" } },
        { "field": { "name": "order_items.count" } }
      ],
      "alignAxisZeros": true,
      "behaviors": { "stackMultiMark": false, "useLayerCompiler": true },
      "configType": "cartesian",
      "_dependentAxis": "y"
    }
  }
}
```

This tile opened in the layers editor and rendered as authored. Layer-compiled tiles render in deliveries too: a dashboard of layer charts downloaded as PNG (`omni dashboards download`) drew every tile as the workbook did. Read the tile back afterwards and confirm `behaviors.useLayerCompiler` is still `true` and the editor is the layers one; see the fallback below.

### Moving a tile between the two compilers through the API

Both directions are a draft patch of the tile's config, in place, keeping its key, filter maps and layout. The UI's own actions (the tab's *Test the new chart editor*, which copies the tab, and the dashboard's *Upgrade charts to the new chart editor* and the tab's *Leave the new chart editor*, which change the tile in place) store exactly the shapes below, so a tile you convert by hand is indistinguishable from one the user converted.

**Classic to layers.** Add `behaviors.useLayerCompiler: true`. That alone is enough when every measure has its own mark or axis, and when the chart is colored by a dimension through the root `color` (a classic `columnStacked` config with the flag added rendered stacked by its dimension as before: the chart-wide color is applied to the layer). The one case the flag alone gets wrong is two or more measures of the same mark on one axis: they stacked under the classic compiler and now overlay. Fold them into a Measure values layer with `color._stack: "stack"` (the shape above); that is also what the UI's upgrade writes for such a chart.

**Layers to classic.** Removing the flag is not enough when the chart has a Measure values layer: a fold shape (`foldedFields` plus an `omni__field_value` series) with the flag absent or `false` renders **"No chart available"**, because the classic compiler does not read the synthetic fields. Unfold it yourself, which is what the UI writes when a chart leaves layers: one `series[]` entry per folded measure, each with the layer's `mark` and axis; the fold's `color` minus its `field` moved to the root `color` (so `_stack` and the legend title survive); the shared mark type on the root `mark`; `foldedFields` and `useLayerCompiler` removed. Per-layer encodings every layer shared (a color field, a size field, a mark type) move to the root; ones that differ stay on their series, where the classic compiler reads only the mark.

```bash
# the tile as it is, from v2-get or v2-get-draft, with only the config changed
omni documents v2-patch-draft <identifier> --body @to-layers.json   # a body like:
# { "summary": "move Revenue vs orders to the layers editor",
#   "queryPresentations": { "data": { "3": { …the tile with behaviors.useLayerCompiler: true… } }, "order": [ …unchanged… ] } }
```

Then `v2-get-draft` to confirm the config came back as sent, and `v2-publish-draft`.

### The layers editor's words, and the keys they set

When a user asks in the editor's own terms, this is what to write. Every row was read back after the editor set it, or written and seen in the editor.

| What the user says (layers editor label) | Where it lives in the config |
|---|---|
| "Left axis" / "Right axis" (the **Y-axes** section) | `series[].yAxis: "y"` / `"y2"`; on a horizontal chart `xAxis: "x"` / `"x2"` |
| "Add a field" to an axis, a layer's **Mark** (Bar / Line / Area / Scatter) | A new `series[]` entry; `series[].mark.type: "bar"` / `"line"` / `"area"` / `"point"` |
| The stacking dropdown beside Mark: **Stacked / Grouped / Overlay / Stacked %** | `series[].color._stack: "stack"` / `"group"` / `"overlay"` / `"stack_percentage"` |
| **Color: Single color** and its swatch | `series[].mark._mark_color` + `series[].manual: true` |
| **Color:** a field | `series[].color.field`; the field is also in `query.pivots` when it is a dimension |
| **Color options → Value mapping** (a swatch per value), **Auto-apply** palette | `colorFields["<field>"].values`, `colorFields["<field>"]._scheme` |
| **Label → Add labels** on a layer | `series[].dataLabel: { enabled: true, field, useSparseLabelAlgorithm: true }` |
| Labels on "All layers" | Root `dataLabel`; a layer with its own `dataLabel` opts out |
| **Measure values** (the token, "Measure values • N") and the **Measure values** section listing its fields; "Remove from measure values" | `foldedFields` (the list) and a series whose `field.name` is `omni__field_value`; removing a field is removing it from `foldedFields` |
| **Measure names** (as a color, a facet, or the X axis) | A field named `omni__field_name` in `series[].color.field`, `facet.column.field` / `facet.row.field`, or `x.field` |
| **Small multiples → Columns / Rows** | `facet.column.field` / `facet.row.field`, with `wrap` and `wrapColumns` |
| **Axis options** (the gear beside Left axis / Right axis): **Title**, **Type**, **Domain Minimum / Maximum**, **Unpin from Zero**, **Scale**, **Zero line → Align with other axis**; its **Labels**, **Reference Line**, **Grid** tabs | `y.axis.title.value`, `y.axis._type`, `y.axis.domain.{min,max}`, `y.axis.domain.zero: false`, `y.axis.scale`, root `alignAxisZeros: true`; `y.axis.label`, `y.axis.referenceLine`, `y.axis.grid` (same under `y2`, or `x` / `x2` horizontal) |
| **Style tab → Default chart palette**, **Reverse colors** | Fieldless root `color._scheme`, `color.reverse` |
| **Style tab → Legends**: **Max width**, per-legend **Title**, **Position**, **Labels** (Truncate / Wrap), **Max items** | `legendSlots.<position>.size`; for a field's legend `colorFields["<field>"].axis.title.value`, `.legendPosition`, `.labelOverflow`, `.maxItems`; for the series legend the same keys on the fieldless root `color` |
| **Simple totals** (in a layer's Label options); the button then reads **+ Add segment labels** | `series[].totals: { enabled: true }` on the stacked layer; the segment labels are that layer's `dataLabel` |
| **Sort stack by: Label / Segment value / Overall sum / Unsorted**, **Sort order** | `series[].color.stackSort: { by: "label" / "size" / "sum" / "unsorted", order: "ascending" / "descending" }` |
| **Axis options → Sort order: Automatic / Ascending / Descending** on a text X axis | `x.axis.sort: { field, order: "ascending" / "descending" }`; Automatic is no `sort` (query order) |
| **Size: Fixed size** on a scatter layer | No `series[].size`; the point size is `mark.point.size` |
| **Axes options (the menu on "Y-axes") → All values: Mark / Color / Size / Label** | The same key written onto every `series[]` entry (or the root broadcast key, which the parser copies onto each layer) |
| **Axes options → Swap left and right**, **Display order: Left values on top / Right values on top** | Every `yAxis` flipped; the order of `series[]`: layers draw in array order, so the last entry is on top |
| **Measure values** section: drag a measure in or out, reorder | `foldedFields` membership and order (also the legend order and, on a Measure names axis or facet, the panel order) |
| **Field properties…** on a layer's field (title, format) | `series[].title.value`; number formats stay on the field in the model or the query |
| Trend line, moving average | `series[].regression`, `series[].movingAverage` |
| **Auto-charting on / off** | `automaticVis: true` / `false` on the presentation; the layers editor turns it off once a layer is edited |
| "Test the new chart editor…" / "Upgrade charts to the new chart editor…" / "Leave the new chart editor…" | The compiler moves in [Moving a tile between the two compilers through the API](#moving-a-tile-between-the-two-compilers-through-the-api): the first copies the tab, the other two change the tile in place |

### What a layer can carry

The layer compiler parses a config against a strict schema: every key below is accepted, and a key that is not listed anywhere in it (at any depth) makes the whole config fall back to the classic editor and compiler, silently. Tested on three such keys: a hex string in `series[].color`, `series[].label`, and `domain` placed directly on `y` instead of under `y.axis`. A value outside an enum does the same: `legendPosition` takes `top`, `bottom`, `left`, `right` or `none`, and `"hidden"` sent the tile to classic. The tell-tale in every case was the same: the tile opens in the X-Axis / Left-Axis / Right-Axis editor instead of Setup / Style. Read the chart in view mode and you cannot tell; the legend and marks still draw.

| Level | Keys the layer compiler accepts |
|---|---|
| Config root | `configType`, `_dependentAxis`, `x`, `x2`, `y`, `y2`, `series`, `tooltip`, `behaviors` (`useLayerCompiler`, `stackMultiMark`), `alignAxisZeros`, `colorFields`, `foldedFields`, `facet`, `dataLabel` (chart-wide "All layers" label), `legendSlots`, `mark` and `color` and `size` (chart-wide broadcasts, see below), `version` |
| Independent axis (`x` on a vertical chart, `y` on a horizontal one) | `field`, `axis`, `manual`, `multipleDimensions` |
| Dependent axis (`y` / `y2`, or `x` / `x2` horizontal) | `axis`, `color`, `manual`, `simpleTotals` (read by the classic compiler only; layers use `series[].totals`) |
| `axis` (either kind) | `title`, `domain`, `scale`, `label`, `grid`, `showLabels`, `showTicks`, `showAxisLine`, `tickCount`, `sort`, `referenceLine`, `_title`, `_type` |
| `series[]` (one layer) | `field`, `yAxis` / `xAxis`, `mark`, `color`, `size`, `dataLabel`, `title`, `totals`, `regression`, `movingAverage`, `manual` |
| `series[].mark` | `type` plus one style object named after it: `bar: { cornerRadius, opacity }`, `line: { color, dash, interpolate, opacity, point, width }`, `area: { …line keys…, line }`, `point: { filled, opacity, shape, size, width }`; and `_mark_color` |
| `series[].color` | `field`, `_stack`, `stackSort`, `manual` stay on the layer; `values`, `else`, `_scheme`, `range`, `reverse`, `axis` (legend title), `legendPosition`, `labelOverflow`, `maxItems`, `showTitle`, `scaleDomain`, `ignoreModeledColors` are field-level and belong in `colorFields["<field>"]` (inline on the series still parses: the first layer in paint order with them wins for that field) |
| `series[].size` (point layers) | `field`, `axis.title.value`, `legendPosition`, `labelOverflow`, `maxItems`, `showTitle`, `manual` |
| `series[].dataLabel` and root `dataLabel` | `enabled`, `field`, `format`, `position`, `minValue`, `maxValue`, `useSparseLabelAlgorithm`, `color`, `font`, `fontSize`, `fontStyle`, `fontWeight` |
| `facet` | `column` / `row` (`field`, `label`, `sort`, `title`, `manual`), `scaleXAxes` / `scaleYAxes` (`shared` / `independent`), `showXAxis` / `showYAxis` (`every` / `once`), `wrap`, `wrapColumns` |

Chart-wide `mark`, `color` (with a `field`), `size` and `dataLabel` are **broadcasts**: the parser copies each onto every layer that lacks its own and then reads only the layers. A fieldless root `color` is different: it holds the series-identity legend's position and title and the chart palette, and stays.

### Layer shapes, each rendered as written

Every row was written through the API with `behaviors.useLayerCompiler: true`, read back unchanged, and rendered as described. The field names are from the sample dataset; `FN` and `FV` stand for `omni__field_name` and `omni__field_value`.

| Shape | The config that does it |
|---|---|
| Three layers across two axes (two lines on `y`, a bar on `y2`) | `series: [{sales, y, line}, {margin, y, line}, {count, y2, bar}]`; no fold needed when the layers should not stack |
| Measure names on the X axis, one bar per measure, no dimension in the query | `x: { field: { name: FN } }`, `foldedFields: [sales, margin, count]`, `series: [{ field: FV, mark bar, color: { field: FN } }]`; the query holds only the measures |
| Small multiples, one panel per measure | `facet: { column: { field: { name: FN } }, wrap: true, wrapColumns: 2 }`, `foldedFields: [sales, margin]`, `series: [{ field: FV, mark bar }]` |
| Small multiples by a real dimension with stacked measures in each panel | `facet.column.field` = the dimension (also in `query.pivots`), plus the stacked Measure values layer |
| Scatter sized by a measure beside a line | `{ field: sales, mark: { type: "point" }, size: { field: { name: count } } }` and `{ field: margin, mark: { type: "line" } }`; the size legend appears beside the series legend |
| Labels on every layer except one | Root `dataLabel: { enabled: true, useSparseLabelAlgorithm: true }` and `dataLabel: { enabled: false }` on the layer to exempt; a layer with any `dataLabel` of its own ignores the root one |
| Moving average on one layer, trend line on another | `series[].movingAverage: { enabled: true, window: { period: 3, type: "lagging" } }` on the bar layer; `series[].regression: { enabled: true, method: "linear" }` on the line layer |
| Stacked measures with a total above each bar | The Measure values layer with `color._stack: "stack"` and `totals: { enabled: true }` on that layer |
| 100% stacked measures | The Measure values layer with `color._stack: "stack_percentage"`; the axis reads 0 to 100% |
| Horizontal grouped measures per category | `_dependentAxis: "x"`, `y: { field: { name: status } }`, the Measure values layer with `xAxis: "x"` and `color._stack: "group"` |
| Grouped by a dimension, largest group first | `series[].color: { field: status, _stack: "group", stackSort: { by: "sum", order: "descending" } }` |
| Pinned colors, a fallback color, a legend title | `colorFields: { "<status>": { values: { "Complete": "#1FAE7E", "Cancelled": "#E5484D" }, else: "#C8C8C8" } }` with `series[].color: { field: status, _stack: "stack", axis: { title: { value: "Order status" } } }` |
| Legend under the chart | `colorFields["<status>"].legendPosition: "bottom"` with root `legendSlots: { bottom: { size: 0.25 } }` (the slot's share of the tile, 0 to 1) |
| Mark styling per layer | `mark: { type: "area", area: { opacity: 0.3, line: true, interpolate: "monotone" } }`, `mark: { type: "line", line: { dash: [4, 4], point: true, width: 3 } }`, `mark: { type: "bar", bar: { cornerRadius: 6, opacity: 0.6 } }` |
| Two color fields, two legends | A Measure values layer colored by `FN` plus a line layer colored by a real dimension (`series[].color.field`); each field gets its own legend |
| Chart-wide mark with one exception | Root `mark: { type: "line" }` and `mark: { type: "bar" }` on the one layer that differs |
| Legend and stack order of folded measures | The order of `foldedFields`: list the measure that should sit at the bottom of the stack first |
| A Measure values layer colored by a real dimension | `series[].color.field` = the dimension on the `omni__field_value` layer: each segment is the measures added together for that value, so the measures cannot be told apart. Color by `omni__field_name` to see the measures; split by the dimension with a facet or a second layer instead |
| Small multiples on two fields | `facet: { row: { field: { name: status } }, column: { field: { name: FN } } }` gives a grid, rows per status and a column per folded measure |
| Which layer draws on top | `series[]` order: the last entry paints last. Bars listed after a line cover it; a line listed after bars runs over them |
| A fold layer and a plain layer on one axis | Allowed: `[{ field: FV, bar, stacked }, { field: count, line, yAxis: "y" }]`; they share the axis scale |
| Target line on the value axis | `y: { axis: { referenceLine: { enabled: true, value: 450000, label: "Target", line: { color: "#888888", dash: [4, 4] } } } }`, as on classic |
| Bars shaded by a measure (gradient) | `series[].color: { field: { name: count } }` with `colorFields["<count>"]: { scaleDomain: { min: 8000, max: 12000 } }`; the legend is a gradient bar over that range |
| Two scatter layers sized by the same measure | `size: { field: { name: count } }` on both point layers; one size legend |
| Small multiples with their own value scales | `facet: { column: …, scaleYAxes: "independent" }` (`showYAxis: "once"` / `"every"` picks how often the axis is drawn) |
| Category axis ordered by the measure | `x: { field: { name: status }, axis: { sort: { field: "<sales>", order: "descending" } } }` |
| Hollow diamond markers | `mark: { type: "point", point: { shape: "diamond", filled: false, size: 150 } }` (shapes: `circle`, `square`, `diamond`, …) |
| A capped, wrapped, untitled legend | `colorFields["<status>"]: { maxItems: 3, labelOverflow: "wrap", showTitle: false }`; the legend shows three entries and a "+ N more" row |
| Formatted labels inside the bar tops | Root `dataLabel: { enabled: true, format: "$#,##0,\"K\"", position: "inside_end", fontSize: 10 }` |
| No series legend on a multi-layer chart | Fieldless root `color: { legendPosition: "none" }`; the fieldless root `color` is where the series-identity legend and the chart palette live |

Two results that are not errors but are worth knowing:

- **A dimension in `query.pivots` that no layer encodes is rolled up** (one bar per month, summed across the pivot) rather than drawn once per pivot value. The classic compiler drew the same chart for that config.
- **Layers on one axis share its scale, so mixed stack modes squash.** A `stack_percentage` layer and a `stack` layer on the same axis render against one domain and the percent layer collapses to a sliver at the bottom. Keep one stack mode per axis.

### A layer that uses fewer dimensions than the query ("smart aggregation")

A layer draws the rows the query returns; it never re-aggregates them. When the query groups by a dimension that a layer does not encode (not on its axis, color, size or facet), the layer needs a row per remaining dimension value, and the warehouse has to supply it: add a subtotal on the **last dimension the layer keeps** to `query.column_totals`, keyed by field name:

```json
"query": {
  "fields": ["order_items.created_at[month]", "order_items.status", "order_items.total_revenue"],
  "column_totals": { "order_items.created_at[month]": { "type": "aggregation" } },
  …
}
```

The layer then reads the month subtotal rows and draws one value per month (the editor shows a **TOTAL** badge on such a layer, and writes exactly this entry when a color field is removed from a layer while the dimension stays in the query). Without the entry the same line layer zigzags through every status row. This is per query, so it also feeds the table under the chart. Subtotals nest from the right, so the dimensions a layer keeps must be a prefix of the query's grouped dimensions. A pivoted dimension that no layer encodes needs nothing: it rolled up on its own in every test.

### Gotchas that change on a layer chart

| Classic rule in this file | On a layer-compiled chart |
|---|---|
| `series[].color: "#hex"` is ignored; `series[].label` is ignored; `domain` directly on `y` is ignored | **Worse than ignored: any key the layer schema does not declare drops the tile back to the classic editor and compiler**, flag and all, with no error; the chart still draws through the classic path. All three were tested. When a layer chart opens in the X-Axis / Left-Axis / Right-Axis editor, remove the undeclared key (see [What a layer can carry](#what-a-layer-can-carry)) and read back. A solid layer color is `mark._mark_color` + `manual: true`; per-value colors go in `colorFields`; the legend label is `title.value`; axis styling goes under `axis` |
| Two same-mark bar series default to STACK; set `color._stack: "overlay"` to overlay | Layers never stack across layers: two bar layers on one axis **overlay** whatever `_stack` says at the root or on the layers. To stack them, fold them into one Measure values layer |
| Stack dimension goes in root `color.field` + `query.pivots` | The pivot is still required; the color field lives on the layer (`series[].color.field`). A root `color.field` still works when you move a classic config over |
| `series[].mark._mark_color` + `manual: true` | Still the per-layer solid color (and what the editor writes) |
| `series[].title.value` for the legend label | Still works |
| Axis styling under `<axis>.axis` | Still works |
| `_dependentAxis`, `yAxis` / `xAxis`, `y2` for the right axis | Unchanged |
| A query dimension the chart does not encode is simply ignored | A layer that omits a grouped dimension draws every row (a line zigzags) unless the query carries a `column_totals` subtotal on the last dimension the layer keeps |

## Config Object: KPI

KPI tiles use `chartType: "kpi"`, `visType: "omni-kpi"`, and **no `configType`**.

> **Pick the right KPI mechanism — `omni-kpi` vs a markdown card. Both are legitimate; choose by what the card needs, and configure whichever you pick *cleanly*.**
>
> **Native `omni-kpi` is the better default for a standard KPI card** — value + change-vs-prior + sparkline, and especially **gauges**: its comparison `swapColors`/`colorPositive`/`colorNegative` and its **`progress`** (gauge) section are first-class. (Markdown can do the lower-is-better swap too, via `swap-colors` — see *Reach for a markdown card* below; native's real edge is the built-in `progress` gauge and not templating the layout.) To make native `omni-kpi` look clean (config choices, not viz limitations):
> - **Drop the tile-title child** — give the card's `containers` stack only the `{as:"chart"}` child (no `{as:"metadata", format:"name"}`), or the card shows its name **twice** (tile title + the number's own `label`).
> - **Set `descriptionBefore`/`descriptionAfter` to `""`** (not absent) on the number/comparison sections — an *absent* description renders the literal word **`undefined`**.
> - Size the row generously (`h≈26–28`) so the value + comparison + sparkline sections don't clip.
>
> **Reach for a markdown card** ([markdown-tiles.md](markdown-tiles.md) → *Worked KPI card*) when you need what the KPI sections can't express: **value-level conditional colour** (recolour the *number* by threshold via a `color_class` calc + `<style>`), a **bespoke layout** (a 3-up percentile card, an inline-bar table), or **exact responsive `clamp(…cqw…)` typography**. Markdown can do the change arrow too — a markdown `<ChangeArrow>` supports the lower-is-better swap via **`swap-colors="true"`** (kebab-case — the camelCase `swapColors` is silently stripped by the sanitizer; see [markdown-tiles.md](markdown-tiles.md) → *kebab-case attributes*), and you can pair it with a `color_class` value for threshold colour, which native KPI can't. So markdown loses none of the status-card capability; the native-KPI advantage is mainly the built-in `progress` gauge and not having to template the layout.
>
> **⚠️ Don't mix the two mechanisms in one KPI row.** A native `omni-kpi` tile and a markdown card render with **different label placement, typography, vertical alignment, and comparison style** — side by side in the same band one card looks visibly off (e.g. a native card shows no uppercase label and a pill-style delta while its markdown neighbours show a top label + sparkline). **Pick one mechanism for the whole row.** If the row is markdown (for the bespoke card look), keep the status cards markdown too and do their green-on-decrease with the direction calc — don't drop a single native KPI in for its `swapColors`.
>
> A KPI **comparison** section's `comparison` (and a **progress** section's `comparison`) is a *full* value-field `{ row, field:{name,pivotMap}, label:{value} }` — a bare `{ "row": "_second" }` persists but crashes at render (see the value-field rule below).

| Field | Required | Description |
|-------|----------|-------------|
| `alignment` | No | Horizontal: `"left"`, `"center"`, `"right"` |
| `verticalAlignment` | No | Vertical: `"top"`, `"center"`, `"bottom"` |
| `markdownConfig` | Yes | Array of KPI section entries |

Each `markdownConfig` entry is `{ id, type, config, lastModified? }`. **`type`** is one of `number` / `comparison` / `sparkline` / `progress` / `text` / `image`, and `config` varies by type (camelCase fields). This is the **stable, intended way to get a sparkline, a comparison delta, or a progress gauge in a tile** — the KPI renderer compiles these sections into its internal components, so you configure them here rather than hand-authoring component tags into a markdown tile (a markdown tile supports only `<Sparkline>`/`<ChangeArrow>` — see [markdown-tiles.md](markdown-tiles.md)).

A value-bearing field is `{ row, field: { name, pivotMap: {} }, label: { value } }` where `row` ∈ `_first | _second | _second_to_last | _last | _totals.0`.

> **⚠️ The `sparkline` section's `field` must OMIT `row`** — it plots *all* rows, so its field is a plain `{ field: { name, pivotMap }, label }` (no `row`). If you copy a `number`/`comparison` field (which *do* carry `row`) into a sparkline, the compiler prefixes the row to the field reference (`_first.view.metric`), which doesn't resolve per-row — **every point reads as 0 and the sparkline renders as a flat line** (no error). `number`/`comparison`/`progress` need `row`; **sparkline must not have it.**

| `type` | `config` fields |
|---|---|
| `number` | `field` (value field), `descriptionBefore?` |
| `comparison` | `field`, `comparison` (the prior value field), `comparisonType` (`number` / `number_percent` / `percent`), **`colorPositive`**, **`colorNegative`**, **`swapColors?`** (true = "lower is better"), `decimals?`, `descriptionBefore?` / `descriptionAfter?` |
| `sparkline` | `field`, `color`, `type` (`line` / `bar` / `area`), `reverse` (bool), `showAxis` (bool), `width?` / `height?` |
| `progress` | `field`, `comparison` (drives `max`), `comparisonType`, `color`, `type` (`bar` / `circle`), `decimals?`, `descriptionBefore?` / `descriptionAfter?` |
| `text` | `text` |
| `image` | `url`, `width?` / `height?` |

Top-level `KpiConfig` also takes `fontLabelSize?` / `fontBodySize?` / `fontKPISize?` and `dynamicFontSize?` (opt into container-query sizing of the big number) alongside `alignment` / `verticalAlignment` / `markdownConfig`.

> The `comparison`/`progress` `field`/`comparison` objects nest a `SummaryValueConfig` (the same `{ field, label, … }` a number uses) plus `row`; the **exact nesting is easiest to get right by reading back an existing KPI tile** (`omni documents v2-get`) and reusing it. The colors here (`colorPositive`/`colorNegative`/`swapColors`) are the configuration-level way to recolor a delta **in a native KPI tile**; for a markdown *card*, the equivalent is the kebab `swap-colors` attribute (see [markdown-tiles.md](markdown-tiles.md)).

> **⚠️ A malformed `markdownConfig` entry PERSISTS on write but CRASHES at render — the API won't catch it.** Two signatures, both from an incomplete value-field:
> - **`Cannot read properties of undefined (reading 'name')`** — a `comparison` entry whose `comparison` (or `field`) is a bare `{ "row": "_second" }` with no `field: { name, pivotMap }`. The renderer reads `entry.config.comparison.field.name` → crash. The `comparison` value is a **full value-field**, not just a row pointer.
> - **`Cannot read properties of undefined (reading 'row')`** — a `progress` entry with **no `comparison`** (the bar's max). The renderer reads `entry.config.comparison.row` and crashes. Supply a `comparison` value-field when the query has a field for the bar's maximum (a target, a total). When it does not, leave `progress` out and show the value another way.
>
> **Every `markdownConfig` entry's `field` (and a `comparison`'s `comparison`) must be the complete `{ row, field: { name, pivotMap: {} }, label: { value } }`** — omitting `row`, `field.name`, or the wrapper crashes the tile. A complete card that renders (value, sparkline, and change versus the prior period; for "lower is better", add `"swapColors": true` to the comparison):
>
> ```jsonc
> "markdownConfig": [
>   { "id": "spark", "type": "sparkline",
>     "config": { "field": { "row": "_first", "field": { "name": "v.metric", "pivotMap": {} }, "label": { "value": "Metric" } },
>                 "color": "#7C3AED", "type": "line", "showAxis": false } },
>   { "id": "num", "type": "number",
>     "config": { "field": { "row": "_first", "field": { "name": "v.metric", "pivotMap": {} }, "label": { "value": "Metric" } } } },
>   { "id": "cmp", "type": "comparison",
>     "config": { "field":      { "row": "_first",  "field": { "name": "v.metric", "pivotMap": {} }, "label": { "value": "" } },
>                 "comparison": { "row": "_second", "field": { "name": "v.metric", "pivotMap": {} }, "label": { "value": "vs prior" } },
>                 "comparisonType": "percent", "colorPositive": "#1FAE7E", "colorNegative": "#E5484D" } }
> ]
> ```
>
> **`_second`/comparison/sparkline need ≥2 rows** — a single-row **snapshot** query (point-in-time, `limit 1`, no time dimension) has no prior row, so use **`number` entries only** there; sparkline/comparison belong on a trend query (sorted desc so `_first` = latest, `_second` = prior).

### Known-good native KPI tile (verified pattern + caveat checklist)

A complete, **render-verified** status KPI — label + value + change-vs-prior (auto-computed %, green-on-decrease) + trend sparkline. Copy it and swap the measure/topic:

```jsonc
// queryPresentations.data["<key>"]
{
  "name": "Return Rate", "type": "query", "topicName": "operations_orders",
  "prefersChart": true, "automaticVis": false,
  "visConfig": { "chartType": "kpi", "fields": ["ecomm__order_items.created_at[month]", "ecomm__order_items.return_rate"], "version": 0,
    "visConfig": { "visType": "omni-kpi", "config": {
      "alignment": "left", "verticalAlignment": "top", "dynamicFontSize": true,
      "markdownConfig": [
        { "id": "num", "type": "number",
          "config": { "field": { "row": "_first", "field": { "name": "ecomm__order_items.return_rate", "pivotMap": {} }, "label": { "value": "Return Rate" } }, "descriptionBefore": "" } },
        { "id": "cmp", "type": "comparison",
          "config": { "field":      { "row": "_first",  "field": { "name": "ecomm__order_items.return_rate", "pivotMap": {} }, "label": { "value": "" } },
                      "comparison": { "row": "_second", "field": { "name": "ecomm__order_items.return_rate", "pivotMap": {} }, "label": { "value": "" } },
                      "comparisonType": "percent", "decimals": 1, "colorPositive": "#1FAE7E", "colorNegative": "#DC2626",
                      "swapColors": true, "descriptionBefore": "", "descriptionAfter": " vs prior mo" } },
        { "id": "spark", "type": "sparkline",
          "config": { "field": { "field": { "name": "ecomm__order_items.return_rate", "pivotMap": {} }, "label": { "value": "" } },
                      "color": "#F59E0B", "type": "line", "width": "360", "height": "64", "reverse": true, "showAxis": false } }
      ] } } },
  "query": { "table": "ecomm__order_items", "fields": ["ecomm__order_items.created_at[month]", "ecomm__order_items.return_rate"],
    "sorts": [{ "column_name": "ecomm__order_items.created_at[month]", "sort_descending": true }],
    "filters": {}, "limit": 24, "join_paths_from_topic_name": "operations_orders",
    "calculations": [], "column_totals": {}, "row_totals": {}, "fill_fields": [], "pivots": [], "userEditedSQL": "" }
}
```

**Caveat checklist (each one bit during a real build; all silent — no API error):**
1. **Drop the tile-title child.** The card's `containers` stack must have **only** the `{as:"chart"}` child — no `{as:"metadata", format:"name"}` — or the label shows **twice** (tile title + the number's label).
2. **`number`/`comparison`/`progress` `field` (and `comparison`'s `comparison`) = a *complete* value-field** `{ row, field:{name,pivotMap}, label }`. A bare `{ "row": "_second" }` (missing `field`) **crashes at render** (`reading 'name'`); a `progress` with no `comparison` crashes (`reading 'row'`).
3. **The `sparkline` `field` MUST OMIT `row`** (it plots all rows). A stray `row` becomes `_first.<field>` in the compiled reference → unresolvable → **every point reads 0 → flat line.**
4. **Set `descriptionBefore`/`descriptionAfter` to `""`, not absent** — an absent one renders the literal word **`undefined`** around the comparison.
5. **Query sorts DESCENDING** so `_first` = latest / `_second` = prior — therefore the **sparkline needs `reverse: true`** or it draws latest→oldest (backwards).
6. **`swapColors: true`** = lower-is-better (green on a *decrease*); the comparison **auto-computes the %** — no table calc. **`comparisonType`**: `percent` / `number` / `number_percent`; `decimals` sets precision.
7. **Sparkline `width`/`height` are fixed px, not responsive** (`%`→px; no container-fill) — match them across tiles you compare.
8. **Snapshot (single-row) query → `number` sections only** (sparkline/comparison need ≥2 rows).
9. **Native KPI canNOT threshold-recolor the *value*** — if you need a red-when-bad number, use a **markdown card** with a `color_class` calc instead (see [markdown-tiles.md](markdown-tiles.md)); everything else above a markdown card and native KPI do equally well.
10. **Read it back** — confirm `visConfig.visConfig.config.markdownConfig` persisted before publishing.

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

`_stack: "stack"` with a **pivoted** color dimension — the query must include `"pivots": ["order_items.status"]`. For horizontal, use `chartType: "barStacked"` with `_dependentAxis: "x"` and `series[].xAxis: "x"`. For 100% stacking, use `columnStackedPercentage` with `color._stack: "stack_percentage"`.

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

For families not fully covered here (funnel, sankey, boxplot, map, regionMap, singleRecord), read back an existing dashboard that uses the chart:

```bash
omni documents v2-get <identifier>
```

Each tile's `visConfig` shows the persisted `chartType`, `fields`, and inner `visConfig` with the rendering spec under `config`, the same shape you write, so it can be reused as a template as is.

> **Tip**: When the organization already has dashboards with the chart types you need, read them back once and reuse those `config` objects as templates.

## resultConfig

Optional field on `queryPresentation` controlling result display independent of the visualization. Commonly includes `columnOrder` (array), `hiddenColumns` (array), `columnWidths` (object of field → pixel width).

### Table display & conditional formatting

**Table display and conditional formatting go in the omni-table's inner config** (`visConfig.visConfig.config`); a config placed in `resultConfig` is ignored with no error. To confirm a setup, write the table on a draft and read it back with `omni documents v2-get-draft`: the formatters come back under the inner `config`. The inner config carries: `tableType` (`"stretch"` fills the tile; default `"spreadsheet"` hugs left), `rowBanding` (`{enabled, bandSize}`), `hideIndexColumn`, `columnFormats` (`{ "<view.field>": { align: "left"|"right" } }`), and **`conditionalFormatters`**:

```jsonc
// visConfig.visConfig = { visType: "omni-table", config: {
//   tableType: "stretch", rowBanding: { enabled: true, bandSize: 1 }, hideIndexColumn: true,
//   columnFormats: { "view.field": { "align": "right" } },
"conditionalFormatters": [
  { "id": "rate_scale", "type": "scale",
    "selection": { "type": "field", "field": "view.rate", "target": "view.rate" },
    "format": { "domain": { "min": 0.94, "mid": 0.96, "max": 0.98 }, "range": ["#d73027","#ffffbf","#1a9850"] } },
  // reversed scale = reverse the `range`. Scale formatters take NO backgroundColor (source strips it).
  { "id": "days_high", "type": "single",
    "selection": { "type": "field", "field": "view.avg_days", "target": "view.avg_days" },
    "rule":   { "type": "greater-than", "value": 5, "valueType": "number" },   // also less-than; valueType number|date|text
    "format": { "backgroundColor": "#ffeeee", "color": "#990000", "fontWeight": "bold", "fontStyle": "italic" } }
] }
```

`selection.type` may be `field`, `row`, or `cellRange`; **`selection` carries both `field` and `target`** (same value for a field selection). With **`automaticVis: true`**, conditional formatting still renders as long as the formatters are in this inner `config`. The whole spec sits under `config`, on write and on read.

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
| `chartType` / `config` / `fields` at the presentation top level (v1 shape) | **400** "Unrecognized key" | Move them into the `visConfig` envelope |
| `modelId` / `model_extension_id` (or v1 `visConfig` hint) in the tile query | Silently ignored/rewritten | Remove — tile queries are server-anchored to the workbook model |
| Query missing required collection fields | **400** listing each missing field | Include `sorts`, `filters`, `calculations`, `column_totals`, `row_totals`, `fill_fields`, `pivots`, `userEditedSQL` (empty fine) plus `table`, `fields`, and always send `limit`, `join_paths_from_topic_name` |
| `barColor` / `areaColor` / `stackedBarColor` | Request rejected (invalid enum) | Use `column`/`bar`, `area`, `columnStacked`/`barStacked` |
| `configType: "pie"` / `"funnel"` / `"map"` | Wrong/missing config | Pie → `configType: "polar"`; funnel/sankey/map have **no** `configType` (use the right `visType`) |
| `prefersChart` is `false` or missing | Always shows table | Set `prefersChart: true` |
| `_dependentAxis` mismatched | Axes inverted / column vs bar wrong | `"y"` for vertical (column/line/area), `"x"` for horizontal bars |
| `series[].yAxis` vs `xAxis` wrong | Measures don't render | `yAxis: "y"` for vertical, `xAxis: "x"` for horizontal |
| `domain`/`title`/`scale` set directly on `x`/`y` (e.g. `y.domain`, `y.min`) | **Silently ignored** — axis won't zoom, title won't change | Nest under `axis`: `y.axis.domain.{min,max,zero}`, `y.axis.title.value`. `domain` is an **object** `{min,max,zero}`, not `[min,max]`; min/max are **raw** values (`0.6` = 60%) |
| `_stack: "normalize"` for 100% stacked | Invalid enum | Use `_stack: "stack_percentage"` (enum: `group`/`stack`/`stack_percentage`/`overlay`) |
| `series[].color: "#hex"` for a solid series color | No effect (ignored per-layer slot) | Use `series[].mark._mark_color` + `manual: true`; for color-by-value use `config.color.values` |
| `series[].color: "#hex"` on a layer-compiled chart (`behaviors.useLayerCompiler: true`) | The tile silently falls back to the classic editor and compiler | Remove it; a solid layer color is `series[].mark._mark_color` + `manual: true`, per-value colors go in root `colorFields` |
| Two measures of the same mark on one axis of a layer-compiled chart | They overlay instead of stacking; root or per-layer `_stack` does not help | Fold them into one Measure values layer (`foldedFields` + an `omni__field_value` series colored by `omni__field_name` with `_stack`) |
| Reading a layer chart's kind from `chartType` | Stale — the layers editor does not update it | Read `series[].mark.type`; set `chartType` yourself when authoring |
| Expecting an API-created cartesian tile to open in the layers editor | It opens in the classic editor | Add `behaviors.useLayerCompiler: true` (and fold same-axis same-mark measures) |
| `series[].label` to rename a legend entry | No effect — legend keeps the field label | Set `series[].title.value` (the legend reads `title.value`, falling back to the field label) |
| Stack dimension not pivoted | Single un-split series | Add the `color.field` dimension to `query.pivots` |
| Missing measure in query | Empty tile, no error | Every query must include at least one measure |
| `regionMap` not shading | "No chart available" / blank map | Use `visType: "map"`, `regionType: "us-states"`/`"countries"`, a `sourceProperty` matching your field's values (`"NAME"`/`"CODE"`/iso codes), and `center`/`zoom` |
| `chartType: "auto"` with empty config | "No chart available" | `auto` can't persist a render; populate a concrete spec from the recipes in this file. When no recipe covers the chart, copy the config from an existing dashboard that uses it (`v2-get`) |
| `aiContext`/`markdown` on AI-summary tile | Renders blank/wrong | Use `ai_context` + `showWarning` (snake_case) |

## Text & AI tiles

- **Markdown** (`chartType: "markdown"`, `visType: "omni-markdown"`): `config: { markdown: "...", version: 1 }`. The markdown body is **mustache-templated against the tile's query** — loop rows with `{{#result}} … {{view_name.field_name.value_static}} … {{/result}}` and reference single values like `{{result._first.view_name.field_name.value_static}}` or `{{result._total.first.view_name.field_name.value_static}}`. Keep a real query on the tile so the template has data.
  - **Use `.value_static` for a clean value**, not `.value`. `.value_static` is the formatted display string; `.value` is an interactive drill element (a clickable component, not plain text).
  - Result rows are keyed by **field name** — there is **no positional column token** (you must name the field, not "column 1").
  - **Set `automaticVis: false` and `prefersChart: false` on the tile**, or the published renderer ignores your markdown and tries to auto-derive a chart from the query → the tile renders **blank** with no error. Tell-tale: `{{result…}}` tokens resolve when tested but the whole tile is white.
  - **The HTML sanitizer allows `style`, `className`, and `data-*` attributes plus `<style>` blocks**, so you can ship scoped CSS inside a markdown tile. (A sandboxed `<iframe>` with `allow-scripts` is also available for arbitrary JS if CSS isn't enough.)
  - **`{{controls.<id>.summary}}`** injects a dashboard control's current selection (its friendly label) into the body — the basis of dynamic captions and the metric-switch pattern (see [markdown-tiles.md](markdown-tiles.md)). Only **dashboard** controls resolve here, not tile-embedded `query.controls`. See [controls.md](controls.md).
- **AI summary** (`chartType: "omni-ai-summary-markdown"`, `visType: "omni-ai-summary-markdown"`): `config: { ai_context: "...", showWarning: true }` (snake_case `ai_context`, **not** `aiContext`; no `markdown`/`version`). Requires a query — the AI summarizes its results.

> **Markdown-tile recipes live in [markdown-tiles.md](markdown-tiles.md)** — sizing/clipping, responsive `cqw` headline fonts, the metric-picker KPI switch, the data-driven funnel, and the [docs.omni.co/showcase](https://docs.omni.co/showcase) gallery pointer.

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

> **Recommendation**: For an unfamiliar chart type, find an existing dashboard that uses it, read it back with `omni documents v2-get`, and reuse the inner vis config as your template.
