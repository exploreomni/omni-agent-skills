# Layer-compiled cartesian charts

The layers chart editor (Omni's "New X/Y chart builder") and the layer compiler behind it: what selects it, the per-layer shape it stores, the Measure values fold, the recipes for creating a layer chart or moving a tile through the API, the editor's labels mapped to config keys, the keys the layer schema accepts, a catalog of shapes rendered as written, and the classic gotchas that change. Everything here was built in the UI and read back with `omni documents v2-get`, or written through the API and checked in the editor and the render. The classic cartesian shapes stay in [visConfig.md](visConfig.md); the envelope and tile fields are in [queryPresentations.md](queryPresentations.md).

## Table of Contents

- [Choosing a shape](#choosing-a-shape)
- [What the layer editor writes](#what-the-layer-editor-writes)
- [Measure values: several measures in one layer](#measure-values-several-measures-in-one-layer)
- [Creating a layer-compiled chart through the API](#creating-a-layer-compiled-chart-through-the-api)
- [Moving a tile between the two compilers through the API](#moving-a-tile-between-the-two-compilers-through-the-api)
- [The layers editor's words, and the keys they set](#the-layers-editors-words-and-the-keys-they-set)
- [What a layer can carry](#what-a-layer-can-carry)
- [Layer shapes, each rendered as written](#layer-shapes-each-rendered-as-written)
- [A layer that uses fewer dimensions than the query ("smart aggregation")](#a-layer-that-uses-fewer-dimensions-than-the-query-smart-aggregation)
- [Gotchas that change on a layer chart](#gotchas-that-change-on-a-layer-chart)


Omni renders a cartesian config through one of two compilers, and the config decides which:

| | Classic compiler | Layer compiler ("layers", the new X/Y chart builder) |
|---|---|---|
| Selected by | `behaviors.useLayerCompiler` absent or `false` | `behaviors.useLayerCompiler: true` |
| Editor shown in the workbook | **X-Axis / Left-Axis / Right-Axis / Color and legend** panel | **Setup / Style** tabs with a "New X/Y chart builder" banner; each measure is a layer with its own **Mark**, **Color** and **Label** |
| Who writes it | Every recipe in [visConfig.md](visConfig.md) unless it says otherwise; any config saved before layers | Every X/Y chart created in the UI since layers went on; the "Test the new chart editor" and "Upgrade charts" actions |

Both compilers read the same envelope (`visConfig.chartType` / `fields` / `visConfig.visType: "basic"` / `config`), the same `configType: "cartesian"`, `_dependentAxis`, `x`, `y` / `y2`, `series[]` and `tooltip`. What differs is where the encodings live and how layers combine. Layers are documented at [docs.omni.co/visualize-present/visualizations/layers](https://docs.omni.co/visualize-present/visualizations/layers).

**A config without the flag stays on the classic compiler.** Nothing about the GA of layers changes what an API-created tile gets: a cartesian config sent through `v2-create` or a draft patch opens in the classic editor and renders through the classic compiler until `behaviors.useLayerCompiler: true` is in its config. Confirm which one a tile is on by opening its workbook tab, clicking **Options** above the chart, and looking for the banner, or by reading the tile back and checking `behaviors.useLayerCompiler`.

## Choosing a shape

**Classic or layers for a new tile.** Write the layer shape for a new X/Y chart unless the request or the dashboard says otherwise. Every X/Y chart built in the UI is layer-compiled, so a layer tile opens in the same editor as its neighbors, while a classic tile beside them opens in the X-Axis / Left-Axis / Right-Axis editor and only reaches the layer features (a color field per layer, pinned colors in `colorFields`, `stackSort`, Measure names on an axis, legend slots) after a move. Write classic only when patching a tile that is already classic and nobody asked to move it, or when the shape you need is a classic recipe in [visConfig.md](visConfig.md) with no row in [Layer shapes](#layer-shapes-each-rendered-as-written). A dashboard can hold both; nothing forces a move.

**Within a layer chart,** the question is how the measures and dimensions relate, and each answer is one shape:

| The chart should show | Shape | Where it is |
|---|---|---|
| Several measures that add up: stacked, grouped or 100% on one axis | One Measure values layer (`foldedFields` + an `omni__field_value` series colored by `omni__field_name`), `color._stack` = `stack`, `group` or `stack_percentage` | [Measure values](#measure-values-several-measures-in-one-layer) |
| Measures that do not add up, on one scale, with their own marks (bars and a line) | One layer per measure on `y`; on one axis the **first** `series[]` entry paints on top, so list the line before the bars; one stack mode per axis | [Layer shapes](#layer-shapes-each-rendered-as-written) |
| A measure on a different scale (a count beside revenue) | Its own layer on `y2`, left out of any fold; `alignAxisZeros: true` when the two zeros should line up | [Creating a layer-compiled chart](#creating-a-layer-compiled-chart-through-the-api) |
| One measure split by a dimension's values (stacked or colored) | `series[].color.field` = the dimension, the dimension in `query.pivots`, `_stack` = `stack` or `group`; pinned colors in `colorFields` | [Layer shapes](#layer-shapes-each-rendered-as-written) |
| Measures compared side by side with no time axis | Measure names on the X axis: `x.field.name: "omni__field_name"` with a fold and an `omni__field_value` bar layer | [Layer shapes](#layer-shapes-each-rendered-as-written) |
| One panel per measure, or per category | `facet.column` (or `facet.row`) on `omni__field_name` or on the dimension (also in `query.pivots`); `scaleYAxes: "independent"` when the panels need their own scales | [Layer shapes](#layer-shapes-each-rendered-as-written) |
| A smoothed or fitted line | `movingAverage` or `regression` on a plain layer, never on the fold | [Measure values](#measure-values-several-measures-in-one-layer) |
| A third measure as point size | `mark.type: "point"` with `size.field` on that layer | [Layer shapes](#layer-shapes-each-rendered-as-written) |
| A chart at coarser grain than the query (a line per month over a query grouped by month and status) | A layer that omits the dimension plus a `column_totals` subtotal on the last dimension it keeps | [Smart aggregation](#a-layer-that-uses-fewer-dimensions-than-the-query-smart-aggregation) |

Two combinations do not work and have no shape: one fold split across the two axes (the measure that belongs on the other axis is its own layer), and two layers stacked on each other (stacking only happens inside one layer). Which chart *family* a question wants (line, horizontal bar, 100% stacked, scatter, KPI, table) is in [design-defaults.md](design-defaults.md#match-chart-to-question).

## What the layer editor writes

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

## Measure values: several measures in one layer

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

- `foldedFields` (root) lists the measures the layer draws, in legend order; when the layer stacks, the first entry is the top segment and the last entry the bottom one. They stay in `query.fields` and `visConfig.fields` as usual.
- The layer's `field.name` is the synthetic **`omni__field_value`** ("Measure values"); its `color.field.name` is **`omni__field_name`** ("Measure names"). `{ "name": … }` is enough — the full field objects the upgrade dialog writes (`label`, `isMeasure`, …) are not needed.
- `color._stack` on this layer is the stacking of the measures: `stack`, `group`, `overlay` or `stack_percentage`.
- A measure that should be its own layer (a line on the right axis beside stacked bars) is a separate `series` entry and must be left out of `foldedFields`.

What the Measure values layer does with keys a plain layer honors, each tried:

- `title.value` on the fold layer changes nothing; its legend title is `color.axis.title.value`.
- `regression` and `movingAverage` on the fold layer draw one line through all the folded rows together, which means nothing; put them on a plain layer.
- `dataLabel` and `totals` (with `position`) on the fold layer work: one label per segment, one total per stack.
- One fold cannot be split across the axes: a second `omni__field_value` series on `y2` redraws every folded measure there as well. A measure that belongs on the other axis is its own layer, left out of `foldedFields`.

## Creating a layer-compiled chart through the API

Take any cartesian recipe in [visConfig.md](visConfig.md), add `"useLayerCompiler": true` to `behaviors`, put the per-layer encodings on the series, and fold measures that share an axis and a mark. Bars on the left axis, a line on the right, zeros aligned:

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

## Moving a tile between the two compilers through the API

Both directions are a draft patch of the tile's config, in place, keeping its key, filter maps and layout. The UI's own actions (the tab's *Test the new chart editor*, which copies the tab, and the dashboard's *Upgrade charts to the new chart editor* and the tab's *Leave the new chart editor*, which change the tile in place) store exactly the shapes below, so a tile you convert by hand is indistinguishable from one the user converted.

**Classic to layers.** Add `behaviors.useLayerCompiler: true`. That alone is enough when every measure has its own mark or axis, and when the chart is colored by a dimension through the root `color` (a classic `columnStacked` config with the flag added rendered stacked by its dimension as before: the chart-wide color is applied to the layer). The one case the flag alone gets wrong is two or more measures of the same mark on one axis: they stacked under the classic compiler and now overlay. Fold them into a Measure values layer with `color._stack: "stack"` (the shape in [Measure values](#measure-values-several-measures-in-one-layer)); that is also what the UI's upgrade writes for such a chart.

**Layers to classic.** Removing the flag is not enough when the chart has a Measure values layer: a fold shape (`foldedFields` plus an `omni__field_value` series) with the flag absent or `false` renders **"No chart available"**, because the classic compiler does not read the synthetic fields. Unfold it yourself, which is what the UI writes when a chart leaves layers: one `series[]` entry per folded measure, each with the layer's `mark` and axis; the fold's `color` minus its `field` moved to the root `color` (so `_stack` and the legend title survive); the shared mark type on the root `mark`; `foldedFields` and `useLayerCompiler` removed. Per-layer encodings every layer shared (a color field, a size field, a mark type) move to the root; ones that differ stay on their series, where the classic compiler reads only the mark.

```bash
# the tile as it is, from v2-get or v2-get-draft, with only the config changed
omni documents v2-patch-draft <identifier> --body @to-layers.json   # a body like:
# { "summary": "move Revenue vs orders to the layers editor",
#   "queryPresentations": { "data": { "3": { …the tile with behaviors.useLayerCompiler: true… } }, "order": [ …unchanged… ] } }
```

Then `v2-get-draft` to confirm the config came back as sent, and `v2-publish-draft`.

## The layers editor's words, and the keys they set

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
| **Axes options → Swap left and right**, **Display order: Left values on top / Right values on top** | Every `yAxis` flipped; the order of `series[]` (see [Which layer draws on top](#layer-shapes-each-rendered-as-written)) |
| **Measure values** section: drag a measure in or out, reorder | `foldedFields` membership and order (also the legend order and, on a Measure names axis or facet, the panel order) |
| **Field properties…** on a layer's field (title, format) | `series[].title.value`; number formats stay on the field in the model or the query |
| Trend line, moving average | `series[].regression`, `series[].movingAverage` |
| **Auto-charting on / off** | `automaticVis: true` / `false` on the presentation; the layers editor turns it off once a layer is edited |
| "Test the new chart editor…" / "Upgrade charts to the new chart editor…" / "Leave the new chart editor…" | The compiler moves in [Moving a tile between the two compilers through the API](#moving-a-tile-between-the-two-compilers-through-the-api): the first copies the tab, the other two change the tile in place |

## What a layer can carry

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
| `series[].regression`, `series[].movingAverage` | `regression: { enabled, method, line: { color, dash, opacity, width }, noGroupByEncoding }`; `movingAverage: { enabled, window: { period, type }, line: { color, dash, opacity, point, width } }`. The two `line` objects are the exception to the strict rule: a key they do not declare (an `interpolate`, say) is dropped without rejecting the config |
| `series[].dataLabel` and root `dataLabel` | `enabled`, `field`, `format`, `position`, `minValue`, `maxValue`, `useSparseLabelAlgorithm`, `color`, `font`, `fontSize`, `fontStyle`, `fontWeight` |
| `facet` | `column` / `row` (`field`, `label`, `sort`, `title`, `manual`), `scaleXAxes` / `scaleYAxes` (`shared` / `independent`), `showXAxis` / `showYAxis` (`every` / `once`), `wrap`, `wrapColumns` |

Chart-wide `mark`, `color` (with a `field`), `size` and `dataLabel` are **broadcasts**: the parser copies each onto every layer that lacks its own and then reads only the layers. A fieldless root `color` is different: it holds the series-identity legend's position and title and the chart palette, and stays.

## Layer shapes, each rendered as written

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
| Legend and stack order of folded measures | The order of `foldedFields` is the legend order, and the **first** entry sits at the **top** of the stack: list the measure that should sit at the bottom last |
| A Measure values layer colored by a real dimension | `series[].color.field` = the dimension on the `omni__field_value` layer: each segment is the measures added together for that value, so the measures cannot be told apart. Color by `omni__field_name` to see the measures; split by the dimension with a facet or a second layer instead |
| Small multiples on two fields | `facet: { row: { field: { name: status } }, column: { field: { name: FN } } }` gives a grid, rows per status and a column per folded measure |
| Which layer draws on top | On **one axis**, the first `series[]` entry paints on top: `[bar, line]` hides the line inside the bars, `[line, bar]` runs it over them, and of two bar layers the first-listed one is in front. **Across the axes**, the axis whose layers come later in `series[]` paints on top: `[line y2, bar y]` hides the line, `[bar y, line y2]` shows it, `[bar y, bar y2]` puts the `y2` bars in front. One tested exception: a line on the primary axis listed before bars on the other axis still drew on top |
| Segment labels and stack totals on folded measures | `dataLabel: { enabled: true, position: "inside_end" }` and `totals: { enabled: true, position: "outside_end" }` on the `omni__field_value` layer |
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

## A layer that uses fewer dimensions than the query ("smart aggregation")

A layer draws the rows the query returns; it never re-aggregates them. When the query groups by a dimension that a layer does not encode (not on its axis, color, size or facet), the layer needs a row per remaining dimension value, and the warehouse has to supply it: add a subtotal on the **last dimension the layer keeps** to `query.column_totals`, keyed by field name:

```json
"query": {
  "fields": ["order_items.created_at[month]", "order_items.status", "order_items.total_revenue"],
  "column_totals": { "order_items.created_at[month]": { "type": "aggregation" } },
  …
}
```

The layer then reads the month subtotal rows and draws one value per month (the editor shows a **TOTAL** badge on such a layer, and writes exactly this entry when a color field is removed from a layer while the dimension stays in the query). Without the entry the same line layer zigzags through every status row. This is per query, so it also feeds the table under the chart. Subtotals nest from the right, so the dimensions a layer keeps must be a prefix of the query's grouped dimensions. A pivoted dimension that no layer encodes needs nothing: it rolled up on its own in every test.

## Gotchas that change on a layer chart

| Classic rule in [visConfig.md](visConfig.md) | On a layer-compiled chart |
|---|---|
| `series[].color: "#hex"` is ignored; `series[].label` is ignored; `domain` directly on `y` is ignored | **Worse than ignored: any key the layer schema does not declare drops the tile back to the classic editor and compiler**, flag and all, with no error; the chart still draws through the classic path. All three were tested. When a layer chart opens in the X-Axis / Left-Axis / Right-Axis editor, remove the undeclared key (see [What a layer can carry](#what-a-layer-can-carry)) and read back. A solid layer color is `mark._mark_color` + `manual: true`; per-value colors go in `colorFields`; the legend label is `title.value`; axis styling goes under `axis` |
| Two same-mark bar series default to STACK; set `color._stack: "overlay"` to overlay | Layers never stack across layers: two bar layers on one axis **overlay** whatever `_stack` says at the root or on the layers. To stack them, fold them into one Measure values layer |
| Stack dimension goes in root `color.field` + `query.pivots` | The pivot is still required; the color field lives on the layer (`series[].color.field`). A root `color.field` still works when you move a classic config over |
| `series[].mark._mark_color` + `manual: true` | Still the per-layer solid color (and what the editor writes) |
| `series[].title.value` for the legend label | Still works |
| Axis styling under `<axis>.axis` | Still works |
| `_dependentAxis`, `yAxis` / `xAxis`, `y2` for the right axis | Unchanged |
| A query dimension the chart does not encode is simply ignored | A layer that omits a grouped dimension draws every row (a line zigzags) unless the query carries a `column_totals` subtotal on the last dimension the layer keeps |

