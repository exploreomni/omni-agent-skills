# Table Calculations Reference

Complete reference for authoring the `calculations[]` array in an Omni query spec. Table calculations are post-query computed columns (running totals, % of total, ratios, conditionals) evaluated on the result set after the SQL runs.

## Contents

1. [Wire shape](#1-wire-shape) — the `calc_name` + `sql_expression` object shape
2. [The AST: `SerializedSqlExpr`](#2-the-ast-serializedsqlexpr) — node types (`call`, `field`, literals)
3. [Operator namespaces](#3-operator-namespaces) — `Omni.*` and `SqlStdOperatorTable.*`
4. [Canonical examples](#4-canonical-examples) — ratio, % of total, running total, chained, CASE, moving average, IFS/concat, pivot totals, DATEDIF, SUM_IF, VLOOKUP
5. [Validation rules and gotchas](#5-validation-rules-and-gotchas) — `calc_name` in `fields`, `swallow_errors`, pivot/limit
6. [Authoring strategy](#6-authoring-strategy) — template → compose → harvest-from-agentic-job order

## 1. Wire shape

The query API accepts **one** shape per calculation: an object with `calc_name` + a parsed AST in `sql_expression`. The workbook-frontend `{name, formula}` style is NOT accepted by the query API — it exists only in YAML / UI input layers and is translated to the AST before the query runs.

At execution time, the calc engine wraps the base aggregation query in an outer `SELECT` and emits each calc as a column there. Window-style operators (`OMNI_RUNNING_TOTAL`, `OMNI_OFFSET_MULTI`, `OMNI_PERCENT_OF_TOTAL`, etc.) compile to a SQL `... OVER (...)` clause in that outer layer, so the shared data model never needs window functions to support them.

```ts
type OmniCalculation = {
  calc_name: string                          // required — identifier; becomes the column alias
  sql_expression: SerializedSqlExpr          // required — the AST (see §2)
  label?: string                             // UI display label
  format?: string                            // e.g. "currency_2", "#,##0.00", "0.0%"
  description?: string
  original_formula?: string                  // optional Excel-style source (informational only)
  sql?: string                               // compiled SQL — set by backend; do not author
  outside_pivot?: boolean                    // evaluate outside pivot grouping
  swallow_errors?: boolean                   // true → calc errors become "#ERROR!" cells & the query still COMPLETEs; keep false while authoring/validating (see §5.11, §6.5)
  allow_refs_to_unselected_fields?: boolean  // permit refs to fields not in query.fields
  drill_disabled?: boolean
}
```

**Required pair every time:** `calc_name` + `sql_expression`. Everything else is optional.

### The non-obvious requirement that breaks tiles

`calc_name` MUST also appear in `query.fields` (and, for dashboard tiles, in the outer `queryPresentation.fields`). The calculation is defined in `calculations[]` but only rendered as a column/series when its name is selected. A tile that "lost" its calc is almost always this.

```json
{
  "fields": ["orders.month", "orders.total_revenue", "calc_0"],
  "calculations": [{ "calc_name": "calc_0", "sql_expression": { ... } }]
}
```

## 2. The AST: `SerializedSqlExpr`

```ts
enum SERIALIZED_SQL_EXPR_TYPE {
  FIELD     = 'field',       // reference to a query field or another calc
  LITERAL   = 'literal',     // number, string, boolean, null
  CALL      = 'call',        // function/operator invocation — recursive
  REFERENCE = 'reference',   // column-total / structural ref (rare)
  SQL_TYPE  = 'sql_type',    // type tag for CAST
  SUB_QUERY = 'sub_query',
}
```

Five node shapes you author by hand:

### `call` — operator invocation (the common case)
```json
{ "type": "call", "operator": "<namespace>.<NAME>", "operands": [ /* SerializedSqlExpr[] */ ] }
```

### `field` — reference to a query field or another calc
```json
{ "type": "field", "field_name": "users.count" }
{ "type": "field", "field_name": "calc_0" }                          // ref another calc
{ "type": "field", "field_name": "users.count", "for_calc": true }   // calc-scoped (used by row-window ops)
```

`field_name` is the **fully qualified** model field (`view.field`) or another calc's `calc_name`. Don't use `${...}` templating — that's view-YAML syntax, not calc-AST.

### `literal` — constant
```json
{ "type": "literal", "value": 2 }
{ "type": "literal", "value": "hello" }
{ "type": "literal", "value": null }
{ "type": "literal", "value": 1, "string_value": "1" }   // string_value mirrors value for offsets
```

### `reference` — column total / structural
```json
{ "type": "reference", "column_ref": ["users.count", "column_total"], "is_default_alias_scoped": false }
```

### `sql_type` — used as a CAST operand
```json
{ "type": "sql_type", "type_name_name": "DOUBLE", "precision": 0, "scale": 0 }
```

## 3. Operator namespaces

Operator strings live in two namespaces. Both appear in the same AST.

- **`Omni.*`** — Omni-specific functions and the Excel-formula vocabulary (`OMNI_FX_*`, `OMNI_PERCENT_OF_TOTAL`, `OMNI_OFFSET_MULTI`, `ABSOLUTE_POSITION`, etc.)
- **`SqlStdOperatorTable.*`** — standard Calcite SQL operators (`PLUS`, `MINUS`, `DIVIDE`, `EQUALS`, `CASE`, `CAST`, `AND`, `OR`, `EXTRACT`, comparators, `ROW_NUMBER`, etc.)

Rough rule: things that map cleanly to a SQL operator/keyword live under `SqlStdOperatorTable.*`; the Excel-flavored functions and Omni-only window ops live under `Omni.*`.

### High-confidence operator subset

**Arithmetic / comparison (`Omni.*` Excel-formula form):**
`OMNI_FX_PLUS`, `OMNI_FX_MINUS`, `OMNI_FX_MULTIPLY`, `OMNI_FX_SAFE_DIVIDE`, `OMNI_FX_EQUALS`, `OMNI_FX_NOT_EQUALS`, `OMNI_FX_AMPERSAND` (string concat)

**Arithmetic / comparison (`SqlStdOperatorTable.*`):**
`PLUS`, `MINUS`, `MULTIPLY`, `DIVIDE`, `EQUALS`, `NOT_EQUALS`, `GREATER_THAN`, `GREATER_THAN_OR_EQUAL`, `LESS_THAN`, `LESS_THAN_OR_EQUAL`, `UNARY_MINUS`, `POWER`

**Aggregates over the result set (`Omni.OMNI_FX_*`):**
`SUM`, `COUNT`, `COUNTA`, `AVERAGE`, `MIN`, `MAX`, `MEDIAN`

**Window / cross-row (`Omni.*`):**
`OMNI_PERCENT_OF_TOTAL`, `OMNI_PERCENT_OF_PREVIOUS`, `OMNI_PERCENT_CHANGE_FROM_PREVIOUS`, `OMNI_RUNNING_TOTAL`, `OMNI_RANK`, `OMNI_LEGACY_OFFSET`, `OMNI_OFFSET_MULTI`, `ABSOLUTE_POSITION`, `OMNI_PIVOT_OFFSET`, `OMNI_FX_PIVOT_INDEX`

**Logic (`Omni.*`):**
`OMNI_FX_IFS`, `OMNI_FX_RANK`, `OMNI_FX_VLOOKUP`, `OMNI_FX_XLOOKUP`, `OMNI_FX_TLOOKUP`

**Logic / control (`SqlStdOperatorTable.*`):**
`AND`, `OR`, `NOT`, `CASE`, `CAST`, `EXTRACT`

**Date / string:** `Omni.OMNI_FX_DATEDIF`, `Omni.OMNI_EPOCH`, `Omni.OMNI_FX_TEXT` (Excel `TEXT(value, format)` — formats a value to string with a mask like `"YYYY-MM"` or `"#,##0.00"`; compiles to dialect-appropriate `TO_CHAR(...)`), `SqlStdOperatorTable.TRIM`, `SqlStdOperatorTable.EXTRACT`

**AI (Snowflake/Databricks only):**
`Omni.OMNI_FX_AI_CLASSIFY`, `OMNI_FX_AI_EXTRACT`, `OMNI_FX_AI_COMPLETE`, `OMNI_FX_AI_SENTIMENT`, `OMNI_FX_AI_SUMMARIZE`

### The five "Omni-only" calc templates

Surfaced in the Omni UI as quick-calc templates. Each takes one `field` operand with `for_calc: true`:

- `Omni.OMNI_PERCENT_OF_TOTAL`
- `Omni.OMNI_PERCENT_OF_PREVIOUS`
- `Omni.OMNI_PERCENT_CHANGE_FROM_PREVIOUS`
- `Omni.OMNI_RUNNING_TOTAL` — semantic form (alternatively, the lowered `SUM(OFFSET_MULTI(...))` form below)
- `Omni.OMNI_RANK` (or `Omni.OMNI_FX_RANK`)

## 4. Canonical examples

### 4.1 Ratio: `users.count / 2`

```json
{
  "calc_name": "calc_half",
  "label": "Cohort %",
  "sql_expression": {
    "type": "call",
    "operator": "Omni.OMNI_FX_SAFE_DIVIDE",
    "operands": [
      { "type": "field", "field_name": "users.count" },
      { "type": "literal", "value": 2 }
    ]
  }
}
```

### 4.2 Percent of total

```json
{
  "calc_name": "calc_pct",
  "label": "% of Total",
  "format": "0.0%",
  "sql_expression": {
    "type": "call",
    "operator": "Omni.OMNI_PERCENT_OF_TOTAL",
    "operands": [
      { "type": "field", "field_name": "orders.total_revenue", "for_calc": true }
    ]
  }
}
```

### 4.2a Percent change from previous row

Use the template operator for month-over-month, week-over-week, or any sorted period-over-period percent change. The date dimension must be sorted ascending so "previous" means the prior period.

```json
{
  "calc_name": "mom_pct_change",
  "label": "MoM % Change",
  "format": "0.0%",
  "sql_expression": {
    "type": "call",
    "operator": "Omni.OMNI_PERCENT_CHANGE_FROM_PREVIOUS",
    "operands": [
      { "type": "field", "field_name": "orders.total_revenue", "for_calc": true }
    ]
  }
}
```

For monthly revenue, select fields like `["orders.month", "orders.total_revenue", "mom_pct_change"]` and sort `orders.month` ascending. Do not use the period-comparison pivot (`omni_period_pivot`) when the user asks for a calculated column; it returns current/previous columns rather than a table calc. Do not hand-author `SqlStdOperatorTable.LAG` for this common case; the template operator exists and carries the correct calc semantics.

### 4.3 Running total (lowered form, what `=SUM(B$1:B1)` produces)

```json
{
  "calc_name": "calc_0",
  "label": "Running Total",
  "format": "currency_2",
  "swallow_errors": false,
  "original_formula": "=SUM(B$1:B1)",
  "sql_expression": {
    "type": "call",
    "operator": "Omni.OMNI_FX_SUM",
    "operands": [{
      "type": "call",
      "operator": "Omni.OMNI_OFFSET_MULTI",
      "operands": [
        { "type": "field", "field_name": "orders.total_revenue" },
        { "type": "call", "operator": "Omni.ABSOLUTE_POSITION",
          "operands": [{ "type": "literal", "value": 1, "string_value": "1" }] },
        { "type": "literal", "value": 0, "string_value": "0" },
        { "type": "literal", "value": 1, "string_value": "1" },
        { "type": "literal", "value": 1, "string_value": "1" }
      ]
    }]
  }
}
```

### 4.4 Chained calc — `calc_outer = calc_inner * 10`

```json
[
  {
    "calc_name": "calc_inner",
    "sql_expression": {
      "type": "call", "operator": "Omni.OMNI_FX_SAFE_DIVIDE",
      "operands": [
        { "type": "field", "field_name": "users.count" },
        { "type": "literal", "value": 2 }
      ]
    }
  },
  {
    "calc_name": "calc_outer",
    "sql_expression": {
      "type": "call", "operator": "Omni.OMNI_FX_MULTIPLY",
      "operands": [
        { "type": "field", "field_name": "calc_inner" },
        { "type": "literal", "value": 10 }
      ]
    }
  }
]
```

**Prefer this over inlining.** When one calc's logic depends on another's, reference by `field_name` rather than duplicating the dependent AST inline. The query engine inlines the reference automatically — the compiled SQL is identical — but the named-reference form is smaller, single-source-of-truth, and stays in sync if you later change the source calc.

### 4.5 Conditional — `IF(revenue > 1000, "high", "low")`

Use this simple `CASE` shape only for a binary if/else. For multi-branch bucket
labels such as `High` / `Mid` / `Low`, use the `OMNI_FX_IFS` pattern in section
4.7 so the calc matches Omni's Excel-style table calculation semantics.

```json
{
  "calc_name": "calc_bucket",
  "sql_expression": {
    "type": "call",
    "operator": "SqlStdOperatorTable.CASE",
    "operands": [
      { "type": "call", "operator": "SqlStdOperatorTable.GREATER_THAN",
        "operands": [
          { "type": "field", "field_name": "orders.total_revenue" },
          { "type": "literal", "value": 1000 }
        ]
      },
      { "type": "literal", "value": "high" },
      { "type": "literal", "value": "low" }
    ]
  }
}
```

### 4.6 Moving average — trailing 3 periods

```json
{
  "calc_name": "trailing_3mo_avg",
  "label": "3-Month Trailing Avg",
  "format": "currency_2",
  "sql_expression": {
    "type": "call",
    "operator": "Omni.OMNI_FX_AVERAGE",
    "operands": [{
      "type": "call",
      "operator": "Omni.OMNI_OFFSET_MULTI",
      "operands": [
        { "type": "field", "field_name": "orders.total_revenue" },
        { "type": "literal", "value": -2, "string_value": "-2" },
        { "type": "literal", "value":  0, "string_value":  "0" },
        { "type": "literal", "value":  3, "string_value":  "3" },
        { "type": "literal", "value":  1, "string_value":  "1" }
      ]
    }]
  }
}
```

Compiles to `AVG(total_revenue) OVER (ORDER BY <sort_field> ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)`.

**`OMNI_OFFSET_MULTI` operand positions:**

| Position | Meaning |
|---|---|
| 1 | field reference |
| 2 | window start offset — integer literal, or `Omni.ABSOLUTE_POSITION(N)` for a fixed anchor row |
| 3 | window end offset (`0` = current row) |
| 4 | window size (number of rows in the range) |
| 5 | step |

Cumulative-from-start (running total, §4.3): `(field, ABSOLUTE_POSITION(1), 0, 1, 1)` → `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`.

Trailing N-period window (moving avg/sum/min/max): `(field, -(N-1), 0, N, 1)` → `ROWS BETWEEN (N-1) PRECEDING AND CURRENT ROW`.

Swap the outer aggregator (`OMNI_FX_AVERAGE`, `OMNI_FX_SUM`, `OMNI_FX_MIN`, `OMNI_FX_MAX`, `OMNI_FX_MEDIAN`) for different window aggregates over the same range.

### 4.7 Conditional buckets and formatted labels — `IFS` + `&` + `TEXT`

Classify a value into named buckets, then build a labeled string from two calcs:

```json
[
  {
    "calc_name": "sales_tier",
    "label": "Sales Tier",
    "sql_expression": {
      "type": "call", "operator": "Omni.OMNI_FX_IFS",
      "operands": [
        { "type": "call", "operator": "SqlStdOperatorTable.GREATER_THAN_OR_EQUAL",
          "operands": [
            { "type": "field", "field_name": "orders.total_revenue" },
            { "type": "literal", "value": 1500000, "string_value": "1500000" }
          ]
        },
        { "type": "literal", "value": "High" },
        { "type": "call", "operator": "SqlStdOperatorTable.GREATER_THAN_OR_EQUAL",
          "operands": [
            { "type": "field", "field_name": "orders.total_revenue" },
            { "type": "literal", "value": 800000, "string_value": "800000" }
          ]
        },
        { "type": "literal", "value": "Mid" },
        { "type": "call", "operator": "SqlStdOperatorTable.EQUALS",
          "operands": [
            { "type": "literal", "value": 1, "string_value": "1" },
            { "type": "literal", "value": 1, "string_value": "1" }
          ]
        },
        { "type": "literal", "value": "Low" }
      ]
    }
  },
  {
    "calc_name": "tier_label",
    "label": "Month + Tier",
    "sql_expression": {
      "type": "call", "operator": "Omni.OMNI_FX_AMPERSAND",
      "operands": [
        { "type": "call", "operator": "Omni.OMNI_FX_AMPERSAND",
          "operands": [
            { "type": "call", "operator": "Omni.OMNI_FX_TEXT",
              "operands": [
                { "type": "field", "field_name": "orders.month" },
                { "type": "literal", "value": "YYYY-MM" }
              ]
            },
            { "type": "literal", "value": " — " }
          ]
        },
        { "type": "field", "field_name": "sales_tier" }
      ]
    }
  }
]
```

**`OMNI_FX_IFS` operand pattern** — alternating `(condition, value, condition, value, ...)`. There is no separate "else" operator. For the default branch, pass a tautology like `EQUALS(1, 1)` as the final condition; it compiles to `WHEN TRUE THEN <default>`. Full compiled form: `CASE WHEN ... THEN ... WHEN TRUE THEN <default> ELSE NULL END`.

**`OMNI_FX_AMPERSAND` (string concat `&`) is binary**, not variadic. For three or more pieces, nest: `((a & b) & c)`. The compiler emits null-safe `CONCAT(COALESCE(a, ''), COALESCE(b, ''))` — a NULL operand becomes `''`, not NULL.

**`OMNI_FX_TEXT(value, format)`** — Excel's `TEXT()` for formatting; compiles to dialect-appropriate `TO_CHAR(...)`. Common masks: `"YYYY-MM"`, `"YYYY-MM-DD"`, `"#,##0.00"`, `"0.0%"`.

### 4.8 Running total inside a pivot (engine auto-partitions)

When the query has `pivots[]` set, the template window operators automatically partition by the pivot column — no special configuration needed. Just use the template form with default `outside_pivot: false`:

```json
{
  "calc_name": "segment_running_total",
  "label": "Running Total (per pivot segment)",
  "format": "currency_2",
  "outside_pivot": false,
  "sql_expression": {
    "type": "call",
    "operator": "Omni.OMNI_RUNNING_TOTAL",
    "operands": [
      { "type": "field", "field_name": "orders.total_revenue", "for_calc": true }
    ]
  }
}
```

Compiles (inside a `pivots: ["orders.status"]` query) to:

```sql
SUM(total_revenue) OVER (PARTITION BY "$omni_pivot_col_num" ORDER BY ...
                         ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
```

The auto-partition applies to all five template operators (`OMNI_PERCENT_OF_TOTAL`, `OMNI_PERCENT_OF_PREVIOUS`, `OMNI_PERCENT_CHANGE_FROM_PREVIOUS`, `OMNI_RUNNING_TOTAL`, `OMNI_RANK`). Each pivot column gets its own independent calc series.

**Power-user alternative — `window_call` node.** For partitioning beyond the auto-injected pivot column (e.g., partition by an arbitrary dimension that isn't the pivot key), use a `window_call` node directly. This is a sixth AST shape not in the `SERIALIZED_SQL_EXPR_TYPE` enum from §2 — it maps straight to a SQL window spec:

```json
{
  "type": "window_call",
  "aggregate": {
    "type": "call",
    "operator": "SqlStdOperatorTable.SUM",
    "operands": [{ "type": "field", "field_name": "orders.total_revenue" }]
  },
  "partition_args": [{ "type": "field", "field_name": "orders.status" }],
  "order_by_args":  [{ "type": "field", "field_name": "orders.month" }],
  "is_rows": true,
  "lower_bound": { "type": "literal", "value": {
    "enum_class_name": "org.apache.calcite.sql.SqlWindow$Bound",
    "name": "UNBOUNDED_PRECEDING"
  }},
  "upper_bound": { "type": "literal", "value": {
    "enum_class_name": "org.apache.calcite.sql.SqlWindow$Bound",
    "name": "CURRENT_ROW"
  }}
}
```

Calcite bound enum names: `UNBOUNDED_PRECEDING`, `CURRENT_ROW`, `UNBOUNDED_FOLLOWING` (and numeric forms for explicit row offsets). `is_rows: true` emits `ROWS BETWEEN`; `false` emits `RANGE BETWEEN`. Skip this node and stick with the template form unless you need explicit partition control.

### 4.9 Row total across pivot columns (outside pivot)

To compute a single value per row that aggregates across all pivot columns, set `outside_pivot: true` and wrap an aggregator around `OMNI_PIVOT_OFFSET`:

```json
{
  "calc_name": "row_total_sales",
  "label": "Row Total (across all pivot columns)",
  "format": "currency_2",
  "outside_pivot": true,
  "sql_expression": {
    "type": "call",
    "operator": "Omni.OMNI_FX_SUM",
    "operands": [{
      "type": "call",
      "operator": "Omni.OMNI_PIVOT_OFFSET",
      "operands": [
        { "type": "field", "field_name": "orders.total_revenue" },
        { "type": "literal", "value":  0, "string_value":  "0" },
        { "type": "literal", "value":  0, "string_value":  "0" },
        { "type": "literal", "value":  1, "string_value":  "1" },
        { "type": "literal", "value": 50, "string_value": "50" }
      ]
    }]
  }
}
```

Compiles to:

```sql
SUM(CASE WHEN col_num BETWEEN 1 AND 50 THEN total_revenue ELSE NULL END)
  OVER (PARTITION BY row_num ORDER BY col_num
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)
```

**`OMNI_PIVOT_OFFSET` operand positions** (decoded by analogy with the compiled SQL):

| Position | Meaning |
|---|---|
| 1 | field reference |
| 2 | row-offset start (use `0` for current row only) |
| 3 | row-offset end (use `0` for current row only) |
| 4 | column-index range start, inclusive (`1` = first pivot column) |
| 5 | column-index range end, inclusive (`50` matches Omni's default column cap; raise if you've increased `column_limit`) |

Swap the outer aggregator (`OMNI_FX_SUM`, `OMNI_FX_AVERAGE`, `OMNI_FX_MIN`, `OMNI_FX_MAX`, `OMNI_FX_MEDIAN`) for different row-summary statistics across the pivot columns.

### 4.10 Date diff — `DATEDIF(start, end, "D")`

```json
{
  "calc_name": "days_to_ship",
  "original_formula": "=DATEDIF(A1,B1,\"D\")",
  "sql_expression": {
    "type": "call",
    "operator": "Omni.OMNI_FX_DATEDIF",
    "operands": [
      { "type": "literal", "value": "DAY", "string_value": "DAY" },
      { "type": "field", "field_name": "orders.created_at[date]" },
      { "type": "field", "field_name": "orders.shipped_at[date]" }
    ]
  }
}
```

**Two non-obvious things vs. the Excel source formula:**

1. **Operand order is reordered** — the AST is `[unit, start, end]`, but the Excel formula the user types is `=DATEDIF(start, end, unit)`. The parser swaps the unit to position 1.
2. **Unit is spelled out, not the Excel single-letter code** — `"DAY"`, `"MONTH"`, `"YEAR"` in the AST (with `string_value` mirroring `value`). The Excel codes (`"D"`, `"M"`, `"Y"`, `"MD"`, `"YM"`, `"YD"`) are translated to these names at formula-parse time and are *not* what the query API accepts.

**Operand types matter** — both date operands must resolve to a DATE, not a TIMESTAMP. Use a `[date]`-truncated timeframe (`created_at[date]`) or wrap a timestamp field in a CAST node. A bare timestamp field produces an empty result with `swallow_errors: true` and a Calcite `SqlBasicCall cannot be cast to SqlLiteral` error without it.

### 4.11 Conditional aggregates — `SUMIF`, `COUNTIF`, `AVERAGEIFS`

```json
{
  "calc_name": "complete_revenue",
  "original_formula": "=SUMIF(B:B,\"Complete\",C:C)",
  "sql_expression": {
    "type": "call",
    "operator": "Omni.OMNI_FX_SUM_IF",
    "operands": [
      {
        "type": "call",
        "operator": "Omni.OMNI_OFFSET_MULTI",
        "operands": [
          { "type": "field", "field_name": "orders.status" },
          { "type": "literal", "value": -536870911, "string_value": "-536870911" },
          { "type": "literal", "value": 0,          "string_value": "0" },
          { "type": "literal", "value": 1073741823, "string_value": "1073741823" },
          { "type": "literal", "value": 1,          "string_value": "1" }
        ]
      },
      { "type": "literal", "value": "Complete", "string_value": "Complete" },
      {
        "type": "call",
        "operator": "Omni.OMNI_OFFSET_MULTI",
        "operands": [
          { "type": "field", "field_name": "orders.total_revenue" },
          { "type": "literal", "value": -536870911, "string_value": "-536870911" },
          { "type": "literal", "value": 0,          "string_value": "0" },
          { "type": "literal", "value": 1073741823, "string_value": "1073741823" },
          { "type": "literal", "value": 1,          "string_value": "1" }
        ]
      }
    ]
  }
}
```

**Three things that trip up hand-authoring:**

1. **Operator name has an extra underscore** — `Omni.OMNI_FX_SUM_IF` (not `SUMIF`). Same pattern for `OMNI_FX_COUNT_IF`, `OMNI_FX_AVERAGE_IFS`, `OMNI_FX_MAX_IFS`, `OMNI_FX_MIN_IFS`, `OMNI_FX_COUNT_IFS`, `OMNI_FX_SUM_IFS`. The Excel formula keeps the original spelling — the parser inserts the underscore on the way in.
2. **Range operands wrap the field in a full-column `OMNI_OFFSET_MULTI`** — the magic tuple `(field, -536870911, 0, 1073741823, 1)` is the canonical "entire result-set column" range. Bare `{type:"field"}` is rejected. This same wrapper appears in `RANK`, `VLOOKUP`, `XLOOKUP`, and other cross-row operators — it's the calc engine's representation of a column reference (an Excel `C:C`).
3. **Criterion is an Excel match-string literal**, not a SQL expression — `"Complete"`, `">1000000"`, `"<>0"`, `">=2024-01-01"`. The engine parses the Excel comparison operator. Wrap in a `literal` node with both `value` and `string_value` set to the match string.

**Result semantics**: `SUMIF` returns a single value broadcast across every row of the result set (the window covers all rows). It is **not** a row-grouped conditional aggregate — for that, use `SUM(CASE WHEN cond THEN value END)` instead.

### 4.12 In-result-set lookup — `VLOOKUP`

```json
{
  "calc_name": "lookup_revenue",
  "original_formula": "=VLOOKUP(A1, A:C, 2)",
  "sql_expression": {
    "type": "call",
    "operator": "Omni.OMNI_FX_VLOOKUP",
    "operands": [
      { "type": "literal", "value": null },
      { "type": "field", "field_name": "orders.status" },
      {
        "type": "call",
        "operator": "Omni.OMNI_OFFSET_MULTI",
        "operands": [
          { "type": "field", "field_name": "orders.status" },
          { "type": "literal", "value": -536870911, "string_value": "-536870911" },
          { "type": "literal", "value": 0,          "string_value": "0" },
          { "type": "literal", "value": 1073741823, "string_value": "1073741823" },
          { "type": "literal", "value": 3,          "string_value": "3" }
        ]
      },
      { "type": "literal", "value": 2, "string_value": "2" }
    ]
  }
}
```

For a static lookup key such as "return Complete-status revenue on every row", make the first operand a string literal and set the column number to the revenue column's 1-based position within the range. With `query.fields` ordered as `["orders.status", "orders.total_revenue", "complete_revenue_lookup"]`, the key column is position 1 and revenue is position 2:

```json
{
  "calc_name": "complete_revenue_lookup",
  "original_formula": "=VLOOKUP(\"Complete\", A:B, 2)",
  "sql_expression": {
    "type": "call",
    "operator": "Omni.OMNI_FX_VLOOKUP",
    "operands": [
      { "type": "literal", "value": "Complete", "string_value": "Complete" },
      { "type": "field", "field_name": "orders.status" },
      {
        "type": "call",
        "operator": "Omni.OMNI_OFFSET_MULTI",
        "operands": [
          { "type": "field", "field_name": "orders.status" },
          { "type": "literal", "value": -536870911, "string_value": "-536870911" },
          { "type": "literal", "value": 0,          "string_value": "0" },
          { "type": "literal", "value": 1073741823, "string_value": "1073741823" },
          { "type": "literal", "value": 2,          "string_value": "2" }
        ]
      },
      { "type": "literal", "value": 2, "string_value": "2" }
    ]
  }
}
```

**Formula signature is 3-arg, AST is 4-operand.** `=VLOOKUP(lookup_value, lookup_range, column_number)` decomposes into:

| Operand | Source in formula | Meaning |
|---|---|---|
| 1 | `lookup_value` — `A1` | The value to search for. `A1` (current-row cell ref) compiles to `literal: null`. A static string compiles to `{"type":"literal","value":"Complete"}`. A reference to another field compiles to `{"type":"field","field_name":"..."}`. |
| 2 | first column of `lookup_range` | The lookup KEY column — the field whose values are being searched. For `A:C`, this is the field at column A. |
| 3 | `lookup_range` width | An `OMNI_OFFSET_MULTI` over the same key field where the **5th operand (step) = number of columns in the range**. `A:C` → step `3`. `A:B` → step `2`. |
| 4 | `column_number` | 1-based index into the range, counted from the key column. `2` returns column B (the next field in `query.fields` after the key). |

**This is an in-result-set lookup, not a cross-query lookup.** The range is the calc engine's view of the current result set's column ordering — `column_number` indexes into `query.fields` starting at the key column. There is no way to look up values from a different topic, model, or tile through this operator.

**Self-referential degenerate case** — `=VLOOKUP(A1, A:C, 2)` always finds the current row's own A-value in column A and returns column B unchanged. Useful only as a smoke test; for actual logic you'd use a static lookup key (`=VLOOKUP("Complete", A:C, 2)` → returns the row matching "Complete" on every row) or a reference to a calc that produces the lookup key.

**Observed limitation in some deployments** — a static string lookup key can be
interpreted as a referenced query id, producing an error such as `No referenced
query with id Complete found in query`. When that happens, stop retrying VLOOKUP
operand variants. For "broadcast the Complete-status revenue on every row", use
the `OMNI_FX_SUM_IF` pattern in section 4.11 instead; it is the same result for
status-by-revenue tables and avoids `userEditedSQL`.

**For cross-tile lookups, this operator is the wrong tool.** Use Omni's `XLOOKUP` / `TLOOKUP` (different AST not covered here) or model the lookup as a join in the topic.

## 5. Validation rules and gotchas

1. **`calc_name` uniqueness** — must be unique within `calculations[]`; used as the result column alias.
2. **`calc_name` must be in `query.fields`** — and in the dashboard tile's outer `queryPresentation.fields`. Missing this is the #1 cause of "calc defined but not showing".
3. **Excel name rules** — no colons (`:`). Otherwise lenient.
4. **References to unselected fields** — by default a calc can only reference fields in `query.fields`. Set `allow_refs_to_unselected_fields: true` to relax (useful for AI-generated calcs that pull in implicit measures).
5. **Circular references** — calcs can reference other calcs by `field_name`, but cycles error out.
6. **Cross-row operators are opaque to drill** — `OMNI_PERCENT_OF_TOTAL`, `OMNI_PERCENT_OF_PREVIOUS`, `OMNI_PERCENT_CHANGE_FROM_PREVIOUS`, `OMNI_RUNNING_TOTAL`, `OMNI_RANK`, `OMNI_OFFSET_*`, `OMNI_PIVOT_OFFSET`, `VLOOKUP`/`XLOOKUP`/`TLOOKUP` skip same-row reference extraction. Set `drill_disabled: true` if you want the drill menu suppressed.
7. **`outside_pivot: true`** — evaluates the calc once per pivoted row across the column axis instead of once per pivot segment. Outside-pivot calcs almost always wrap an aggregator (`OMNI_FX_SUM`, `OMNI_FX_AVERAGE`, etc.) around `OMNI_PIVOT_OFFSET` to sweep across the column-index range — see §4.9. Default `false` (engine auto-partitions template operators by pivot column — see §4.8).
8. **Don't author `sql:`** — the backend compiles it; it's read-only output.
9. **YAML vs API asymmetry** — workbook YAML accepts the friendly form `calc_1: { sql: "=SUM(B$1:B1)", label: "..." }` and parses it to the AST on load. The query API and dashboard tile renderers require the AST in `sql_expression` — they do not run the formula→AST translator.
10. **Pivoted queries reject `limit: null`** — when `pivots[]` is non-empty, pass an explicit numeric limit (e.g., `5000`). `null` returns `400 Bad Request: query.limit: Unlimited limit (null) cannot be used with pivoted queries`. Not calc-specific but bites every calc-on-pivot example.
11. **`#ERROR!` cells are a *swallowed error*, not data.** With `swallow_errors: true`, a calc that fails to compile or evaluate stores the literal string `#ERROR!` in its column and the query still returns `COMPLETE` — trivially mistaken for real values, a blank calc, or an engine bug. To get the actual cause, **re-run with `swallow_errors: false` (or omit it)** so the query fails with the real message. The most common trigger is a missing referenced field: a calc with `allow_refs_to_unselected_fields: false` (the default — rule 4) requires *every* field it references to be present in `query.fields`, so a calc that reads e.g. `last_order_date` errors unless that field is selected. Corollary: **when you re-run a calc query you extracted from a document, dashboard tile, or `omni ai` job to verify it, run it _verbatim_** — reducing the field list can drop a field the calc references and manufacture an `#ERROR!`/failure that looks like the calc's fault but is your reduction's.

## 6. Authoring strategy

Constructing arbitrary ASTs from scratch is brittle. Pragmatic order of operations:

1. **Try a named template operator first** for the five canonical cases (`OMNI_PERCENT_OF_TOTAL`, `OMNI_PERCENT_OF_PREVIOUS`, `OMNI_PERCENT_CHANGE_FROM_PREVIOUS`, `OMNI_RUNNING_TOTAL`, `OMNI_RANK`) — single `field` operand with `for_calc: true`.
2. **Compose from primitives** (`OMNI_FX_PLUS`/`MINUS`/`MULTIPLY`/`SAFE_DIVIDE`, `SqlStdOperatorTable.CASE`, `OMNI_FX_IFS`, aggregates) for arithmetic and conditional logic over selected fields.
3. **Harvest the AST from an agentic job when unsure** — for any calc beyond simple arithmetic or template operators, prefer `omni ai job-submit <modelId> "<description of the calc> as a table calculation"` and lift the `calculations` from the result's `actions[].generate_query`, then validate with `omni query run` (see SKILL.md → *Table Calculations*). The agentic path authors calcs that `generate-query` silently drops; `omni ai generate-query <modelId> "<description>" --run-query=false` is the simple/shape-only fallback (it returns the parsed `sql_expression` directly, but for non-trivial calcs it can omit operators). Both reliably produce working operand shapes for less-common operators (`OFFSET_MULTI`, `IFS`, `XLOOKUP`, `TEXT`, AI functions); fall back to the UI + `omni documents get-queries <id>` only when the output is wrong (usually it isn't).
4. **Always** add `calc_name` to `query.fields` (and the outer `queryPresentation.fields` for dashboard tiles).
5. **Keep `swallow_errors: false` (the default) while authoring and validating** so a bad operand fails the query loudly with the real compile/eval message — instead of silently rendering `#ERROR!` cells you might read as data, a blank calc, or an engine bug (see §5.11). Only set `swallow_errors: true` deliberately on a *finalized* tile where per-cell resilience matters (one bad calc shouldn't break the whole table for viewers) — and even then, validate once with it `false` first.

> **What the re-run after an agentic harvest actually checks.** When you harvested from a `job-submit` (step 3), the job **already executed** the calc — its result carries `hasResults`, `totalRowCount`, and a populated `csvResult` with the real computed values; re-running the *identical* query just re-proves that. The reason to re-run is **translation fidelity**: harvesting is a reshape (lift `actions[].generate_query.query`, add `modelId`/`table`/`join_paths_from_topic_name`, strip AI-only keys, later map into a tile's `queryPresentation.fields` + `calculations`), and the job only validated *its* object — not the one you assembled. So re-run **your** artifact with `swallow_errors: false` and **diff the values against the job's `csvResult`**: matching numbers prove the reshape, and a dropped/renamed field is exactly the translation failure that "it ran and returned rows" would miss. (Contrast `generate-query --run-query=false`, which never executes — there the run validates execution itself, not your extraction.)
