# Databricks Metric View: YAML Reference

---

## Complete YAML Structure

```yaml
version: 1.1                         # always 1.1 (requires Databricks Runtime 17.2+)
comment: "string"                    # top-level description / ai_context

source: catalog.schema.table         # fully-qualified base table

filter: "optional_sql_condition"     # maps to Omni always_filter

joins:
  - name: joined_view_name           # snake_case alias — used to prefix column refs
    source: catalog.schema.table
    'on': source.fk = joined_view_name.pk   # 'on' MUST be single-quoted (YAML reserved word)
    # using:                         # alternative to 'on': for shared key names
    #   - shared_key_col
    joins:                           # nested joins allowed for structure, but...
      - name: deeper_view            # ⚠️ columns from nested joins CANNOT be used in expr
        source: catalog.schema.table
        'on': joined_view_name.fk = deeper_view.pk

dimensions:
  - name: snake_case_name            # required
    expr: column_or_sql_expression   # required — bare column or SQL
                                     # for joined columns: join_name.column (direct joins only)
    display_name: "Human Label"      # from Omni field label
    comment: "description"           # from Omni field description
                                     # NOTE: data_type is NOT a valid field — omit it
    synonyms:                        # from Omni synonyms (max 10, max 255 chars)
      - "alias one"
      - "alias two"
    format:
      type: date                     # date | date_time | number | currency | percentage | byte
                                     # NOTE: all type values are lowercase
      date_format: YYYY-MM-DD        # required for date/date_time types
      # currency_code: USD           # for currency type (NOT iso_code)
      # decimal_places: 2            # unsupported — omit entirely
      # hide_group_separator: true   # for number type (NOT group_separator)

measures:
  - name: snake_case_name
    expr: SUM(column)                # aggregation or MEASURE() composed expression
    display_name: "Human Label"
    comment: "description"
    synonyms:
      - "alias"
    format:
      type: currency
      currency_code: USD
```

> **Valid top-level keys:** `version`, `comment`, `source`, `filter`, `joins`, `dimensions`, `measures`

---

## Aggregate Type Mapping

| Omni `aggregate_type` | Databricks `expr` |
|---|---|
| `sum` | `SUM(col)` |
| `count` | `COUNT(*)` |
| `count_distinct` | `COUNT(DISTINCT col)` |
| `average` | `AVG(col)` |
| `max` | `MAX(col)` |
| `min` | `MIN(col)` |
| `median` | `PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY col)` |
| `list` | *(skip — not supported in metric views)* |

---

## Format Mapping

| Omni `value_format_name` | Databricks `format` spec |
|---|---|
| `usd` / `usd_0` | `type: currency, currency_code: USD` |
| `gbp` | `type: currency, currency_code: GBP` |
| `eur` | `type: currency, currency_code: EUR` |
| `percent` / `percent_0` | `type: percentage` |
| `decimal_0` / `decimal_1` / `decimal_2` | `type: number` |
| `id` (numeric) | `type: number, hide_group_separator: true` |
| `id` (string) | omit `format:` entirely |
| date field | `type: date, date_format: YYYY-MM-DD` |
| datetime field | `type: date_time, date_format: YYYY-MM-DD HH:mm:ss` |

> ⚠️ `decimal_places` is unsupported — omit it entirely. Use `currency_code` not `iso_code`. All `type` values are lowercase.
