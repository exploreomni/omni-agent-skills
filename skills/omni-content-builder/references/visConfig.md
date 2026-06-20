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

> **Important**: The visualization config schema is not fully documented in Omni's public API docs. The cartesian structures below (axis, color, series, mark) are derived from Omni's visualization parser schema and cross-checked by reading dashboards back via `omni documents v2-get`. For uncommon chart types (funnel, sankey, map, boxplot, single-record), **always verify** by building a reference chart in the UI and reading it back before relying on these examples.

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

> **Read-back is flat — writes must be nested.** `v2-get` returns the inner vis config **flat**: the spec keys spread beside `visType`, with no `config` key. A patch that sends that flat shape back **silently keeps only `visType`** and drops the rest (flat-sent `markdownConfig`/`alignment` dropped; `config`-nested persisted). Misplaced *presentation*-level keys, by contrast, 400 loudly. Never round-trip a GET tile unchanged; re-nest the inner spec under `config` first. **This covers *any* write sourced from a GET payload — restoring/reverting/duplicating/moving a tile by copying it out of a snapshot and patching it back is also a round-trip** (the flat config gets dropped → "No chart available"). Verify the reverted tile — don't assume a restore is safe.

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
- **Two same-mark bar series default to STACK — you must force overlay.** `behaviors.stackMultiMark:false` is *not* enough: when an axis has ≥2 series of the same stackable mark (bar/area) and no explicit stack, the compiler returns `STACK` (verified in `get-effective-axis-stack.ts`), so the ghost stacks *on top of* the actual (gray top = actual + projected) instead of overlapping. Set **`config.color._stack: "overlay"`** (enum: `group`/`stack`/`stack_percentage`/`overlay`) — the compiler returns that explicit value before falling through to the same-mark STACK default, and `OVERLAY` skips the stacking-field encodings so both bars draw from zero. Tell-tale of the bug: the dependent axis auto-scales to ~`actual+projected` instead of ~`projected`.
- **Watch the anchor branch.** A run-rate projection table-calc (the `OMNI_OFFSET_MULTI`/`OMNI_FX_ROW`/`COUNT_A` "is-this-the-last-row" pattern) is typically non-null on the **last *two*** rows: the current month gets the projected value, and the **second-to-last** gets its *actual* value as an anchor — necessary so a projection **line** visibly connects from the last complete point. For a **column** overlay that anchor paints an unwanted ghost cap on the prior month. Strip it: the calc's outer `CASE` has the shape `CASE(isLastRow, projection, CASE(isSecondToLast, actual, null))` — replace `operand[2]` (the inner anchor `CASE`) with a `null` literal so only the current month projects.
- A run-rate projection needs a date-extent measure (`max(timestamp)` cast through the session timezone, like `last_order_date`/`last_session_date`) **on the topic's own base view** — it can't reach a `max-date` measure on a view the topic doesn't join. The calc references it via `allow_refs_to_unselected_fields:true`, so it need not be a selected field.

### Small multiples (faceting)

Split one chart into per-category panels with `config.facet`:

```json
"facet": { "column": { "field": { "name": "products.category" } }, "wrap": true, "wrapColumns": 3 }
```

Use `column` and/or `row`; `wrap: true` + `wrapColumns` controls trellis wrapping. Scales/axes default to shared.

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
| `innerRadiusPercent` | No | `0`–`100`, donut hole size = ring thinness. `66` ≈ thin ring, `~40` chunky, `0` = solid pie. |
| `outerRadiusPercent` | No | `0`–`100`. **Defaults to 90 — but auto-shrinks to `90 × 0.7 ≈ 63` whenever `dataLabel.enabled`** (reserves label room). If labels are on and the donut looks small, set this explicitly (e.g. `80`). |
| `dataLabel` | No | `{ enabled: true, field: { name } }`. `field` sets **what the slice label shows** — point it at the `color` dimension to label slices by category; omit `field` and it shows the `theta` value. |
| `dataLabelPercentage` | No | `{ enabled: true, decimals: 1 }` — **appends the auto share** → `"Category (23.4%)"`. Separator is hardcoded parentheses (no dash). `percent` = ECharts' share of the `theta` total. |
| `dataLabelPosition` | No | `"inside"` / `"outside"` — a **top-level polar key**, not `dataLabel.position`. |
| `tooltip` | No | Fields for hover |

> **No legend sizing.** The pie config exposes no legend-size control — the only legend option is `color.legendPosition` (position, incl. `NONE`). A larger/custom legend requires a markdown tile.
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

> **"No `configType`" ≠ "no `config` wrapper."** Funnel and sankey still write their inner spec **nested under `config`**: `visConfig.visConfig = { visType: "funnel", config: { value, color, orient, … } }`. They merely omit the `configType` discriminator *inside* `config` (that field only exists for the `"basic"` renderer). Authoring the inner spec **flat** (`{ visType, value, color, … }` with no `config`) silently drops everything but `visType` → the tile renders **"No chart available."** Same drop as the GET round-trip trap, but it also bites fresh funnel/sankey authoring.

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

> Map specs are best captured by building one in the UI and reading it back (`omni documents v2-get`, re-nesting the flat inner spec under `config`).

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

**Table display + conditional formatting live in the omni-table's INNER config** (`visConfig.visConfig.config` on write — NOT `resultConfig`). Verify by building a conditionally-formatted table in the UI (or via Blobby) and reading it back with `omni documents v2-get` — the formatters come back under the inner `config`, and a config placed in `resultConfig` is silently ignored. The inner config carries: `tableType` (`"stretch"` fills the tile; default `"spreadsheet"` hugs left), `rowBanding` (`{enabled, bandSize}`), `hideIndexColumn`, `columnFormats` (`{ "<view.field>": { align: "left"|"right" } }`), and **`conditionalFormatters`**:

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

`selection.type` may be `field`, `row`, or `cellRange`; **`selection` carries both `field` AND `target`** (same value for a field selection). **`automaticVis: true` is fine** — conditional formatting renders as long as the formatters are in this inner `config`, not `resultConfig` (where they're silently ignored). On write, nest the whole spec under `config` (GET flattens it).

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
| `domain`/`title`/`scale` set directly on `x`/`y` (e.g. `y.domain`, `y.min`) | **Silently ignored** — axis won't zoom, title won't change | Nest under `axis`: `y.axis.domain.{min,max,zero}`, `y.axis.title.value`. `domain` is an **object** `{min,max,zero}`, not `[min,max]`; min/max are **raw** values (`0.6` = 60%) |
| `_stack: "normalize"` for 100% stacked | Invalid enum | Use `_stack: "stack_percentage"` (enum: `group`/`stack`/`stack_percentage`/`overlay`) |
| `series[].color: "#hex"` for a solid series color | No effect (ignored per-layer slot) | Use `series[].mark._mark_color` + `manual: true`; for color-by-value use `config.color.values` |
| `series[].label` to rename a legend entry | No effect — legend keeps the field label | Set `series[].title.value` (the legend reads `title.value`, falling back to the field label) |
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

> **Recommendation**: For an unfamiliar chart type, build it once in the UI, read it back with `omni documents v2-get`, and reuse the inner vis config — re-nested under `config` — as your template. That is the most reliable path to a correct config.
