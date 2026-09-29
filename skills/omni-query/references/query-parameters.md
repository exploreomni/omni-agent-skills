# Query Parameters Reference

Reference for the `query` object in an `omni query run` body: its parameters, field names, sorts, filters, pivots, and transposed measures, plus common query patterns.

## Contents

- [Query Parameters](#query-parameters)
- [Field Naming](#field-naming)
- [Sorts](#sorts)
- [Filters](#filters)
- [Pivots](#pivots)
- [Transpose measures into rows (`transposed_measures`)](#transpose-measures-into-rows-transposed_measures)
- [Common Query Patterns](#common-query-patterns)

## Query Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `modelId` | **Yes — inside `query`** | UUID of the Omni model (or branch/workbook model id). **Required on every standalone `query run`**; omitting it 400s. Contrast: v2 dashboard **tile** queries omit it entirely. |
| `table` | Conditional | Base view (the `FROM`). Required for a semantic query **unless** `join_paths_from_topic_name` is set (base view comes from the topic) or `userEditedSQL` is used (table ignored). |
| `fields` | Yes | Array of `view.field_name` references |
| `join_paths_from_topic_name` | Recommended | Topic for join resolution |
| `limit` | No | Row limit (default 1000, max 50000, `null` for unlimited) |
| `sorts` | No | Array of sort objects |
| `filters` | No | Filter object |
| `pivots` | No | Array of field names to pivot on |

- **`query run` requires `modelId` INSIDE the `query` object — every time.** A standalone body is `{"query":{"modelId":"<uuid>", …}}`; omit it and the call **400s** with `query.modelId: Invalid input: expected string, received undefined`. This is the **exact opposite** of a v2 **dashboard tile** query (`omni-content-builder`), whose tile query must **never** carry `modelId` (the server anchors tiles to the document's workbook model). Don't let the tile rule bleed into standalone queries — **tiles omit `modelId`; `query run` requires it.** When running against a **branch** or a **workbook/draft model**, set `modelId` to *that* model's id (the branch model id or the draft's `workbookModelId`), not the shared model — and pass `branchId` at the top level only when the skill explicitly calls for it (a branch's own model id already resolves branch fields).

## Field Naming

Fields use `view_name.field_name`. Date fields support timeframe brackets:

```
users.created_at[date]      — Daily
users.created_at[week]      — Weekly
users.created_at[month]     — Monthly
users.created_at[quarter]   — Quarterly
users.created_at[year]      — Yearly
```

## Sorts

```json
"sorts": [
  { "column_name": "order_items.total_revenue", "sort_descending": true }
]
```

## Filters

`query.filters` is a map of **`fieldName` → a typed filter object** — the shape Omni's UI emits (verified against a live dashboard's `filterConfig` and end-to-end via `query run`):

```json
"filters": {
  "users.state":            { "type": "string", "kind": "EQUALS",       "values": ["California", "New York"] },
  "products.category":      { "type": "string", "kind": "CONTAINS",      "values": ["Jeans"] },
  "order_items.sale_price": { "type": "number", "kind": "GREATER_THAN",  "values": [100] },
  "order_items.created_at": { "type": "date",   "kind": "BEFORE",        "values": ["2024-01-01"] },
  "order_items.shipped_at": { "type": "date",   "kind": "TIME_FOR_INTERVAL_DURATION", "ui_type": "PAST", "left_side": "12 months ago", "right_side": "12 months" },
  "order_items.is_shipped": { "type": "boolean", "is_negative": false }
}
```

- **`type`** — `string` / `number` / `date` / `boolean`. **Boolean filters use `is_negative`** (`false` = is true, `true` = is false), *not* `kind`/`values` (+ optional `treat_nulls_as_false`).
- **`kind`** (operator, for string/number/date) — string: `EQUALS`, `CONTAINS`, `STARTS_WITH`, `ENDS_WITH`, `IS_EMPTY`, `SQL_LIKE`; number: `EQUALS`, `GREATER_THAN`, `LESS_THAN`, `BETWEEN`; date: `BEFORE`, `ON_OR_AFTER`, `BETWEEN`, `TIME_FOR_INTERVAL_DURATION`/`TIME_FOR_UNIT_DURATION` (rolling windows), `IS_ON_DAY_OF_WEEK`, … (`QUERY_OFFSET` references another query).
- **`values`** — array of operands: a single value, a list (multi-select `EQUALS`), or `[lo, hi]` for `BETWEEN`. Date **rolling windows** use `left_side`/`right_side` + `ui_type` (e.g. `PAST`) instead of `values`.
- **Verify the filter actually bound.** A filter object with the wrong properties for its type (e.g. `kind`/`values` on a `boolean`, which needs `is_negative`) is **silently ignored** — the query returns `COMPLETE` but the filter never reaches the SQL. Confirm via `cache:"SkipCache"` → `summary.display_sql` (the `WHERE`), or that the row count actually changes. The exact `kind`/`ui_type`/boolean enums live in `omni documents v2-create --schema` (under the filter objects); see also [references/filter-expressions.md](filter-expressions.md).

> **Do NOT use the bare-string shorthand** (`"order_items.status": "complete"`, `"last 90 days"`, `"not null"`). The query API rejects it — `400 "Unable to parse data stream"` as of August 2026, `500 "Cannot use 'in' operator to search for 'query_id' in <value>"` on older builds. The typed object above is the reliable form. *(Reproduced on current Omni for value, date, null-string, number, and boolean forms.)*

## Pivots

```json
{
  "query": {
    "fields": ["order_items.created_at[month]", "order_items.status", "order_items.count"],
    "pivots": ["order_items.status"],
    "join_paths_from_topic_name": "order_items"
  }
}
```

**Pivoted queries reject `limit: null`** — pass an explicit numeric limit (e.g., `5000`). Unlimited is only allowed when `pivots[]` is empty.

## Transpose measures into rows (`transposed_measures`)

Folds several **measures** from one wide row into **long form** — one row per measure — so the measures become a category you can chart against (e.g. a funnel, or a "measures on the axis" bar). `transposed_measures` is an **array of the measure field names** to fold (the same names you put in `fields`), **not a boolean** — passing `true` is silently rejected (`z.array(z.string())`), yielding an empty result.

```json
{
  "query": {
    "table": "order_items",
    "fields": ["order_items.units_sold", "order_items.shipped_items", "order_items.delivered_items"],
    "transposed_measures": ["order_items.units_sold", "order_items.shipped_items", "order_items.delivered_items"],
    "join_paths_from_topic_name": "order_items"
  }
}
```

The result gains three synthetic columns at the first transposed measure's position:
- **`measure_name`** — the measure's field name; **renders as the measure's friendly label** in a viz (e.g. "Units Sold").
- **`measure_order`** — `0, 1, 2, …` in the order listed (the stage order).
- **`measure_value`** — that measure's value for the row.

This is the supported way to build a **funnel from multiple measures** (Omni's funnel needs a stage *dimension* + one measure, not N measures): chart `measure_name` as the stage and `measure_value` as the value. See `omni-content-builder` → *Config Object: Funnel*.

## Common Query Patterns

**Time Series**: fields + date dimension + ascending sort + date filter

**Top N**: fields + metric + descending sort + limit

**Aggregation with Breakdown**: multiple dimensions + multiple measures + descending sort by key metric
