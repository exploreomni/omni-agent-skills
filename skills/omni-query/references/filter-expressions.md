# Filter Expressions Reference

Complete reference for the `filters` object in Omni query API calls (`query run`, and the `query` inside a tile's `queryPresentation`).

`filters` is a map of **`fieldName` → a typed filter object** — the exact shape Omni's UI stores (in a tile's `query.filters` / a dashboard control's `config`) and Omni's AI emits (`ai job-submit` / `generate-query`). Every value is an **object** with a `type` and (for string/number/date) a `kind`:

```json
"filters": {
  "users.state":            { "type": "string", "kind": "EQUALS",       "values": ["California", "New York"] },
  "products.category":      { "type": "string", "kind": "CONTAINS",      "values": ["Jeans"] },
  "order_items.sale_price": { "type": "number", "kind": "GREATER_THAN",  "values": [100] },
  "order_items.created_at": { "type": "date",   "kind": "BEFORE",        "values": ["2024-01-01"] },
  "order_items.shipped_at": { "type": "date",   "kind": "TIME_FOR_INTERVAL_DURATION", "ui_type": "PAST", "left_side": "12 months ago", "right_side": "12 months" },
  "order_items.is_shipped": { "type": "boolean", "is_negative": false },
  "users.email":            { "type": "null",   "is_negative": true }
}
```

> **Do NOT use bare-string shorthand.** `{ "order_items.status": "complete" }` (or `"last 90 days"`, `"not null"`, `123`, `true`) is **rejected**: the API walks every filter value looking for a `query_id` key (the "filter by another query's results" feature) and a non-object value throws `500 "Cannot use 'in' operator to search for 'query_id' in <value>"`. The `filters` map has **always** required object values — bare scalars are never valid.

> **Authoritative source for the full filter union.** `query run --schema` does *not* describe filters (its `query` object is an opaque pass-through). The exhaustive, typed union lives in the **documents** schema at the same path a tile uses:
> ```
> omni documents v2-create --schema --field queryPresentations.data.query.filters
> ```
> It returns a closed `oneOf` of **8 `type`s** — `string`, `number`, `date`, `boolean`, `null`, `composite`, `user_attribute`, `query` — each with its `kind`/`ui_type` enums and required props. It's the same `query.filters` shape `query run` consumes (verified by binding each), and it's future-proof.

## String filters (`type: "string"`)

| `kind` | Meaning | Example value object |
|---|---|---|
| `EQUALS` | match value(s); multiple `values` = match-any (`IN`) | `{ "type":"string", "kind":"EQUALS", "values":["complete","pending"] }` |
| `CONTAINS` | substring | `{ "type":"string", "kind":"CONTAINS", "values":["Smith"] }` |
| `STARTS_WITH` | prefix | `{ "type":"string", "kind":"STARTS_WITH", "values":["A"] }` |
| `ENDS_WITH` | suffix | `{ "type":"string", "kind":"ENDS_WITH", "values":[".com"] }` |
| `SQL_LIKE` | raw SQL `LIKE` pattern | `{ "type":"string", "kind":"SQL_LIKE", "values":["A%n_"] }` |
| `IS_EMPTY` | empty/blank string | `{ "type":"string", "kind":"IS_EMPTY", "values":[] }` |

- Add **`"is_negative": true`** to negate (e.g. *not* equal, *not* contains).
- Add **`"case_insensitive": true`** to ignore case.
- For **null** vs **empty-string**, use a `null`-type filter (below), not `IS_EMPTY`.

## Number filters (`type: "number"`)

| `kind` | Meaning | Example |
|---|---|---|
| `EQUALS` | exactly N | `{ "type":"number", "kind":"EQUALS", "values":[100] }` |
| `GREATER_THAN` | `> N` | `{ "type":"number", "kind":"GREATER_THAN", "values":[100] }` |
| `LESS_THAN` | `< N` | `{ "type":"number", "kind":"LESS_THAN", "values":[1000] }` |
| `BETWEEN` | inclusive range | `{ "type":"number", "kind":"BETWEEN", "values":[50, 200] }` |

`is_negative: true` negates (e.g. `EQUALS` → not-equal).

## Date filters (`type: "date"`)

**Point/range kinds** take `values`:

| `kind` | Meaning | Example |
|---|---|---|
| `BEFORE` | before a date | `{ "type":"date", "kind":"BEFORE", "values":["2024-01-01"] }` |
| `ON_OR_AFTER` | on/after a date | `{ "type":"date", "kind":"ON_OR_AFTER", "values":["2024-01-01"] }` |
| `BETWEEN` | inclusive range | `{ "type":"date", "kind":"BETWEEN", "values":["2024-01-01","2024-12-31"] }` |

**Rolling windows** use `ui_type` + `left_side`/`right_side` (no `values`):

```json
"order_items.created_at": {
  "type": "date", "kind": "TIME_FOR_INTERVAL_DURATION",
  "ui_type": "PAST", "left_side": "12 months ago", "right_side": "12 months"
}
```
- `ui_type`: `PAST`, `BEFORE`, `ON_OR_AFTER`, `ANY_TIME`, `BETWEEN`, `YEAR`, `MONTH_OF_YEAR`, `DAY`, `IS_IN_THE_MONTH`, `IS_IN_THE_QUARTER`, `IS_IN_THE_FISCAL_QUARTER`, `IS_IN_THE_FISCAL_YEAR`, `IS_ON_DAY_OF_WEEK`, `TIME_FOR_INTERVAL_DURATION`, `TIME_FOR_UNIT_DURATION`, `CUSTOM`.
- `kind` for dates also includes the grain-match operators (`IS_ON_DAY_OF_WEEK`, `IS_IN_MONTH_OF_YEAR`, `IS_AT_HOUR_OF_DAY`, `IS_IN_QUARTER_OF_YEAR`, …) and `QUERY_OFFSET` (relative to another query).

## Boolean filters (`type: "boolean"`)

Booleans use **`is_negative`**, *not* `kind`/`values`:

```json
"order_items.is_shipped": { "type": "boolean", "is_negative": false }   // false → is true; true → is false
```
- Optional `"treat_nulls_as_false": true`.
- ⚠️ Do **not** filter a boolean with `{ "type":"string", "kind":"IS_EMPTY", "is_negative":true }` — it compiles to `IS NULL` (the opposite), and `IS_EMPTY` without `values` 400s.

## Null filters (`type: "null"`)

A dedicated type — **not** `string`/`IS_EMPTY` (`IS_EMPTY` is empty-string `= ''`). Works on a regular **dimension** of any type (verified on string and date — the generated `col IS [NOT] NULL` is type-agnostic). `is_negative: true` → `IS NOT NULL`; `false` → `IS NULL`:

```json
"users.email":            { "type": "null", "is_negative": true },    // WHERE … email IS NOT NULL
"order_items.shipped_at": { "type": "null", "is_negative": false }     // WHERE … shipped_at IS NULL   (date dimension)
```

> **On a measure the null check is still applied** (verified by row count). A null-able measure (e.g. an `AVG` → `SUM/NULLIF(COUNT,0)`) binds as `HAVING … IS [NOT] NULL`. A never-null measure (e.g. `COALESCE(SUM(…),0)`) is **constant-folded**: `IS NULL` → empty result (`WHERE 1=0`, 0 rows), `IS NOT NULL` → all rows. Both correct. Aggregate *value* filters bind as `HAVING` (below).

## Composite filters (same-field OR/AND) — `type: "composite"`

Combine multiple conditions **on one field** with OR or AND. The nested `filters` are bare typed filters (no `fieldName`):

```json
"users.state": {
  "type": "composite", "conjunction": "OR",
  "filters": [
    { "type": "string", "kind": "EQUALS", "values": ["Delaware"] },
    { "type": "string", "kind": "EQUALS", "values": ["New Jersey"] }
  ]
}
// → WHERE (STATE = 'Delaware' OR STATE = 'New Jersey')
```
`conjunction` is `"OR"` or `"AND"`. (For simple multi-value equality on one field, the multi-value `EQUALS` array is equivalent.) Composite also works as a **dashboard control** (see below).

## User-attribute filters (row-level personalization) — `type: "user_attribute"`

Bind a field to the **running user's** attribute value (resolves at query time to the caller):

```json
"users.email": { "type": "user_attribute", "user_attribute_name": "omni_user_email" }
// → WHERE EMAIL = '<caller's email>'   (omni_user_email = built-in "current user's email")
```
Add `"is_negative": true` for `!=`. Works standalone in `query run` (resolves to the API key's user).

## Combining filters

Multiple entries are **AND**-combined:

```json
"filters": {
  "order_items.created_at": { "type":"date",   "kind":"TIME_FOR_INTERVAL_DURATION", "ui_type":"PAST", "left_side":"90 days ago", "right_side":"90 days" },
  "order_items.status":     { "type":"string", "kind":"EQUALS", "values":["Complete"] },
  "order_items.sale_price": { "type":"number", "kind":"GREATER_THAN", "values":[50] }
}
```
(created in the last 90 days **AND** status = Complete **AND** sale_price > 50.) Match-any on one field is the multi-value `values` array (`EQUALS` → `IN`).

## Deploying filters in a document → omni-content-builder

This reference covers the filter **shapes** as used in a **single query** (`query run` / a tile's `query.filters`). Everything about how filters and controls live in a **document** is owned by **omni-content-builder**:

- **Tab-level** — cross-field OR (`MULTI_FIELD_FILTER` in a tile's `query.controls`), "is from another query" (`by_query` / `type:"query"`, referencing a sibling tab), and interactive controls (`FIELD_SELECTION`, `TOP_N`, …).
- **Dashboard** — filter controls in `document.controls`, and **wiring controls/filters to tiles**: the per-tile **`map`** scoping (`false` = exclude a tile, `"<fieldName>"` = remap, omit/empty = apply to all by `config.fieldName`) and layout placement (without a content-item a control lands in the HIDDEN CONTROLS tray).

→ [controls.md](../../omni-content-builder/references/controls.md) and [containers.md](../../omni-content-builder/references/containers.md). The filter-value **shapes** those controls carry (string/number/date/boolean/null/composite/user_attribute) are the ones documented above.

## Filtering on measures (→ `HAVING`)

A filter keyed by a **measure** becomes a `HAVING` on the aggregate — comparison/value `kind`s work:

```json
"order_items.total_revenue": { "type": "number", "kind": "GREATER_THAN", "values": [1000] }
// → HAVING COALESCE(SUM(sale_price), 0) > 1000
"order_items.order_count":   { "type": "number", "kind": "GREATER_THAN", "values": [100] }
// → HAVING COUNT(DISTINCT order_id) > 100
```

`type:"null"` on a measure is applied either way. A null-able measure (AVG / ratio) → `HAVING <expr> IS [NOT] NULL` — e.g. `average_order_value` → `(COALESCE(SUM(sale_price),0) / NULLIF(COUNT(DISTINCT order_id),0)) IS NOT NULL`. A never-null measure (`COALESCE(SUM(…),0)`) is constant-folded: `IS NULL` → 0 rows (`WHERE 1=0`), `IS NOT NULL` → all rows.

> **Ratio-measure null trap.** `num / NULLIF(denom, 0)` is SQL-null only when **denom = 0**. Grouping by the denominator's entity (e.g. `orders_per_customer` grouped by `users.id`, where the customer count per group is always 1) makes it never-null → `IS NULL` returns 0 rows. "No activity" is ratio **= 0**, not null — filter `= 0`, not `IS NULL`.

## Two gotchas — always verify a filter *bound*

1. **Malformed object → silently dropped.** A filter object with the wrong properties for its type (e.g. `kind`/`values` on a `boolean`, which needs `is_negative`) is **silently ignored**: the query returns `COMPLETE` but the filter never reaches the SQL. Confirm it bound via `cache: "SkipCache"` → `summary.display_sql` (check the `WHERE`), or that the row count actually changed.
2. **Bare scalar → `500`** (`query_id` error, above).

## Get the exact shape for free — harvest from an agentic job

Omni's AI emits these typed objects exactly. For any non-trivial filter, run `omni ai job-submit <modelId> "<NL prompt that names the filter>"`, then lift `actions[].generate_query.query.filters` verbatim — it's guaranteed-valid (e.g. a "not null" prompt returns `{ "type":"null", "is_negative":true }`).

## Complete query example

```json
{
  "query": {
    "modelId": "your-model-id",
    "table": "order_items",
    "fields": ["order_items.created_at[month]", "order_items.total_revenue", "order_items.count"],
    "filters": {
      "order_items.created_at": { "type": "date",   "kind": "TIME_FOR_INTERVAL_DURATION", "ui_type": "PAST", "left_side": "6 months ago", "right_side": "6 months" },
      "order_items.status":     { "type": "string", "kind": "EQUALS", "values": ["Complete"] },
      "users.state":            { "type": "null",   "is_negative": true }
    },
    "sorts": [{ "column_name": "order_items.created_at[month]", "sort_descending": false }],
    "limit": 100,
    "join_paths_from_topic_name": "order_items"
  },
  "resultType": "csv"
}
```
