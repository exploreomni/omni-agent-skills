---
name: omni-to-databricks-metric-view
description: "Convert an Omni Analytics topic into a Databricks Metric View definition in Unity Catalog. Use this skill whenever someone wants to export Omni metrics to Databricks, create a Metric View from an Omni topic, harden BI metrics into Unity Catalog, or bridge Omni's semantic layer with Databricks AI/BI dashboards and Genie spaces."
---

# Omni → Databricks Metric View

Converts an Omni topic into a Databricks Metric View by first exploring the Omni model via API, then translating its field definitions into the Databricks Metric View embedded YAML format and executing via the Databricks CLI.

---

## Prerequisites

```bash
# Omni CLI
command -v omni >/dev/null || curl -fsSL https://raw.githubusercontent.com/exploreomni/cli/main/install.sh | sh
```

```bash
export OMNI_BASE_URL="https://yourorg.omniapp.co"
export OMNI_API_TOKEN="your-api-key"
```

```bash
# Databricks CLI — verify installed
databricks --version
# List configured profiles
cat ~/.databrickscfg
```

---

## Workflow

### Step 1 — Gather Requirements

Ask the user:

1. Which **Omni topic** do they want to convert? (e.g., `orders`)
2. What is the **Unity Catalog destination**? (`catalog.schema`) (e.g., `main.sales`)
3. What is the **Databricks SQL Warehouse ID**? (run `databricks sql warehouses list` to find it)
4. Is this a **new metric view** or does one already exist at `catalog.schema.[topic_name]_mv`?
5. Which **Databricks CLI profile** to use (optional — only if the user has multiple profiles in `~/.databrickscfg`)?

> ⚠️ **STOP** — Confirm all answers before proceeding. The metric view will be named `[topic_name]_mv` by default (e.g., `orders_mv`).

---

### Step 2 — Explore the Omni Model

#### 2a. Find the model ID

```bash
omni models list --modelkind SHARED
```

Identify the **Shared Model** and note its `id`. Always prefer the Shared Model over Schema or Workbook models.

#### 2b. Fetch the topic file

```bash
omni models yaml-get <modelId> --filename <topic_name>.topic
```

From the topic file extract:
- `base_view` — the primary view/table
- `joins` — the join hierarchy (indentation defines join chain)
- `fields` — inclusion/exclusion rules (if present)
- `always_filter` — any permanent WHERE conditions
- `ai_context` — any AI instructions to carry over as a `comment`
- `sample_queries` — any example queries

#### 2c. Fetch the relationships file

```bash
omni models yaml-get <modelId> --filename relationships
```

#### 2d. Fetch each view file referenced in the topic

For every view in `base_view` and `joins`, fetch its YAML:

```bash
omni models yaml-get <modelId> --filename <view_name>.view
```

> If a view is prefixed with `omni_dbt_`, fetch the file that starts with `omni_dbt_` (e.g., `omni_dbt_ecomm__order_items.view`).

Key things to extract from each view file:
- `sql_table_name` — the underlying Databricks table reference
- `derived_table.sql` — if present, this view is a CTE with no physical table; **skip it**
- All `dimension`, `dimension_group`, `measure`, and `filter` field definitions
- Field-level `label`, `description`, `synonyms`, `hidden`, `type`, `sql`, `value_format_name`, `primary_key`

---

### Step 3 — Identify Tables and Joins

#### Mapping view names to Databricks tables

The `base_view` in the topic file is the primary table. Convert view names to fully-qualified Databricks table references (`catalog.schema.table`):

| Omni `base_view` / join value | Databricks table |
|---|---|
| `ecomm__order_items` | `catalog.ecomm.order_items` |
| `omni_dbt_ecomm__order_items` | `catalog.ecomm.order_items` (strip `omni_dbt_`) |

The `__` separator maps to schema (left) and table name (right). Confirm the catalog prefix with the user. If the schema does not exist in Unity Catalog, skip that table entirely.

#### Reading the join hierarchy

