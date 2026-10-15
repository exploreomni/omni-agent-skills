# Building Dashboards People Can Act On

The [Design defaults](../SKILL.md#design-defaults) make a dashboard readable. This reference makes an operational or exec dashboard *actionable*: a viewer should finish it knowing what to do today and with whom. Same rule as the defaults: direction from the user, an existing dashboard's conventions, or an org theme wins.

## Contents

- [Order by what can still change](#order-by-what-can-still-change)
- [Tables: five columns, no truncated headers](#tables-five-columns-no-truncated-headers)
- [List rows in a markdown tile](#list-rows-in-a-markdown-tile)
- [Every view drills](#every-view-drills)
- [Relative dates everywhere](#relative-dates-everywhere)
- [Click path: overview → breakdown → deep dive](#click-path-overview--breakdown--deep-dive)
- [Colour has one meaning](#colour-has-one-meaning)
- [Comparing a value with its outcome](#comparing-a-value-with-its-outcome)
- [Shares that sum to 100%](#shares-that-sum-to-100)
- [Legends and axis formats](#legends-and-axis-formats)
- [Titles, subtitles, and KPI height](#titles-subtitles-and-kpi-height)
- [Scope filters vs viewer controls](#scope-filters-vs-viewer-controls)
- [Tiles an alert can watch](#tiles-an-alert-can-watch)
- [Checklist before publishing](#checklist-before-publishing)

## Order by what can still change

- **Still recoverable before already lost.** Put the "at risk" list above or left of the "over / lost" list. A viewer can act on the first; the second is a post-mortem.
- **Every list row names an owner** (account manager, team lead, project owner). A row without an owner answers "what", not "with whom".
- **Use a live window, not lifetime totals.** For example, open items with activity in the last 90 days. Lifetime numbers are dominated by stale records. Say the window in the subtitle.
- **Move data-quality outliers to their own tile.** A tiny denominator (a 2-hour budget, a £10 target) produces ratios like 77,214% that top every ranked list. Filter them out of the main lists (`budget > 10`) and show them in a "Check these" tile.

## Tables: five columns, no truncated headers

- **At most 5 columns.** If a row needs more context, use a [list row](#list-rows-in-a-markdown-tile).
- **Long measure labels truncate column headers** ("Time Value at Cli…") on a narrow tile. Shorten the labels (`resultConfig` column labels or a shorter measure `label`), widen the tile, or switch to a list row. Never ship a table whose headers truncate.
- **Size the row `limit` to what the tile shows** without scrolling, and say so in the subtitle ("the 7 closest to budget"). Check it in a PNG render ([downloads.md](downloads.md)); the API cannot tell you a header truncated.

## List rows in a markdown tile

A `{{#result}}…{{/result}}` section repeats once per result row; inside it, field tokens are relative to the row ([mustache.md](mustache.md#iterating-rows-with-result)). One row = a bold title, one muted context line, one number, and an optional bar against a target:

```html
<style>
.r{display:flex;gap:12px;align-items:center;padding:6px 0;border-bottom:1px solid #E5E7EB}
.r .t{flex:1;min-width:0} .r .c{font-size:12px;color:#6B7280}
.r .n{font-weight:700;white-space:nowrap}
.bar{position:relative;height:6px;background:#F1F5F9;border-radius:3px;margin-top:4px}
.bar .f{height:6px;background:#D97706;border-radius:3px}
.bar .m{position:absolute;left:66.67%;top:-3px;width:2px;height:12px;background:#334155}
</style>
{{#result}}
<div class="r">
  <div class="t"><b>{{projects.name.value}}</b>
    <div class="c">{{projects.owner.value}} · {{projects.client.value_static}}</div>
    <div class="bar"><div class="f" style="width:min(100%, calc({{projects.pct_of_budget.raw}} / 1.5 * 100%))"></div><div class="m"></div></div>
  </div>
  <div class="n">{{projects.pct_of_budget.value}}</div>
</div>
{{/result}}
```

The bar's scale is 0–150%, so the 100% target marker sits at 66.67%. Clamp with `min(100%, …)` so overruns don't spill. The tile needs `automaticVis: false` ([visConfig.md](visConfig.md)); sort and `limit` the query, since the section renders every row returned.

### Trade-off: markdown looks better but is less flexible

A list row reads better than a native table or chart, but it costs flexibility. Choose it on purpose:

- **Viewers can't change it.** They can't re-sort it, resize columns, add a field, or switch it to a chart in the UI. Changing what it shows means editing the HTML template.
- **Authors and the AI agent have more to change.** A new field or a renamed field needs the query, the template and its CSS changed together. A field missing from `query.fields` renders as an empty string with no error.
- **Drilling only works where you put `.value`.** Native tables and charts drill on every cell; a markdown tile drills only on those tokens.
- **Controls that change fields don't carry through.** A `FIELD_SELECTION` or field-picker swap won't update the template, which still names the old field. A templated `breakdown` dimension (below) does carry through, because the field name stays the same.

Use markdown for short, curated lists that leaders read, such as "the 7 projects to act on". Use native tables and charts where people explore: re-sorting, adding fields, drilling across many cells. A deep-dive page usually needs both.

## Every view drills

In markdown tiles, use **`.value`** for names and key numbers: it renders a drillable, interactive element. **`.value_static`** is display-only text; use it for secondary context. **`.raw`** belongs only inside CSS or HTML attributes (`width:calc(…)`, `class="…"`). A dashboard whose markdown uses only `.value_static` has no drill path. Token reference: [mustache.md](mustache.md).

## Relative dates everywhere

Use a relative window on the dashboard date control **and** on every tile-level date filter, so the dashboard never goes stale:

```jsonc
{ "type": "date", "kind": "TIME_FOR_INTERVAL_DURATION", "ui_type": "PAST",
  "left_side": "12 complete months ago", "right_side": "12 months" }
```

- **Month over month:** `"left_side": "2 complete months ago", "right_side": "2 months"`, labelled "last month vs previous month".
- **Never hard-code a month name** in a tile title, subtitle, series title, or calculation label ("September vs August"). It is wrong the day the month turns. Use relative words, or `{{filters.<view.field>.summary}}` in a markdown tile ([mustache.md](mustache.md)).

## Click path: overview → breakdown → deep dive

Three pages, each answering the next question:

1. **Overview** — the KPI that says whether there is a problem.
2. **Breakdown** — where it is: a `heatmap` of department × business unit ([visConfig.md](visConfig.md#config-object-heatmap)), clickable to drill.
3. **Deep dive** — "pick a team": a single-select string filter placed **in the page**, and a "View by" filter **inside the chart tile** that changes which dimension the chart breaks down by.

**Build "View by" as a templated dimension.** A cartesian chart pins its category field in `visConfig` (`y.field` / `x.field`, plus the axis `sort`), so a `FIELD_SELECTION` switcher swaps the field in the tile's query without changing what the chart plots. Use a filter-only field and a templated `CASE` dimension ([omni-model-builder → templated-filters.md](../../omni-model-builder/references/templated-filters.md)). The chart always plots `breakdown`, and "View by" is an ordinary single-select filter:

```yaml
# topic views: block (or the view file)
time:
  filters:
    view_by:
      type: string
      suggestion_list: [ { value: Person }, { value: Client }, { value: Month } ]
      default_filter: { is: Person }
      filter_single_select_only: true
  dimensions:
    breakdown:
      sql: |-
        CASE {{ filters.time.view_by.value }}
          WHEN 'Person' THEN ${time.person}
          WHEN 'Client' THEN ${jobs.client}
          WHEN 'Month'  THEN FORMAT(${time.work_date}, 'yyyy-MM')
        END
```

On SQL Server and Fabric, format the month with `FORMAT(x, 'yyyy-MM')`; `CONVERT` with a style code is rejected in a model field ("CAST second argument should always be a type"). Sort the chart by a measure (for example hours, descending), so every View by option reads sensibly.

```jsonc
// controls.data
"team": { "config": {
  "type": "string", "kind": "EQUALS", "fieldName": "time.team", "label": "Team",
  "values": ["Design"], "filterControlType": "singleValueEquals" }, "map": {} },
"view_by": { "config": {
  "type": "string", "kind": "EQUALS", "fieldName": "time.view_by", "label": "View by",
  "values": ["Person"], "filterControlType": "singleValueEquals" },
  "map": { /* "<every other tile key>": false */ } }

// page-3 grid: the team filter as its own grid item, above the chart
{ "type": "filter", "id": "team", "instanceKey": "p3-team",
  "appearance": { "control": "buttonToggle", "display": "inline" },
  "gridPosition": { "x": 0, "y": 7, "w": 24, "h": 6 } }

// the chart tile stack's children: the View by filter, then the chart (which plots time.breakdown)
{ "type": "filter", "id": "view_by", "instanceKey": "tile-9-view-by",
  "appearance": { "control": "buttonToggle", "display": "inline" } },
{ "as": "chart", "id": "9", "type": "query", "instanceKey": "tile-viz-9" }
```

A page-placed filter still applies to every tile it maps to, on every page. Scope it with `map` ([controls.md](controls.md#map--per-tile-scoping)). Page and placement mechanics: [containers.md](containers.md).

## Colour has one meaning

- **One meaning per colour across the page:** red = over / lost, amber = at risk, neutral slate or grey = context. Don't reuse red for a series that only means "this year".
- **Always pair colour with a text label** ("At risk", "Over") so the meaning survives greyscale and colour-blind viewing.
- **Set single-series colours explicitly** with `series[].mark._mark_color` + `manual: true` ([visConfig.md](visConfig.md#series-array)). An `automaticVis` chart draws in the default blue, which clashes with a red/amber page.

## Comparing a value with its outcome

To show a value against what it produced (time value vs recognised revenue, budget vs spend), don't overlay or group two bars and make the reader estimate the gap. Either:

- **Stack the parts:** "recovered" + "not recovered", where "not recovered" is a difference measure (`value - outcome`). The bar total is the value and the red segment is the gap. Use `barStacked` / `columnStacked` and title the series with `series[].title.value`.
- **Plot the ratio** (`outcome / value`) as a line on its own chart.

One value axis only; never put the two on `y` and `y2`.

## Shares that sum to 100%

`barStackedPercentage` does not normalise raw measures: stacking raw hours gives an axis that reads 1,600,000%. Model the shares:

1. Define one share measure per segment series (`billable_hours / total_hours`, `non_billable_hours / total_hours`, …), so the series sum to 1 on every bar.
2. Chart the share measures with `barStacked` and pin the value axis:

```jsonc
"x": { "axis": { "domain": { "min": 0, "max": 1 },
                 "label": { "format": { "format": "percent_0" } } } }
```

Check the axis reads 0–100% in a PNG render.

## Legends and axis formats

- **Legend at the bottom:** `config.color.legendPosition: "bottom"`. The values are lowercase; an uppercase value draws the legend over the bars.
- **Rename legend entries** with `series[].title.value`; there is no `series[].label` ([visConfig.md](visConfig.md#series-array)).
- **Axis number format:** `<axis>.axis.label.format.format`, e.g. `"number_0"`, `"gbpcurrency_0"`, `"percent_0"`.

## Titles, subtitles, and KPI height

- **Titles are questions** ("Which teams are absorbing it?", "Is it getting better?").
- **The subtitle is the definition and the window, in one line** ("Hours over budget ÷ budget, open jobs, last 90 days").
- **A KPI tile with a two-line subtitle needs `h` ≥ 22–24.** At `h: 16` the number clipped.

## Scope filters vs viewer controls

- **Fixed scope** (one business unit, open status only) goes in each tile's `query.filters`. Nobody changes it, so it shouldn't take a control.
- **At most 5 viewer-facing controls**, each one a viewer would change.
- **A dashboard control replaces a tile-level filter on the same field.** With the control blank the tile shows every row, and with it set the tile shows the control's value only ([controls.md](controls.md#map--per-tile-scoping)). Scope through a different field that has no dashboard control.

## Tiles an alert can watch

An alert is a schedule with a condition on one tile (set up in `omni-content-explorer` → *Alerts*). The tile decides whether the alert is useful:

- **Categorical columns only** (item, owner, band), filtered to the rows at the threshold. The tile then changes only when a row enters, leaves, or changes band, so a `RESULTS_CHANGED` alert fires on real change. A numeric column changes on every run, so the alert fires daily.
- **Keep the list short.** An alert that lists 50 or more rows every run gets ignored. Filter to the rows someone should act on (a threshold, a recent window such as "crossed 100% in the last 14 days", or a minimum size), and aim for about 10 rows or fewer on a normal day.
- **Name the condition in the subtitle** ("Alert: Results changed, daily"), so whoever sets the alert picks the right one. `RESULTS_CHANGED` suits a watchlist; `RESULTS_PRESENT` suits an exception list that should normally be empty.
- **Put alertable lists on their own page,** with their optional filters (for example "only my jobs") next to them. The alert keeps the filter values set when it is created.

## Checklist before publishing

- [ ] At-risk before lost; an owner on every row
- [ ] No table over 5 columns; no truncated headers in the PNG
- [ ] Every row limit fits its tile and is named in the subtitle
- [ ] Names and key numbers in markdown use `.value`
- [ ] Every date filter is relative; no month names in titles or labels
- [ ] Each colour means one thing and has a text label
- [ ] Outliers sit in a check tile, not the main list
- [ ] Fixed scope in tile filters; 5 or fewer viewer controls
