# Omni → Databricks Metric View: Field Mapping Reference

---

## Dimensions

### Standard string/number dimension

```yaml
# Omni
city:
  sql: '"CITY"'
  label: City
  description: Customer's city
  synonyms: [ municipality, location city, town ]
  type: string
```
```yaml
# Metric View output
dimensions:
  - name: city
    expr: CITY
    display_name: "City"
    comment: "Customer's city"
    synonyms: [ municipality, location city, town ]
```

---

### Date / timestamp dimension

```yaml
# Omni
created_at:
  sql: '"CREATED_AT"'
  type: time
  label: Created At
```
```yaml
# Metric View output
dimensions:
  - name: created_at
    expr: CREATED_AT
    display_name: "Created At"
    format:
      type: date_time
      date_format: YYYY-MM-DD HH:mm:ss
```

---

### Dimension group (`type: time` with `timeframes`) → one dimension per timeframe

```yaml
# Omni
created_at:
  sql: '"CREATED_AT"'
  type: time
  timeframes: [ date, week, month, quarter, year ]
  label: Created At
```
```yaml
# Metric View output
dimensions:
  - name: created_at_date
    expr: "DATE_TRUNC('DAY', CREATED_AT)"
    display_name: "Created At Date"
    format:
      type: date
      date_format: YYYY-MM-DD

  - name: created_at_week
    expr: "DATE_TRUNC('WEEK', CREATED_AT)"
    display_name: "Created At Week"
    format:
      type: date
      date_format: YYYY-[W]WW

  - name: created_at_month
    expr: "DATE_TRUNC('MONTH', CREATED_AT)"
    display_name: "Created At Month"
    format:
      type: date
      date_format: YYYY-MM

  - name: created_at_quarter
    expr: "DATE_TRUNC('QUARTER', CREATED_AT)"
    display_name: "Created At Quarter"
    format:
      type: date
      date_format: YYYY-[Q]Q

  - name: created_at_year
    expr: "DATE_TRUNC('YEAR', CREATED_AT)"
    display_name: "Created At Year"
    format:
      type: date
      date_format: YYYY
```

**Timeframe → `DATE_TRUNC` unit mapping:**

| Omni timeframe | Databricks expression |
|---|---|
| `date` | `DATE_TRUNC('DAY', col)` |
| `week` | `DATE_TRUNC('WEEK', col)` |
| `month` | `DATE_TRUNC('MONTH', col)` |
| `quarter` | `DATE_TRUNC('QUARTER', col)` |
| `year` | `DATE_TRUNC('YEAR', col)` |
| `hour` | `DATE_TRUNC('HOUR', col)` |
| `day_of_week` | `DAYOFWEEK(col)` |
| `month_num` | `MONTH(col)` |

---

### Group dimension → `CASE WHEN` expression

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
```yaml
# Metric View output
dimensions:
  - name: device_type_groups
    display_name: "Device Type Groups"
    expr: |
      CASE
        WHEN device_type IN ('mobile', 'tablet') THEN 'Handheld'
        WHEN device_type = 'desktop' THEN 'Desktop'
        ELSE 'Other'
      END
```

---

### Bin dimension → `CASE WHEN` range expression

```yaml
# Omni
age_bin:
  sql: ${age}
  bin_boundaries: [ 18, 35, 50, 65 ]
  label: Age Group
```
```yaml
# Metric View output
dimensions:
  - name: age_bin
    display_name: "Age Group"
    expr: |
      CASE
        WHEN age < 18 THEN 'below 18'
        WHEN age >= 18 AND age < 35 THEN '>= 18 and < 35'
        WHEN age >= 35 AND age < 50 THEN '>= 35 and < 50'
        WHEN age >= 50 AND age < 65 THEN '>= 50 and < 65'
        WHEN age >= 65 THEN '65 and above'
        ELSE NULL
      END
```

---

### Duration dimension → `DATEDIFF` expression