The `joins` parameter in the topic uses indentation to define the join chain — a table indented beneath another joins into its parent:

```yaml
joins:
  user_order_facts: {}          # skip — derived CTE, no physical table
  ecomm__users: {}              # joins to base_view (order_items)
  ecomm__inventory_items:       # joins to base_view (order_items)
    ecomm__products:            # joins to inventory_items
      demo__product_images: {}            # joins to products
      ecomm__distribution_centers: {}    # joins to products
```

> Skip any view backed by a `derived_table` — these have no physical Databricks table to reference in joins.

#### Primary keys

In each view file, find the dimension with `primary_key: true`. Note this field — it should be listed first among dimensions for that table.

> ✋ **STOP** — Confirm the full table list and join hierarchy with the user before continuing.

---

### Step 4 — Resolve the Field List

The topic's `fields` parameter controls which fields are included in the metric view.

#### Field targeting rules

| Syntax | Meaning |
|---|---|
| *(no `fields` parameter)* | Include **all** fields from all views |
| `all_views.*` | Include all fields from all views |
| `view.*` | Include all fields in the named view |
| `tag:<value>` | Include all fields tagged with this value |
| `view.field` | Include this specific field |
| `-view.field` | **Exclude** this specific field |

#### How to apply exclusions correctly

Exclusions (prefixed with `-`) must be applied **after** all inclusions are resolved:

1. Start with an empty inclusion set
2. Process each entry in `fields` in order:
   - Inclusion rule (`view.*`, `view.field`, `tag:x`) → add matching fields to the set
   - Exclusion rule (`-view.field`) → remove that field from the set, even if a wildcard added it
3. The final set is the complete list of fields to translate

**Example:**

```yaml
fields:
  - ecomm__order_items.*          # include all order_items fields
  - ecomm__users.country          # include just this one users field
  - -ecomm__order_items.cost      # remove cost
  - -ecomm__order_items.raw_json  # remove raw_json
```

Result: all `order_items` fields **except** `cost` and `raw_json`, plus `users.country`.

> ⚠️ **Critical:** A `-` exclusion always wins. Never include a field that has been explicitly excluded, regardless of what wildcard added it.

Also remove any field marked `hidden: true` unless it was explicitly included by name.

---

### Step 5 — Build Join Definitions

Using the join hierarchy from Step 3 and `relationships.yaml` from Step 2c, map each join to a Databricks metric view join entry.

Each entry in `relationships.yaml` looks like:

```yaml
- join_from_view: ecomm__order_items
  join_to_view: ecomm__inventory_items
  join_type: always_left
  on_sql: ${ecomm__order_items.inventory_item_id} = ${ecomm__inventory_items.id}
  relationship_type: assumed_many_to_one
```

Extract the column names from `on_sql` and build the `on:` clause. Use the view name as the join `name`.

**Star schema join (single level):**

```yaml
joins:
  - name: ecomm__inventory_items
    source: catalog.ecomm.inventory_items
    'on': source.inventory_item_id = ecomm__inventory_items.id
```

**Snowflake schema join (multi-hop):**

```yaml
joins:
  - name: ecomm__inventory_items
    source: catalog.ecomm.inventory_items
    'on': source.inventory_item_id = ecomm__inventory_items.id
    joins:
      - name: products
        source: catalog.ecomm.products
        'on': ecomm__inventory_items.product_id = products.id
```

> ⚠️ `on` is a YAML 1.1 reserved word (boolean `true`) — **always single-quote the key** as `'on':`. The value does NOT need quoting unless it contains a colon. Skip any join to a table that contains `MAP` type columns — they are unsupported.

> ⚠️ **Nested join column references are not supported in `expr`.** Databricks metric views only allow `join_name.column` references for **direct star joins** (1 level deep). Columns from nested (snowflake) joins cannot be used in dimension or measure `expr` fields. To expose product-level dimensions from a snowflake schema, prefer a source view that already has those fields denormalized (e.g., an `inventory_items` view with `product_name`, `product_category`, etc.) and join that directly instead of chaining through a products table.

