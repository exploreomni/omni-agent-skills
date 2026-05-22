# YAML Filter Syntax Reference

Complete reference for the filter condition syntax used in Omni model YAML. This syntax applies across three contexts:

- **Measure filters** — `filters:` block on a measure definition
- **Topic always filters** — `always_where_filters:`, `always_having_filters:` on a topic
- **Topic default filters** — `default_filters:` on a topic

## Core Structure

```yaml
<field_name>:
  <operator>: <value>
```

For topic-level filters, always use fully qualified field names (`view_name.field_name`):

```yaml
always_where_filters:
  users.state:
    is: California
```

For measure filters, use the bare field name for fields on the measure's own view. Fields from a joined view must be fully qualified:

```yaml
measures:
  california_revenue:
    aggregate_type: sum
    filters:
      state:             # bare — field is on this view
        is: California
      users.country:     # qualified — field is on a joined view
        is: US
```

## Value Formats

**Strings and dates** — unquoted:
```yaml
contains: Blob
before: 2025-01-01
```

**Arrays** — square bracket syntax:
```yaml
is: [ California, Oregon, Washington ]
between: [ 10, 100 ]
```

**Booleans** — three-state logic:
- `true` — true only
- `false` — false only
- `null` — null only
- `falsey` — false or null

## Negation

Prefix any operator with `not_` to negate it:
```yaml
not_contains: test
not_starts_with: internal
not_between: [ 10, 100 ]
```

**Exceptions:** `and`, `or`, and `is` do not support `not_` prefix. Use the `not` operator instead of `not_is`:
```yaml
not: California
```

**Null checks** — use `not: null` for IS NOT NULL, `is: null` for IS NULL:
```yaml
# IS NOT NULL
some_field:
  not: null

# IS NULL
some_field:
  is: null
```

## Combining Multiple Conditions

Multiple field conditions are AND-combined:
```yaml
filters:
  state:
    is: California
  age:
    greater_than_or_equal_to: 65
```

Use `and` / `or` for multiple conditions on the same field:
```yaml
filters:
  status:
    or:
      - is: complete
      - is: shipped
```

---

## Conditional Operators

| Operator | Description |
|----------|-------------|
| `is` | Exact match |
| `not` | Does not match (use instead of `not_is`) |
| `and` | Rows meeting all specified conditions |
| `or` | Rows meeting at least one condition |

## Numeric Operators

| Operator | Description |
|----------|-------------|
| `greater_than` | `> N` |
| `greater_than_or_equal_to` | `>= N` |
| `less_than` | `< N` |
| `less_than_or_equal_to` | `<= N` |
| `between` | Inclusive range — value is `[ min, max ]` |

### Examples

```yaml
amount:
  greater_than_or_equal_to: 100
```

```yaml
sale_price:
  between: [ 50, 200 ]
```

## String Operators

| Operator | Description |
|----------|-------------|
| `contains` | Contains substring |
| `starts_with` | Starts with substring |
| `ends_with` | Ends with substring |
| `case_insensitive` | Modifier — makes other string operators case-insensitive |

### Examples

```yaml
name:
  contains: Smith
```

```yaml
email:
  not_ends_with: .test
```

## Date & Time Operators

| Operator | Description |
|----------|-------------|
| `before` | Dates before a specified date |
| `on_or_after` | Dates on or after a specified date |
| `between_dates` | Dates within a range |
| `time_for_duration` | Duration starting from a point in time |
| `date_offset_from_query` | Dynamic date relative to workbook query parameters |
| `day_of_week` | Specific day of week |
| `day_of_month` | Specific day of month |
| `day_of_quarter` | Specific day of quarter |
| `day_of_year` | Specific day of year |
| `hour_of_day` | Specific hour of day |
| `month_of_year` | Specific month of year |
| `quarter_of_year` | Specific quarter of year |

### Examples

```yaml
# On or after a fixed date
created_at:
  on_or_after: 2024-01-01
```

```yaml
# Date range (end date is exclusive)
created_at:
  between_dates: [ 2024-01-01, 2024-12-31 ]
```

```yaml
# Before a fixed date
created_at:
  before: 2024-01-01
```

```yaml
# Past 7 days (rolling)
created_at:
  time_for_duration: [ 7 days ago, 7 days ]
```

```yaml
# Past 7 complete days
created_at:
  time_for_duration: [ 7 complete days ago, 7 days ]
```

```yaml
# Duration from a fixed start date
created_at:
  time_for_duration: [ 2024-01-01, 3 months ]
```

```yaml
# Specific day of week (negated)
created_at:
  not_day_of_week: Saturday
```

```yaml
# Specific hour of day (1 = 1:00–1:59 AM)
created_at:
  hour_of_day: 1
```

## Measure Filter Examples

Measure filters use bare field names for fields on the measure's own view, and qualified names (`view.field`) for fields on joined views.

```yaml
measures:
  completed_orders:
    aggregate_type: count
    filters:
      status:           # bare — field is on this view
        is: complete

  california_revenue:
    sql: ${sale_price}
    aggregate_type: sum
    filters:
      state:            # bare — own view
        is: California

  us_orders:
    aggregate_type: count
    filters:
      users.country:    # qualified — field is on a joined view
        is: US

  orders_with_id:       # IS NOT NULL filter
    aggregate_type: count
    filters:
      id:
        not: null
```

## Advanced Operators

| Operator | Description |
|----------|-------------|
| `cancel_query_filter` | Allows a measure to override user query filters with measure-specific values |
| `field_name_in_query` | Filters using results of another query — includes only matching rows |
| `field_name_not_in_query` | Inverse — excludes rows present in the filtering query |