```yaml
# Omni
fulfillment_days:
  duration:
    sql_start: ${created_at[date]}
    sql_end: ${delivered_at[date]}
    intervals: [ days ]
  label: Fulfillment Days
```
```yaml
# Metric View output
dimensions:
  - name: fulfillment_days
    display_name: "Fulfillment Days"
    expr: "DATEDIFF(DAY, DATE_TRUNC('DAY', created_at), DATE_TRUNC('DAY', delivered_at))"
```

**Duration interval → `DATEDIFF` unit mapping:**

| Omni interval | Databricks unit |
|---|---|
| `days` | `DAY` |
| `weeks` | `WEEK` |
| `months` | `MONTH` |
| `hours` | `HOUR` |
| `minutes` | `MINUTE` |
| `seconds` | `SECOND` |

---

### Boolean (`type: yesno`) → BOOLEAN dimension

```yaml
# Omni
is_returned:
  sql: '"IS_RETURNED"'
  type: yesno
  description: Whether the item was returned

completed_orders:
  sql: "${status} = 'Complete'"
  type: yesno
  label: Completed Orders
```
```yaml
# Metric View output — BOOLEAN dimensions (not filters, and no data_type field)
dimensions:
  - name: is_returned
    expr: IS_RETURNED
    display_name: "Is Returned"
    comment: "Whether the item was returned"

  - name: completed_orders
    expr: "status = 'Complete'"
    display_name: "Completed Orders"
```

---

## Measures

### Standard measure

```yaml
# Omni
total_sale_price:
  sql: "${sale_price}"
  aggregate_type: sum
  label: Total Sale Price
  description: Total revenue from completed orders
  synonyms: [ Total Revenue, Total Receipts ]
  value_format_name: usd
```
```yaml
# Metric View output
measures:
  - name: total_sale_price
    expr: SUM(sale_price)
    display_name: "Total Sale Price"
    comment: "Total revenue from completed orders"
    synonyms:
      - "Total Revenue"
      - "Total Receipts"
    format:
      type: currency
      currency_code: USD
```

---

### Count / count distinct

```yaml
# Omni
order_count:
  aggregate_type: count
  label: Order Count

unique_users:
  sql: "${user_id}"
  aggregate_type: count_distinct
  label: Unique Users
```
```yaml
# Metric View output
measures:
  - name: order_count
    expr: COUNT(*)
    display_name: "Order Count"

  - name: unique_users
    expr: COUNT(DISTINCT user_id)
    display_name: "Unique Users"
```

---

### Derived / composed measure → use `MEASURE()`

```yaml
# Omni
gross_margin:
  sql: "${total_sale_price} - ${total_cost}"
  label: Gross Margin
  value_format_name: usd

average_order_value:
  sql: "${total_sale_price} / NULLIF(${order_count}, 0)"
  label: Average Order Value
  value_format_name: usd
```
```yaml
# Metric View output — define atomic measures first, then composed
measures:
  - name: gross_margin
    expr: "MEASURE(total_sale_price) - MEASURE(total_cost)"
    display_name: "Gross Margin"
    format:
      type: currency
      currency_code: USD

  - name: average_order_value
    expr: "MEASURE(total_sale_price) / NULLIF(MEASURE(order_count), 0)"
    display_name: "Average Order Value"
    format:
      type: currency
      currency_code: USD
```

---

### Filtered measure → `FILTER (WHERE ...)`

```yaml
# Omni
california_revenue:
  sql: "${sale_price}"
  aggregate_type: sum
  filters:
    users.state:
      is: California

multi_state_revenue:
  sql: "${sale_price}"
  aggregate_type: sum
  filters:
    users.state:
      is: [ New York, New Jersey ]

returned_item_count:
  sql: "${id}"
  aggregate_type: count
  filters:
    is_returned:
      is: true
```
```yaml
# Metric View output
measures:
  - name: california_revenue
    expr: "SUM(sale_price) FILTER (WHERE ecomm__users.state = 'California')"
    display_name: "California Revenue"

  - name: multi_state_revenue
    expr: "SUM(sale_price) FILTER (WHERE ecomm__users.state IN ('New York', 'New Jersey'))"
    display_name: "Multi-State Revenue"

  - name: returned_item_count
    expr: "COUNT(id) FILTER (WHERE is_returned IS TRUE)"
    display_name: "Returned Item Count"
```