---

### Step 6 — Map Dimensions and Measures

For each field that survived Step 4, translate it from Omni's format into Databricks Metric View YAML.

> ⚠️ Only translate fields that survived the Step 4 inclusion/exclusion resolution. Do not add excluded fields.

---

#### Dimensions

The field `label` becomes `display_name`. Carry `description` and `synonyms` directly. The `sql` expression (with Omni's `${view.column}` refs stripped to bare column names) becomes `expr`.

---

**Standard string/number dimension:**

```yaml
# Omni view YAML
city:
  sql: '"CITY"'
  label: City
  description: Customer's city
  type: string
```
```yaml
# Metric View output
dimensions:
  - name: city
    expr: CITY
    display_name: "City"
    comment: "Customer's city"
    data_type: STRING
```

---

**Date / timestamp dimension:**

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
    data_type: TIMESTAMP
    format:
      type: DateTime
```

---

**Dimension group** (Omni `type: time` with `timeframes`) → one dimension per timeframe:

```yaml
# Omni
created_at:
  sql: '"CREATED_AT"'
  type: time
  timeframes: [ date, week, month, quarter, year ]
  label: Created At
```
```yaml
# Metric View output — one entry per timeframe
dimensions:
  - name: created_at_date
    expr: "DATE_TRUNC('DAY', CREATED_AT)"
    display_name: "Created At Date"
    data_type: DATE
    format:
      type: Date
      format: YYYY-MM-DD

  - name: created_at_week
    expr: "DATE_TRUNC('WEEK', CREATED_AT)"
    display_name: "Created At Week"
    data_type: DATE

  - name: created_at_month
    expr: "DATE_TRUNC('MONTH', CREATED_AT)"
    display_name: "Created At Month"
    data_type: DATE
    format:
      type: Date
      format: YYYY-MM

  - name: created_at_quarter
    expr: "DATE_TRUNC('QUARTER', CREATED_AT)"
    display_name: "Created At Quarter"
    data_type: DATE

  - name: created_at_year
    expr: "DATE_TRUNC('YEAR', CREATED_AT)"
    display_name: "Created At Year"
    data_type: DATE
    format:
      type: Date
      format: YYYY
```

Timeframe → `DATE_TRUNC` unit mapping:

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
    data_type: STRING
```

---

**Bin dimension** → translate to a `CASE WHEN` range expression:

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
    data_type: STRING
```

---

**Duration dimension** → translate to a `DATEDIFF` expression:

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
    data_type: NUMBER
```

Duration interval → `DATEDIFF` unit mapping:

| Omni interval | Databricks unit |
|---|---|
| `days` | `DAY` |
| `weeks` | `WEEK` |
| `months` | `MONTH` |
| `hours` | `HOUR` |
| `minutes` | `MINUTE` |
| `seconds` | `SECOND` |

---

**Boolean (yes/no) dimension** → becomes a `BOOLEAN` dimension (NOT a filter):

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
# Metric View output — BOOLEAN dimensions, not filters
dimensions:
  - name: is_returned
    expr: IS_RETURNED
    display_name: "Is Returned"
    comment: "Whether the item was returned"
    data_type: BOOLEAN

  - name: completed_orders
    expr: "status = 'Complete'"
    display_name: "Completed Orders"
    data_type: BOOLEAN
```

---

#### Measures

The `sql` field references the source column. Map Omni `aggregate_type` to the appropriate SQL aggregation function.

---

**Standard measure:**

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
      type: Currency
      iso_code: USD
      decimal_places: 2
```

---

**Count / count distinct:**

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
    format:
      type: Number
      decimal_places: 0

  - name: unique_users
    expr: COUNT(DISTINCT user_id)
    display_name: "Unique Users"
    format:
      type: Number
      decimal_places: 0
```

---

**Derived / composed measure** (Omni `type: number` referencing other measures) → use `MEASURE()`:

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
# Metric View output — composed measures using MEASURE() references
measures:
  - name: gross_margin
    expr: "MEASURE(total_sale_price) - MEASURE(total_cost)"
    display_name: "Gross Margin"
    format:
      type: Currency
      iso_code: USD
      decimal_places: 2

  - name: average_order_value
    expr: "MEASURE(total_sale_price) / NULLIF(MEASURE(order_count), 0)"
    display_name: "Average Order Value"
    format:
      type: Currency
      iso_code: USD
      decimal_places: 2
```

> ⚠️ Composed measures must be defined **after** all atomic measures they reference.

---

**Filtered measure** → use the SQL `FILTER (WHERE ...)` clause:

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
    format:
      type: Currency
      iso_code: USD
      decimal_places: 2

  - name: multi_state_revenue
    expr: "SUM(sale_price) FILTER (WHERE ecomm__users.state IN ('New York', 'New Jersey'))"
    display_name: "Multi-State Revenue"

  - name: returned_item_count
    expr: "COUNT(id) FILTER (WHERE is_returned IS TRUE)"
    display_name: "Returned Item Count"
```

---

**Aggregate type → Databricks expression mapping:**

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

#### Format Mapping

| Omni `value_format_name` | Databricks `format` spec |
|---|---|
| `usd` / `usd_0` | `type: Currency, iso_code: USD, decimal_places: 0 or 2` |
| `gbp` | `type: Currency, iso_code: GBP` |
| `eur` | `type: Currency, iso_code: EUR` |
| `percent` | `type: Percentage, decimal_places: 2` |
| `percent_0` | `type: Percentage, decimal_places: 0` |
| `decimal_0` | `type: Number, decimal_places: 0` |
| `decimal_1` | `type: Number, decimal_places: 1` |
| `decimal_2` | `type: Number, decimal_places: 2` |
| `id` | `type: Number, group_separator: false` |
| *(date field)* | `type: Date, format: YYYY-MM-DD` |
| *(datetime field)* | `type: DateTime` |

---

#### AI Context

If the topic has an `ai_context` parameter, carry it into the metric view's top-level `comment` field:

```yaml
# Omni topic
ai_context: "This topic covers completed ecommerce orders. Use order_count for volume and total_sale_price for revenue."
```
```yaml
# Metric View YAML — top-level comment
comment: "This topic covers completed ecommerce orders. Use order_count for volume and total_sale_price for revenue."
```

> ✋ **STOP** — Review all dimensions, measures, and join definitions with the user before generating the final output.

---

### Step 7 — Check for Existing Metric View

```bash
databricks sql execute \
  --warehouse-id <WAREHOUSE_ID> \
  --statement "SHOW VIEWS IN catalog.schema LIKE '%_mv'"
```

- If `[topic_name]_mv` **does not exist** → use `CREATE OR REPLACE VIEW ... WITH METRICS`
- If `[topic_name]_mv` **already exists** → use `ALTER VIEW ... AS $$ ... $$`

---

### Step 8 — Generate the SQL

Assemble the full SQL using the embedded YAML format. Always use `version: 1.1`.

**CREATE (new view):**

```sql
CREATE OR REPLACE VIEW catalog.schema.orders_mv
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
comment: "Metric view for Orders — generated from Omni topic orders"
source: catalog.ecomm.order_items

joins:
  - name: ecomm__users
    source: catalog.ecomm.users
    on: "source.user_id = ecomm__users.id"
  - name: ecomm__inventory_items
    source: catalog.ecomm.inventory_items
    on: "source.inventory_item_id = ecomm__inventory_items.id"
    joins:
      - name: ecomm__products
        source: catalog.ecomm.products
        on: "ecomm__inventory_items.product_id = ecomm__products.id"

dimensions:
  - name: id
    expr: id
    display_name: "Order ID"
    data_type: NUMBER

  - name: status
    expr: status
    display_name: "Order Status"
    data_type: STRING

  - name: created_at_date
    expr: "DATE_TRUNC('DAY', created_at)"
    display_name: "Created At Date"
    data_type: DATE
    format:
      type: Date
      format: YYYY-MM-DD

  - name: created_at_month
    expr: "DATE_TRUNC('MONTH', created_at)"
    display_name: "Created At Month"
    data_type: DATE

  - name: is_returned
    expr: is_returned
    display_name: "Is Returned"
    data_type: BOOLEAN

  - name: country
    expr: ecomm__users.country
    display_name: "Country"
    data_type: STRING

measures:
  - name: order_count
    expr: COUNT(*)
    display_name: "Order Count"
    format:
      type: Number
      decimal_places: 0

  - name: total_sale_price
    expr: SUM(sale_price)
    display_name: "Total Sale Price"
    synonyms:
      - "Total Revenue"
      - "Total Receipts"
    format:
      type: Currency
      iso_code: USD
      decimal_places: 2

  - name: total_cost
    expr: SUM(cost)
    display_name: "Total Cost"
    format:
      type: Currency
      iso_code: USD
      decimal_places: 2

  - name: gross_margin
    expr: "MEASURE(total_sale_price) - MEASURE(total_cost)"
    display_name: "Gross Margin"
    format:
      type: Currency
      iso_code: USD
      decimal_places: 2

  - name: average_order_value
    expr: "MEASURE(total_sale_price) / NULLIF(MEASURE(order_count), 0)"
    display_name: "Average Order Value"
    format:
      type: Currency
      iso_code: USD
      decimal_places: 2
$$
```

**ALTER (existing view):**

```sql
ALTER VIEW catalog.schema.orders_mv
AS $$
version: 1.1
comment: "..."
source: catalog.ecomm.order_items
...
$$
```

---

### Step 9 — Execute via Databricks CLI

`databricks sql execute` does not exist in Databricks CLI v0.295.0+. Use the SQL Statements REST API instead:

```bash
# Write SQL to temp file
cat > /tmp/orders_mv.sql << 'ENDSQL'
CREATE OR REPLACE VIEW catalog.schema.orders_mv
WITH METRICS
LANGUAGE YAML
AS $$
  ... (full YAML body) ...
$$
ENDSQL

# Execute via API (wait_timeout must be between 5s and 50s)
databricks api post /api/2.0/sql/statements \
  --json "{
    \"warehouse_id\": \"<WAREHOUSE_ID>\",
    \"statement\": $(cat /tmp/orders_mv.sql | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'),
    \"wait_timeout\": \"50s\",
    \"catalog\": \"<CATALOG>\",
    \"schema\": \"<SCHEMA>\"
  }"

