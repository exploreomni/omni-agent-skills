# queryPresentations Reference

Complete reference for v2 tile queryPresentation objects — the keyed-map envelope, parameter tables, the visualization-config nesting, chart type examples, and caveats for reusing tiles from existing dashboards.

In the v2 documents API, tiles live in the `queryPresentations` slice of the document envelope:

```jsonc
"queryPresentations": {
  "data": { "<tileKey>": { /* queryPresentation */ } },
  "order": ["1", "2"]
}
```

Every chart queryPresentation requires: `name`, `prefersChart: true`, a `visConfig` envelope (carrying `chartType` and the nested rendering spec), and a `query` with the full required-field set. The inner rendering-spec shape varies by chart family — the examples below show the exact structure for each.

## Table of Contents

- [Keyed map & order semantics](#keyed-map--order-semantics)
- [Where the visualization config lives](#where-the-visualization-config-lives-read-this-first) — the #1 gotcha
- [v1 → v2 field locations](#v1--v2-field-locations)
- [Key Parameters](#key-parameters)
- [queryPresentation Object Parameters](#querypresentation-object-parameters)
- [Query Object Parameters](#query-object-parameters)
- [chartType values (summary)](#charttype-values-summary)
- [Discovering the Full Structure from Existing Dashboards](#discovering-the-full-structure-from-existing-dashboards)
- [Caveats When Reusing queryPresentations](#caveats-when-reusing-querypresentations)
- [Chart Type Examples](#chart-type-examples)
- [Cartesian Config Fields](#cartesian-config-fields-visconfigvisconfigconfig)
- [Quick Reference: chartType → visType → config](#quick-reference-charttype--vistype--config)

## Keyed map & order semantics

`queryPresentations.data` is a map keyed by string record keys (`"1"`, `"2"`, …); `order` is the tab order and must list every live key. Patches **merge by key** — keys you don't send are untouched.

| Operation | What to send |
|---|---|
| Add a tile | New key in `data` + the key appended to a complete `order` array (+ a `containers` stack so it renders — see [containers.md](containers.md)) |
| Edit a tile | Just that key, with the full tile object — re-author the inner vis config nested under `config` (never echo the flat GET shape) |
| Delete a tile | The key set to `null` in `data` + a complete `order` without it (+ remove its `containers` stack) |
| Reorder tabs | Just `order` |

- **`order` replaces wholesale** — whenever you send it, send the complete array.
- **A single patch can touch at most 48 `data` entries** — batch larger rewrites into multiple patches on the same draft.
- **Tile `"1"` on create merges over a server seed tile** — some seed properties can win over what you sent (`automaticVis: false` came back `true` on tile `"1"` while tile `"2"` kept `false`). Read the document back and re-patch tile `"1"` if its exact fields matter.
- **A multi-tile `v2-create` auto-lays-out only tile `"1"`** — author the full `containers` tree for the rest.

## Where the visualization config lives (read this first)

This is the single most common source of "my chart renders as a table / loses its spec" bugs. A chart is defined by **one queryPresentation-level field**: the `visConfig` envelope.

```json
"visConfig": {
  "chartType": "columnStacked",
  "fields": ["order_items.created_at[quarter]", "order_items.status", "order_items.distinct_order_count"],
  "version": 0,
  "visConfig": {
    "visType": "basic",
    "config": { "configType": "cartesian", "_dependentAxis": "y", "...": "family-specific spec" }
  }
}
```

- `chartType` and `fields` sit at the **outer** `visConfig` level. They are **no longer top-level presentation keys** — the v1 top-level `chartType`/`fields`/`config` are unknown keys and 400.
- The renderer (`visType`) and the rendering spec live in the **inner** `visConfig` — and on write the spec **must be nested under `config`**.

> **Write vs. read asymmetry — the one remaining silent failure.** `v2-get` returns the inner vis config **flat**: the spec keys spread beside `visType`, with no `config` key. A patch that sends that flat shape back **silently keeps only `visType`** and drops everything else (flat-sent `markdownConfig`/`alignment` dropped; `config`-nested persisted). Always re-author the inner spec nested under `config` before writing.

Everything else now fails **loudly** — tile bodies are strict (`additionalProperties: false`), so unknown or misplaced top-level keys return a clean 400:

| What you send | What happens |
|---|---|
| Top-level `chartType`, `fields`, or `config` on the presentation (v1 shape) | **400** "Unrecognized key" |
| `modelId` / `model_extension_id` inside `query` | **Silently rewritten** — the server re-anchors the tile to the document's workbook model (a sent shared-model id reads back as the workbook model). Omit them. |
| `query` missing any required collection field | **400** listing each missing field |
| Inner vis spec sent **flat** (no `config` key) | **Silently dropped** — only `visType` persists |

Set `automaticVis: false` whenever you author an explicit vis config — otherwise the renderer may derive its own chart instead of using your spec.

## v1 → v2 field locations

If you're carrying payloads or muscle memory over from the v1 documents API:

| v1 location | v2 location |
|---|---|
| presentation `chartType` (top level) | `visConfig.chartType` |
| presentation `visConfig.visType` | `visConfig.visConfig.visType` |
| presentation `visConfig.config` (rendering spec) | `visConfig.visConfig.config` on **write**; flattened into `visConfig.visConfig` on **read** |
| presentation `fields` (top-level duplicate of query fields) | gone — only `visConfig.fields` |
| `query.visConfig` (`{ "chartType": … }` hint) | gone — not part of the v2 query schema; the tile is driven entirely by the presentation-level envelope |
| `query.modelId` | gone — server-anchored to the workbook model; a sent value is silently rewritten |

The rendering-spec **content** (mark/series/tooltip/configType/`_dependentAxis`, …) is unchanged from v1 — only the envelope moved.

## Key Parameters

| Parameter | Notes |
|-----------|-------|
| `modelId` | Only at the top level of a `v2-create` body — the **shared** model UUID, not a branchId. Never inside a tile or its query. |
| Field format | `table.field_name` or `table.field_name[week\|month\|day\|quarter\|year]` for time granularity |
| `sorts` | `column_name` must match the **exact field string** (e.g., `"order_items.created_at[month]"`), with `sort_descending` boolean |

## queryPresentation Object Parameters

The allowed tile keys — anything else is a 400:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `name` | Yes | Tile/tab title |
| `type` | **Yes** | Tile kind — omitting it 400s. Dashboard query tiles — **including raw-SQL tiles** — use **`"query"`**; a raw-SQL tile is a `query` tile with `userEditedSQL` set (do **not** use `"sql"` — that is a separate content-item kind, not a dashboard query tile; the renderer reports "Unknown content item type"). Other enum values (`blank`, `csv`, `dataset`, `spreadsheet`, `sql`, `dbt`, `query-view`, `linked`, `app`) are non-query content items. The `containers` slot's child `type` must match — for query tiles it is always `"query"`. |
| `topicName` | Recommended | Topic name for the query — set this whenever querying from a topic. Ensures correct join context in the dashboard. |
| `prefersChart` | Yes (charts) | **Must be `true` to render a chart.** Without it, Omni always shows the results table regardless of any other vis settings. |
| `automaticVis` | Recommended | Set `false` when authoring an explicit vis config (and always for markdown tiles). Seed-tile caveat: tile `"1"` on create can come back `true` — re-patch if it matters. |
| `visConfig` | Yes (charts) | The envelope: `{ chartType, fields, version, visConfig: { visType, config } }` — see above. |
| `query` | Yes | Query definition (see below). |
| `description` | No | Tile description. |
| `subTitle` | No | Tile subtitle. |
| `filterOrder` | No | Ordering of tile-level filters. |
| `isSql` | No | `true` for SQL-mode tiles. |
| `resultConfig` | No | Result display: `columnOrder`, `hiddenColumns`, `columnWidths`, `tableType`, `conditionalFormatters` — see [visConfig.md](visConfig.md). |
| `aiConfig` | No | AI-generated description/subtitle settings — see [visConfig.md](visConfig.md). |
| `sourceQueryPresentationKey` | No | Reference to another tile's key (appears in read-back on derived tiles; not normally authored). |

> *(charts)* in the Required column means the field is required **for chart tiles**; a plain table tile uses `prefersChart: false` and an inner `config: {}`.

### visConfig envelope

| Field | Required | Description |
|-------|----------|-------------|
| `chartType` | Yes (charts) | The chart type enum value (e.g. `"columnStacked"`, `"lineColor"`, `"pie"`, `"kpi"`). See the full list in [visConfig.md](visConfig.md). |
| `fields` | Yes | The fields the visualization uses — mirror `query.fields`. (The v1 top-level duplicate is gone; this is the only copy outside the query.) |
| `version` | Recommended | `0` |
| `visConfig.visType` | Yes (charts) | Renderer: `"basic"` for cartesian/pie/heatmap/boxplot, `"omni-kpi"` for KPI, `"funnel"`, `"sankey"`, `"map"` (point **and** region/choropleth maps), `"omni-table"` for tables. |
| `visConfig.config` | Yes (charts) | The chart rendering spec — **nested under `config` on write** (reads back flat). Per-family shapes in [visConfig.md](visConfig.md). |

## Query Object Parameters

The `query` object follows the [Query API](https://docs.omni.co/api/queries.md) shape, with two v2-specific rules:

1. **Send all twelve fields below** — ten are schema-required and omitting any of those returns a 400 listing each one (empty values are fine for the collections); `limit` and `join_paths_from_topic_name` are technically optional but always send them (an unbounded query and broken topic joins are worse than a 400).
2. **No `modelId` / `model_extension_id`** — the server anchors every tile to the document's workbook model; a sent value is silently rewritten. Omit them.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `table` | Yes | The topic's **base view** (not a joined view) |
| `fields` | Yes | Array of `view.field_name` references (supports timeframe brackets like `[month]`) |
| `limit` | Yes | Row limit |
| `join_paths_from_topic_name` | Yes | The topic name — resolves joins from the topic's base view so joined-view fields work. Set alongside `topicName` on the parent queryPresentation. |
| `sorts` | Yes | Array of `{ "column_name": "...", "sort_descending": bool }` — `[]` fine |
| `filters` | Yes | Object of `{ "field_name": "expression" }` — supports `"last 90 days"`, `"this quarter"`, `">100"`, etc. — `{}` fine |
| `calculations` | Yes | `[]` fine. Each entry = `{ calc_name, sql_expression (an operator AST), known_type:"NUMBER", swallow_errors:true, outside_pivot:false, allow_refs_to_unselected_fields:false, format? }`. **Don't hand-write the `sql_expression` AST — harvest it from an agentic job** (`omni-query` → *Table Calculations*; see below). |
| `column_totals` | Yes | `{}` fine |
| `row_totals` | Yes | `{}` fine |
| `fill_fields` | Yes | `[]` fine |
| `pivots` | Yes | Array of field names to pivot on — a color/stack dimension (e.g. for a stacked chart) **must** be pivoted. `[]` fine |
| `userEditedSQL` | Yes | `""` for a normal semantic tile. Set to a SQL string to make this a **raw-SQL tile** (see below). |

There is no `query.visConfig` in v2 — the v1 `{ "chartType": … }` hint is not part of the schema and does nothing. The tile is driven entirely by the presentation-level `visConfig` envelope.

> **Authoring `calculations` — defer to `omni-query`.** The `sql_expression` AST (operator tree), the operator catalog, and the harvest-don't-hand-write workflow are owned by **`omni-query`** → *Table Calculations* + its `references/table-calculations.md`; don't restate or hand-build them here. **Prefer the agentic path** for any non-trivial calc: `omni ai job-submit`, then lift the `calculations` verbatim from the result's `actions[].generate_query` and validate with `query run` — `omni ai generate-query --run-query=false` is the simple/shape-only fallback. **Content-builder specifics:** a calc **renders in a tile only if its `calc_name` is in both `query.fields` *and* the tile's outer `queryPresentation.fields`**; and in a **markdown** tile, drive geometry from raw **measure** tokens + CSS `calc()` rather than calc tokens (table-calc tokens proved unreliable in markdown tiles — see [mustache.md](mustache.md)).

> **Querying a topic — base view + join path.** Set `table` to the topic's **base view**, pass `join_paths_from_topic_name: <topic>`, and set `topicName` on the parent queryPresentation. Joined-view fields (e.g. `users.state` on an `order_items` topic) resolve through the topic's join map — keep `table` at the base view, not the joined view. For the full mechanics, the omit-it failure mode, and verifying with `omni models get-topic` (`base_view_name`/`join_via_map`), see **`omni-query`**'s *Build queries on a topic*. (For *choosing* which topic, or when to extend/create one, see `omni-query` and `omni-model-builder`.)

### Raw-SQL tiles

A raw-SQL tile is a regular **`type: "query"` tile with `userEditedSQL` set** — *not* a `type: "sql"` content item (that is a different kind and renders as "Unknown content item type" on a dashboard). Put the SQL in `userEditedSQL`; `table` is ignored (the SQL is authoritative). Optionally add `"rewriteSql": false` to run it verbatim or `"dbtMode": true` for Jinja/dbt templating (see **`omni-query`** → *Running Raw SQL* for behavior, the permission gate, and the row cap).

**Two render requirements** — without either, the tile shows "Item missing":
- a real `visConfig` (e.g. the `omni-table` table shape), and
- **`query.fields` populated with the SQL's result column ids** (matching `visConfig.fields`). For a raw-SQL tile this is *not* `[]` — the table needs the columns to display, even though `userEditedSQL` drives the data. Run the SQL once via `omni query run` to read the exact ids (they resolve to `view.col`, e.g. `ecomm__order_items.status`).

```jsonc
"<tileKey>": {
  "name": "Ad-hoc SQL",
  "type": "query",
  "prefersChart": false,
  "automaticVis": false,
  "visConfig": { "chartType": "table", "fields": ["ecomm__order_items.status", "ecomm__order_items.orders"], "version": 0, "visConfig": { "visType": "omni-table", "config": {} } },
  "query": {
    "fields": ["ecomm__order_items.status", "ecomm__order_items.orders"],
    "userEditedSQL": "select status, count(*) as orders from ECOMM.ORDER_ITEMS group by 1",
    "table": "", "limit": 1000, "join_paths_from_topic_name": "",
    "sorts": [], "filters": {}, "calculations": [],
    "column_totals": {}, "row_totals": {}, "fill_fields": [], "pivots": []
  }
}
```

(`join_paths_from_topic_name: ""` — an empty string, never `null`; a `null` 400s on patch.) The tile reads back with `type: "query"`, `isSql: false`, and `userEditedSQL` set — so the **access-warning signal is `userEditedSQL` being populated**, not the tile `type`.

A raw-SQL tile is a **non-topic tile** — it's invisible to Viewer / Restricted Querier roles unless the document has **Access Boost** (dashboard-only; see "Access matters" in the skill body). **End-to-end path** for surfacing a raw-SQL tile to restricted roles (caller needs Manager on the document + the org Access-Boost capability):
1. Author/patch the tile with `userEditedSQL` and publish the draft (`v2-publish-draft`).
2. Verify the tile renders (`omni documents get-queries` → `omni query run`).
3. Access-Boost the document — **`omni-admin`** → *Document Permissions* (`add-permits` with `accessBoost: true` for specific users/groups, or `update-permission-settings` with `organizationAccessBoost: true` for everyone in the org).

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

The most reliable way to learn the exact inner config for a chart family (especially the less common ones) is to build it once in the Omni UI and read it back:

```bash
omni documents v2-get <identifier>
```

Returns the full envelope — `queryPresentations` (`data` keyed map + `order`), `controls`, `containers`, `settings`. Each tile includes `topicName`, the `visConfig` envelope, and the full `query` object — use this as the source of truth when recreating or templating dashboards.

> **Read-back warning:** the inner vis config comes back **flat** (spec keys spread beside `visType`, no `config` key). Before reusing a tile in a create/patch body, re-nest everything except `visType` under `config`. Round-tripping the flat shape silently strips the spec.

## Caveats When Reusing queryPresentations

These apply when copying tiles from an existing document (for both creating new dashboards and updating existing ones):

- **Re-nest the inner vis config** — `visConfig.visConfig` from a GET is flat; move every key except `visType` under a `config` key before writing.
- **Strip `modelId` and `model_extension_id`** from each query object — the server re-anchors tiles to the target document's workbook model and silently rewrites any value you send, so a copied id is at best dead weight.
- **Strip the v1 `query.visConfig` hint** if copying from old v1 exports — it is not part of the v2 query schema.
- **Filter to the tiles you want** — a document's `data` map can include workbook-only tabs not placed on the dashboard. Only carry over (and `order` + lay out) the tiles you want visible.
- **Queries without `topicName` are valid** — SQL-mode and tab-selector queries won't have a `topicName`. Do not add one.
- **Do not save known-broken query-level filters** — if `omni query run` rejects a tile query filter with a server-side parsing error, validate the unfiltered base query once. Do not save the broken filter into the tile; either use a verified dashboard-level control or leave the dashboard unchanged and report the blocker.
- **Bound server-side failures** — if a patch fails with a validation error, stop after one corrected retry; discard the draft and report rather than looping filter rewrites.
- **Check readback for a stripped spec** — after writing, read the tile back (`v2-get` / `v2-get-draft`) and confirm its (flat) inner `visConfig` contains more than just `visType`, and `visConfig.chartType` is set. If only `visType` survived, the write sent the flat shape — re-nest under `config` and retry.

## Period-over-period (current vs previous) in a tile

To show current-vs-previous columns (e.g. a comparison grid, or a "% change" KPI), the query uses **`period_over_period_computations`** + a pivot on the synthetic **`omni_period_pivot`** field (add `"omni_period_pivot"` to `fields` and to `pivots`). Every measure in the query then splits into *Current Period* / *Previous Period* columns. Sorts that target a pivoted measure carry a `pivot_value_map` (e.g. `{"omni_period_pivot":"Current Period"}`).

```jsonc
"period_over_period_computations": [
  { "date_filter_field_name":"view.created_at", "time_unit_name":"MONTH","time_unit":"MONTH","periods_ago":0,"is_dynamic_previous_period":false,"is_ignored":true },
  { "date_filter_field_name":"view.created_at", "time_unit_name":"MONTH","time_unit":"MONTH","periods_ago":1,"is_dynamic_previous_period":false,"is_ignored":false }
]
```

> **PoP pivot tiles render fine — a blank/"No Results" pivot table is almost always (a) wrong render config or (b) an empty period filter, NOT a limitation.** A period-pivot table (`omni_period_pivot` + `period_over_period_computations`) renders Current/Previous columns + a `% Change` calc correctly when the tile is **`visType:"omni-table"`, `automaticVis:true`, `prefersChart:true`** AND the date filter lands on a period that actually has data. A blank or "No Results" almost always means the filtered period is empty (check with `query run` first) — not a render bug. The `% Change` column is a calc with **`outside_pivot:true`** whose operands carry **`pivot_value_map:{omni_period_pivot:"Current Period"|"Previous Period"}`** (e.g. `SAFE_DIVIDE(MINUS(oc@Current, oc@Previous), oc@Previous)`). Note the pivot splits **every** measure into Current/Previous — there's no per-measure opt-in; to compare only a couple, hide the rest.
> **`v2-patch` is stricter than `generate-query` here.** Harvesting the PoP shape from `omni ai generate-query` gives an *ignored* (current-period) entry that omits `time_unit_name`/`time_unit`/`periods_ago` — patching that **400s** (`expected string/number, received undefined`). On write, give **every** entry (ignored one included) all of `time_unit_name`, `time_unit`, and `periods_ago` (use `periods_ago: 0` for the current/ignored entry).

## Chart Type Examples

**Convention:** the first example shows a complete tile in the v2 envelope. Every example after it shows **only the `visConfig` object** — drop it into a tile alongside `name`, `type: "query"`, `topicName`, `prefersChart`, `automaticVis: false`, and a `query` with the full required-field set (query shape called out where it matters, e.g. pivots).

### Complete tile: Line Chart

Time-series or continuous data. `visType: "basic"`, cartesian config, `_dependentAxis: "y"`.

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
    }
  },
  "query": {
    "table": "order_items",
    "fields": ["order_items.created_at[month]", "order_items.total_revenue"],
    "sorts": [{ "column_name": "order_items.created_at[month]", "sort_descending": false }],
    "filters": { "order_items.created_at": "this quarter" },
    "limit": 100,
    "join_paths_from_topic_name": "order_items",
    "calculations": [], "column_totals": {}, "row_totals": {},
    "fill_fields": [], "pivots": [], "userEditedSQL": ""
  }
}
```

### Line chart with multiple series

Add more entries to `series` (in `visConfig.visConfig.config`) and include them in `tooltip`:

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

### Table (Safe Default)

The simplest and most reliable tile. Use when unsure about chart config. Set `prefersChart: false` on the tile; the inner `config` is an empty object.

```json
"visConfig": {
  "chartType": "table",
  "fields": ["order_items.status", "order_items.count", "order_items.total_revenue"],
  "version": 0,
  "visConfig": { "visType": "omni-table", "config": {} }
}
```

### KPI (Single Value)

Displays one or more big numbers. Uses `visType: "omni-kpi"` and `chartType: "kpi"`. No `configType`.

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

### KPI with multiple values

Add more entries to `markdownConfig` (inside `visConfig.visConfig.config`), each with a unique `id`:

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

### Column Chart (Vertical Bars)

Dimension on x-axis, measure on y-axis. `chartType: "column"`, `_dependentAxis: "y"`, `series[].yAxis: "y"`.

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
  }
}
```

### Bar Chart (Horizontal Bars)

Dimension on y-axis, measure on x-axis. `chartType: "bar"`, `_dependentAxis: "x"`, `series[].xAxis: "x"`. Good for ranked lists (Top N).

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
  }
}
```

### Area Chart

Same as a line chart but with `mark.type: "area"` and `chartType: "area"`.

```json
"visConfig": {
  "chartType": "area",
  "fields": ["order_items.created_at[month]", "order_items.total_revenue"],
  "version": 0,
  "visConfig": {
    "visType": "basic",
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
  }
}
```

### Stacked Column Chart (Vertical)

A category/time dimension on x, a measure on y, and a **pivoted** dimension that becomes the stack. `chartType: "columnStacked"`, `color._stack: "stack"` with the pivoted field, `_dependentAxis: "y"`. **The query must pivot the stack dimension**: `"pivots": ["order_items.status"]`. (For a horizontal stacked **bar**, use `chartType: "barStacked"` with `_dependentAxis: "x"` and `series[].xAxis: "x"`. For 100% stacking, use `columnStackedPercentage` / `barStackedPercentage` with `color._stack: "normalize"`.)

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
  }
}
```

### Pie / Donut

`chartType: "pie"`, `visType: "basic"`, inner `config.configType: "polar"`. The category is `theta`; for a donut set `pastry: "donut"` (and optionally `innerRadiusPercent`).

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

## Cartesian Config Fields (`visConfig.visConfig.config`)

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

> For funnel, sankey, map, region map, heatmap, and boxplot, the inner `config` field names are best confirmed by building the chart once in the Omni UI and reading it back (`omni documents v2-get`, re-nesting the flat inner spec under `config`) — see [visConfig.md](visConfig.md) for the known shapes.
