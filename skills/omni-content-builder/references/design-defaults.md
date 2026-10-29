# Dashboard Design Defaults

- **Lead with the answer, top-left.** Put the main KPI / answering chart in the upper-left — viewers scan in an F/Z pattern.
- **3–5 charts per page.** Beyond that, split across pages/tabs (see [containers.md](containers.md)).
- **Functional color, 90/10.** Neutral tones dominate; one accent for emphasis or status — not decoration.
- **Match chart to question** — trend → line/area/bar; ranking → horizontal bar; part-to-whole → 100% stacked; correlation → scatter; the full table is [below](#match-chart-to-question).
- **Put controls next to what they drive,** with action-oriented labels ("Filter by Region", not "Region").
- **Hide complexity behind a parent control** — one control drives many; leave the child controls unplaced (see [controls.md](controls.md#parent-controls-one-control-drives-many)).
- **Charts read without hovering.** A viewer should get the key insight from the chart itself; a tooltip is a detail, not the message.

## Match chart to question

By question, with the chart and the config that answers it. A requested chart type always wins.

| The question | Chart | Config |
|---|---|---|
| How has it moved over time? | Line, area or column on a date axis | Cartesian ([layers.md](layers.md) for a new tile, [visConfig.md](visConfig.md) for a classic one) |
| Which is biggest? | Horizontal bar, sorted by the measure | `_dependentAxis: "x"`, the category on `y`, `axis.sort` by the measure |
| How do the parts make the whole? | 100% stacked; a pie only for a handful of parts | `_stack: "stack_percentage"` on the Measure values layer or the colored layer; pie in [other-chart-types.md](other-chart-types.md#config-object-pie--donut) |
| Do two measures move together? | Scatter, a third measure as size | `mark.type: "point"`, `size.field` |
| One number, how is it doing? | KPI tile with a comparison | [kpi-tiles.md](kpi-tiles.md) |
| Where does it concentrate across two dimensions? | Heatmap | [other-chart-types.md](other-chart-types.md#config-object-heatmap) |
| Where do items drop out of a sequence, or flow between states? | Funnel; sankey | [other-chart-types.md](other-chart-types.md#config-object-funnel) |
| How is it spread? | Boxplot | [other-chart-types.md](other-chart-types.md#config-object-boxplot) |
| By region? | Map | [other-chart-types.md](other-chart-types.md#config-object-map--region-map) |
| The viewer wants the rows | Table | `prefersChart: false`; also the fallback when no chart type was asked for and the config is uncertain |

Several measures in one X/Y chart, a second axis, facets and smart aggregation are chosen in [layers.md](layers.md#choosing-a-shape).