# With a named profile
databricks api post /api/2.0/sql/statements \
  --profile <PROFILE_NAME> \
  --json "..."
```

Verify the view was created:

```bash
databricks api post /api/2.0/sql/statements \
  --json "{
    \"warehouse_id\": \"<WAREHOUSE_ID>\",
    \"statement\": \"SHOW VIEWS IN catalog.schema LIKE '%_mv'\",
    \"wait_timeout\": \"30s\",
    \"catalog\": \"<CATALOG>\",
    \"schema\": \"<SCHEMA>\"
  }"
```

Grant access:

```bash
databricks api post /api/2.0/sql/statements \
  --json "{
    \"warehouse_id\": \"<WAREHOUSE_ID>\",
    \"statement\": \"GRANT SELECT ON VIEW catalog.schema.orders_mv TO \`group_name\`\",
    \"wait_timeout\": \"30s\",
    \"catalog\": \"<CATALOG>\",
    \"schema\": \"<SCHEMA>\"
  }"
```

---

## Complete YAML Structure Reference

```yaml
version: 1.1                        # always 1.1 (requires Runtime 17.2+)
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
      # currency_code: USD            # for currency type (NOT iso_code)
      # decimal_places: 2           # for number/currency/percentage (integer value)
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
      iso_code: USD
      decimal_places: 2
