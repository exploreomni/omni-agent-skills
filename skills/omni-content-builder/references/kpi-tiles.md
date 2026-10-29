# KPI tiles

The native KPI visualization (`chartType: "kpi"`, `visType: "omni-kpi"`): the `markdownConfig` entry types (`number`, `comparison`, `sparkline`, `progress`, `text`, `image`), their `config` shapes, a verified single-value tile, and the caveats. The envelope the config sits in is in [visConfig.md](visConfig.md); markdown KPI cards that follow a control are in [markdown-tiles.md](markdown-tiles.md).

## Table of Contents

- [Config shape](#config-shape)
- [Known-good native KPI tile (verified pattern + caveat checklist)](#known-good-native-kpi-tile-verified-pattern--caveat-checklist)
- [Complete example](#complete-example)

## Config shape

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

## Known-good native KPI tile (verified pattern + caveat checklist)

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

## Complete example

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

