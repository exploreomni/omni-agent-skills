# Mapping Omni Fields to Semantic View Entries

## Contents

- [Dimensions → `dimensions` or `time_dimensions`](#dimensions--dimensions-or-time_dimensions)
- [Measures → `metrics`](#measures--metrics)
- [Filter-Only Fields (Templated Filters)](#filter-only-fields-templated-filters)

## Dimensions → `dimensions` or `time_dimensions`

The field name becomes the dimension name unless a `label` is defined. Carry `description` and `synonyms` directly.

---

**Standard dimension:**

```yaml
# Omni view YAML
city:
  sql: '"CITY"'
  label: City
  description: Customer's city
```
```yaml
# Semantic View output
- name: city
  expr: CITY
  description: Customer's city
  data_type: TEXT
```

---

**Date/timestamp dimension** → use `time_dimensions`:

```yaml
# Omni
created_at:
  sql: '"CREATED_AT"'
  type: time
  label: Created At
```
```yaml
# Semantic View output
time_dimensions:
  - name: created_at
    expr: CREATED_AT
    data_type: TIMESTAMP
```

---

**Group dimension** → translate to a `CASE WHEN` expression:

```yaml
# Omni
device_type_groups:
  sql: ${device_type}
  label: Device Type Groups
  groups:
    - filter:
        is: [ mobile, tablet ]
      name: Handheld
    - filter:
        is: desktop
      name: Desktop
  else: Other
```
```sql
-- expr value
CASE
  WHEN "DEVICE_TYPE" IN ('mobile', 'tablet') THEN 'Handheld'
  WHEN "DEVICE_TYPE" = 'desktop' THEN 'Desktop'
  ELSE 'Other'
END
```

---

**Bin dimension** → translate to a `CASE WHEN` range expression:

```yaml
# Omni
age_bin:
  sql: ${age}
  bin_boundaries: [ 18, 35, 50, 65 ]
```
```sql
-- expr value
CASE
  WHEN "AGE" < 18 THEN 'below 18'
  WHEN "AGE" >= 18 AND "AGE" < 35 THEN '>= 18 and < 35'
  WHEN "AGE" >= 35 AND "AGE" < 50 THEN '>= 35 and < 50'
  WHEN "AGE" >= 50 AND "AGE" < 65 THEN '>= 50 and < 65'
  WHEN "AGE" >= 65 THEN '65 and above'
  ELSE NULL
END
```

---

**Duration dimension** → translate to a `TIMESTAMPDIFF` expression:

```yaml
# Omni
fulfillment_days:
  duration:
    sql_start: ${created_at[date]}
    sql_end: ${delivered_at[date]}
    intervals: [ days ]
```
```sql
-- expr value (days)
CASE
  WHEN TIMESTAMPADD(DAY, 1 * TIMESTAMPDIFF(DAY, DATE_TRUNC('DAY', "CREATED_AT"), DATE_TRUNC('DAY', "DELIVERED_AT")), DATE_TRUNC('DAY', "CREATED_AT"))
       <= DATE_TRUNC('DAY', "DELIVERED_AT")
  THEN TIMESTAMPDIFF(DAY, DATE_TRUNC('DAY', "CREATED_AT"), DATE_TRUNC('DAY', "DELIVERED_AT"))
  ELSE TIMESTAMPDIFF(DAY, DATE_TRUNC('DAY', "CREATED_AT"), DATE_TRUNC('DAY', "DELIVERED_AT")) - 1
END
```

---

**Boolean dimension** → becomes a named `filter` (not a dimension):

```yaml
# Omni
is_returned:
  sql: '"IS_RETURNED"'
  description: Whether the item was returned

completed_orders:
  sql: ${status} = 'Complete'
  label: Completed Orders
```
```yaml
# Semantic View output — goes in filters, not dimensions
filters:
  - name: is_returned
    expr: IS_RETURNED
    description: Whether the item was returned
  - name: completed_orders
    expr: STATUS = 'Complete'
    description: Completed Orders
```

---

## Measures → `metrics`

The `sql` field references the source column and `aggregate_type` defines the aggregation.

---

**Standard measure:**

```yaml
# Omni
total_sale_price:
  sql: ${sale_price}
  aggregate_type: sum
  label: Total Sale Price
  description: Total revenue of orders
  synonyms: [ Total Revenue, Total Receipts ]
```
```yaml
# Semantic View output
metrics:
  - name: total_sale_price
    expr: COALESCE(SUM("SALE_PRICE"), 0)
    description: Total revenue of orders
    synonyms: [ Total Revenue, Total Receipts ]
```

---

**Derived measure** (no `aggregate_type`) — references other measures:

```yaml
# Omni
gross_margin:
  sql: ${total_sale_price} - ${total_cost}
  label: Gross Margin
```
```yaml
# Semantic View output — top-level derived metric
metrics:
  - name: gross_margin
    expr: total_sale_price - total_cost
```

---

**Filtered measure** → wraps in `CASE WHEN`:

```yaml
# Omni
california_revenue:
  sql: ${sale_price}
  aggregate_type: sum
  filters:
    users.state:
      is: California
```
```sql
-- expr value
COALESCE(SUM(CASE WHEN "users"."STATE" = 'California' THEN "SALE_PRICE" ELSE NULL END), 0)
```

Array and boolean filter variants:
```yaml
# is: [New York, New Jersey]  →  "STATE" IN ('New York', 'New Jersey')
# is: true                    →  field IS TRUE
```

---

## Filter-Only Fields (Templated Filters)

Filter-only fields in Omni are parameterized inputs defined in a `filters:` block in a view YAML. They don't map to a real column — they inject dynamic values into other fields' SQL at query time via Mustache templates. Snowflake Semantic Views have no equivalent runtime parameter system, so these must be resolved to static SQL during conversion.

**Example filter-only field definition:**

```yaml
# In a view file — under a top-level `filters:` key
filters:
  status_filter:
    type: string
    default_filter:
      is: "Complete"
  order_date_filter:
    type: timestamp
```

---

**Two reference patterns to detect in dimension/measure SQL:**

**Pattern 1 — Block (conditional) syntax:**

```sql
{{# order_items.status_filter.filter }} order_items.status {{/ order_items.status_filter.filter }}
```

The block is conditionally active when the user applies a filter. A `{{^ }}` block is the fallback when no filter is applied:

```sql
{{# order_items.status_filter.filter }} order_items.status {{/ order_items.status_filter.filter }}
{{^ order_items.status_filter.filter }} 1=1 {{/ order_items.status_filter.filter }}
```

**Pattern 2 — Value (direct injection) syntax:**

```sql
-- Direct value substitution
DATE_TRUNC('day', created_at) >= '{{filters.order_items.order_date_filter.value}}'

-- Range variants for date filters
created_at BETWEEN '{{filters.order_items.order_date_filter.range_start}}' AND '{{filters.order_items.order_date_filter.range_end}}'
```

Scan all dimension and measure SQL for both patterns using these signatures:
- `{{# <view>.<field>.filter }}` — block open
- `{{^ <view>.<field>.filter }}` — block fallback open
- `{{filters.<view>.<field>.value}}` — direct value
- `{{filters.<view>.<field>.range_start}}` / `{{filters.<view>.<field>.range_end}}` — date ranges

---

**Resolution logic — apply in order for each reference found:**

**Step 1 — Inline `{{^ }}` fallback (block pattern only):**

If the SQL contains a `{{^ view.field.filter }}` fallback block, use the fallback expression as the static SQL — it's what executes when no filter is applied.

```sql
-- Input
{{# order_items.status_filter.filter }} order_items.status {{/ order_items.status_filter.filter }}
{{^ order_items.status_filter.filter }} 1=1 {{/ order_items.status_filter.filter }}

-- Resolved static SQL
1=1
```

**Step 2 — `default_filter` on the filter field definition:**

Find the referenced filter-only field in the view YAML and check for a `default_filter` property. Render it as a static SQL condition:

| `default_filter` value | Rendered SQL |
|---|---|
| `is: "Complete"` | `field = 'Complete'` |
| `is: ["New York", "CA"]` | `field IN ('New York', 'CA')` |
| `is: true` | `field IS TRUE` |
| `greater_than: 100` | `field > 100` |

For **value syntax**, substitute the rendered scalar value directly into the SQL string:

```sql
-- Input
DATE_TRUNC('day', created_at) >= '{{filters.order_items.order_date_filter.value}}'

-- default_filter: is: "2024-01-01"
-- Resolved
DATE_TRUNC('day', created_at) >= '2024-01-01'
```

For **range syntax**, use `range_start` / `range_end` from the `default_filter` if defined, otherwise warn the user.

**Step 3 — No fallback and no `default_filter` — warn the user:**

> ⚠️ Field `<view>.<field>` references filter-only field `<view>.<filter_field>` but has no `default_filter` and no inline `{{^ }}` fallback. It cannot be statically resolved for a Snowflake Semantic View. Options:
> 1. Skip this field from the output entirely.
> 2. Ask the user what static value or condition to hardcode.
> 3. Use `1=1` (always-true no-op) to preserve the field shape without the filter effect.

**Summary decision tree:**

```
Does the SQL reference a filter-only field?
  (via {{# view.field.filter }} OR {{filters.view.field.value}} etc.)
  │
  ├── Block pattern → Does SQL have {{^ view.field.filter }} fallback?
  │     ├── Yes → Use fallback expression as static SQL
  │     └── No  → Go to default_filter check ↓
  │
  ├── Value pattern → Go to default_filter check ↓
  │
  └── default_filter check:
        ├── Yes → Render default_filter as static SQL / value substitution
        └── No  → Warn user, ask how to proceed
```

> ⚠️ Filter-only fields themselves are **never** emitted as dimensions, metrics, or filters in the Semantic View output — they exist only to parameterize other fields' SQL.