```

> **Valid top-level keys:** `version`, `comment`, `source`, `filter`, `joins`, `dimensions`, `measures`

---

## Critical Rules

1. **Naming**: Always name the metric view `[topic_name]_mv` (snake_case, lowercase)
2. **CREATE vs ALTER**: Check for existence first — `CREATE OR REPLACE` for new, `ALTER VIEW` for existing
3. **Version**: Always use `version: 1.1` (requires Databricks Runtime 17.2+)
4. **Skip derived CTEs**: Views with `derived_table.sql` and no physical table cannot be sources or joins — skip and warn the user
5. **Confirm before executing**: Show the full generated SQL to the user for review before running the CLI command
6. **Boolean fields**: Map Omni `type: yesno` as BOOLEAN dimensions — **not** filters. Omit `data_type` — it is not a valid YAML field and will cause a parse error
7. **Composed measures**: When an Omni measure's `sql` references other measures (e.g., `${total_revenue} / ${order_count}`), use `MEASURE()` syntax and define atomic measures first
8. **YAML quoting**: `on` is a YAML 1.1 reserved word — **always write the key as `'on':`** (single-quoted). The value does not need quoting unless it contains a colon. Use block scalar (`|`) for multi-line expressions
9. **No SELECT \***: Databricks metric views do not support `SELECT *` — all fields must be explicitly defined
10. **MAP columns**: Skip joins to tables containing `MAP` type columns — not supported
11. **Joined column references**: Only **direct star join** columns (1 level deep) can be referenced in `expr`. Use `join_name.column` (e.g., `ecomm__users.country`). Columns from nested/snowflake joins (2+ levels) cannot be resolved and will error — flatten them through a denormalized direct join instead
12. **Warehouse ID required**: Always confirm the warehouse ID before execution — it cannot be inferred
13. **Exclusions win**: In field resolution, a `-` exclusion always overrides any wildcard inclusion
14. **Format type values are lowercase**: Use `number`, `currency`, `date`, `date_time`, `percentage`, `byte` — not `Number`, `Currency`, `DateTime` etc.
15. **Date/DateTime format requires `date_format`**: `type: date` and `type: date_time` both require a `date_format` sub-field (e.g., `date_format: YYYY-MM-DD`). If you don't need a specific format, omit the entire `format:` block — the type is inferred from the column
16. **ID format field**: Use `hide_group_separator: true` (not `group_separator: false`) under `format: type: number` for ID fields — but only if the underlying column is numeric. Salesforce-style IDs are STRING columns; omit `format:` entirely for string ID fields
17. **CLI execution**: `databricks sql execute` does not exist in CLI v0.295.0+. Use `databricks api post /api/2.0/sql/statements` with `--json`. Pass `catalog` and `schema` in the JSON body. `wait_timeout` must be between `5s` and `50s`
18. **Omni CLI flag**: Use `--filename` (no hyphen), not `--file-name`
19. **Currency format uses `currency_code`**: The correct sub-field is `currency_code: USD`, not `iso_code: USD`
20. **`decimal_places` does not accept integer literals**: Neither `0` nor `1` nor `2` work as plain integers. Omit `decimal_places` entirely — it is unsupported in the current runtime

---

## Reference

- [Databricks Metric Views overview](https://docs.databricks.com/aws/en/metric-views/)
- [Create a metric view with SQL](https://docs.databricks.com/aws/en/metric-views/create/sql)
- [Metric view syntax reference](https://docs.databricks.com/aws/en/metric-views/data-modeling/syntax)
- [Semantic metadata](https://docs.databricks.com/aws/en/metric-views/data-modeling/semantic-metadata)
- [Joins](https://docs.databricks.com/aws/en/metric-views/data-modeling/joins)
- [Composability](https://docs.databricks.com/aws/en/metric-views/data-modeling/composability)
- [Window measures](https://docs.databricks.com/aws/en/metric-views/data-modeling/window-measures)
- [Level of detail](https://docs.databricks.com/aws/en/metric-views/data-modeling/level-of-detail)
