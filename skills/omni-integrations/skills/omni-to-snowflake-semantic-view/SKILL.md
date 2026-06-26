---
name: omni-to-snowflake-semantic-view
description: "Convert an Omni Analytics topic into a Snowflake Semantic View YAML definition. Use this skill whenever someone wants to export Omni metrics to Snowflake, create a Semantic View from an Omni topic, harden BI metrics into the warehouse, or bridge Omni's semantic layer with Snowflake Cortex Analyst."
---

# Omni → Snowflake Semantic View

Converts an Omni topic into a Snowflake Semantic View YAML definition by first exploring the Omni model via API, then translating its definitions into the Snowflake Semantic View format.

---

## Prerequisites

```bash
# Verify the Omni CLI is installed — if not, ask the user to install it
# See: https://github.com/exploreomni/cli#readme
command -v omni >/dev/null || echo "ERROR: Omni CLI is not installed."
```

```bash
# Show available profiles and select the appropriate one
omni config show
# If multiple profiles exist, ask the user which to use, then switch:
omni config use <profile-name>

# Confirm the active profile is authenticated and inspect your permissions:
omni whoami whoami
```

> **Auth**: a profile authenticates with an **API key** or **OAuth**. If `whoami` (or any call) returns **401**, hand off — ask the user to run `! omni config login <profile>` (OAuth 2.1 browser flow; it blocks ~2 min on the browser). Don't run `config login` yourself in a headless/CI session (no browser → timeout); on a local interactive machine you *may*. See the **`omni-api-conventions`** rule for profile setup (`omni config init --auth oauth`) and discovering request-body shapes with `--schema`.

---

> **Tip**: Use `-o json` to force structured output for programmatic parsing, or `-o human` for readable tables. The default is `auto` (human in a TTY, JSON when piped).

## Runtime Environment Detection

Before starting, determine which environment you are running in — this controls how SQL is executed against Snowflake in Step 7.

### How to detect

Check for the presence of the built-in Snowflake SQL execution capability:

- **Cortex Code** (Snowflake Notebooks / Cortex Analyst): Native SQL execution is available. No extra tooling required.
- **Claude Code, Cursor, or any external IDE/agent**: No native Snowflake connection. You must use one of the CLI options below.

### Detection heuristic

```
If the agent can execute a SQL statement like `SELECT CURRENT_USER()` directly without any shell command → you are in Cortex Code.
Otherwise → you are in an external environment.
```

If unsure, ask the user: _"Are you running this inside Snowflake (Cortex Code / Notebooks), or in an external tool like Claude Code or Cursor?"_

### External environment: Snowflake connectivity options

For **Claude Code, Cursor, or any terminal-based agent**, choose one of the following. Check availability in order:

#### Option A — Snowflake CLI (`snow`) ✅ Recommended

```bash
# Check if available
command -v snow

# Configure a connection (first time)
snow connection add

# Execute SQL
snow sql -q "SELECT CURRENT_USER();" --connection <connection_name>
```

Set a default connection to avoid repeating `--connection` on every call:
```bash
snow connection set-default <connection_name>
```

#### Option B — SnowSQL (classic CLI)

```bash
# Check if available
command -v snowsql

# Execute SQL
snowsql -a <account> -u <user> -q "SELECT CURRENT_USER();"
```

#### Option C — Python (`snowflake-connector-python`)

```bash
pip install snowflake-connector-python
```

```python
import snowflake.connector
conn = snowflake.connector.connect(
    account="<account>",
    user="<user>",
    password="<password>",   # or use key-pair / SSO
    warehouse="<warehouse>",
    database="<database>",
    schema="<schema>",
)
conn.cursor().execute("<SQL here>")
```

> ✋ **STOP** — Confirm the Snowflake connection method with the user before proceeding to Step 7. Record which method is being used so Step 7 generates the correct execution command.

---

## Workflow

### Step 1 — Gather Requirements

Ask the user:
1. Which **Topic** do they want to convert?
2. What should the **Semantic View be named**?
3. Where should it be created in Snowflake (**database** and **schema**)?
4. Which **role** should be granted access to the Semantic View?

> ⚠️ **STOP** — Confirm all four answers before proceeding.

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

#### 2c. Fetch the relationships file

```bash
omni models yaml-get <modelId> --filename relationships
```

#### 2d. Fetch each view file referenced in the topic

For every view in `base_view` and `joins`, fetch its YAML:

```bash
omni models yaml-get <modelId> --filename <view_name>.view
```

> If a view is prefixed with `omni_dbt_`, fetch the file that also starts with `omni_dbt_` (e.g. `omni_dbt_ecomm__order_items.view`).

---

### Step 3 — Identify Tables and Joins

#### Mapping view names to Snowflake tables

The `base_view` in the topic file is the primary table. Convert view names to Snowflake table references:

| `base_view` / join value | Snowflake table |
|---|---|
| `ecomm__order_items` | `ECOMM.ORDER_ITEMS` |
| `omni_dbt_ecomm__order_items` | `ECOMM.ORDER_ITEMS` (strip `omni_dbt_`) |

The `__` separator maps to schema (left) and table name (right). If the schema does not exist in Snowflake, skip that table entirely.

#### Reading the join hierarchy

The `joins` parameter in the topic uses indentation to define the join chain — a table indented beneath another joins into its parent:

```yaml
joins:
  user_order_facts: {}        # skip — this is a derived CTE, not a physical table
  ecomm__users: {}            # joins to base_view (ORDER_ITEMS)
  ecomm__inventory_items:     # joins to base_view (ORDER_ITEMS)
    ecomm__products:          # joins to INVENTORY_ITEMS
      demo__product_images: {}           # joins to PRODUCTS
      ecomm__distribution_centers: {}   # joins to PRODUCTS
```

> Skip any view that is a derived table (CTE defined in SQL in Omni). These have no physical Snowflake table to reference.

#### Primary keys

In each view file, find the dimension with `primary_key: true` — this becomes the `unique: true` dimension in the Semantic View.

> ✋ **STOP** — Confirm the table list with the user before continuing.

---

### Step 4 — Resolve the Field List

The topic's `fields` parameter controls which fields from the views are included in the Semantic View.

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

Exclusions (prefixed with `-`) must be applied **after** all inclusions are resolved. The process is:

1. Start with an empty inclusion set
2. Process each entry in `fields` in order:
   - If it is an inclusion rule (`view.*`, `view.field`, `tag:x`) → add matching fields to the set
   - If it is an exclusion rule (`-view.field`) → **remove** that field from the set, even if it was added by a wildcard
3. The final set is the complete list of fields to include in the Semantic View

**Example:**

```yaml
fields:
  - ecomm__order_items.*          # include all order_items fields
  - ecomm__users.country          # include this one users field
  - -ecomm__order_items.cost      # remove cost — excluded even though * was used above
  - -ecomm__order_items.raw_json  # remove raw_json — same reason
```

Result: all `order_items` fields **except** `cost` and `raw_json`, plus `users.country`.

> ⚠️ **Critical:** A `-` exclusion always wins. Never include a field that has been explicitly excluded, regardless of what wildcard included it.

---

### Step 5 — Build Relationships

Using the join hierarchy from Step 3 and the `relationships.yaml` fetched in Step 2c, map each join to a Snowflake Semantic View relationship.

Each entry in `relationships.yaml` looks like:

```yaml
- join_from_view: ecomm__order_items
  join_to_view: ecomm__inventory_items
  join_type: always_left
  on_sql: ${ecomm__order_items.inventory_item_id} = ${ecomm__inventory_items.id}
  relationship_type: assumed_many_to_one
```

The `on_sql` field tells you the join columns. Extract the column names to populate `relationship_columns` in the output.

**Available relationship parameters:**

| Parameter | Description |
|---|---|
| `join_from_view` | Source view the join originates from |
| `join_to_view` | Target view being joined to |
| `join_type` | SQL join type (e.g. `always_left`) |
| `on_sql` | SQL condition — extract column names from this |
| `relationship_type` | Cardinality (e.g. `assumed_many_to_one`) |
| `reversible` | Whether the join is bi-directional |
| `where_sql` | Additional WHERE clause when join is active |

---

### Step 6 — Map Dimensions and Measures

For each view in the resolved field list, translate its Omni field definitions into Semantic View entries.

> ⚠️ Only translate fields that survived the Step 4 inclusion/exclusion resolution. Do not add fields that were excluded.

#### Dimensions → `dimensions` or `time_dimensions`

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

#### Measures → `metrics`

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

#### Filter-Only Fields (Templated Filters)

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

---

#### AI Context → `module_custom_instructions`

If the topic has an `ai_context` parameter, include it as:

```yaml
module_custom_instructions:
  question_categorization: <ai_context value>
```

---

#### Sample Queries → `verified_queries`

Convert each entry under `sample_queries` into a SQL statement for `verified_queries`. Use the `prompt` as the `question` and the `description` as context for writing the SQL.

> ✋ **STOP** — Review all dimensions, measures, and relationships with the user before generating the final output.

---

### Step 7 — Generate and Execute the Semantic View

#### Output YAML structure

```yaml
name: <name>
description: <string>

tables:
  - name: <name>
    description: <string>
    base_table:
      database: <database>
      schema: <schema>
      table: <table name>

    dimensions:
      - name: <name>
        synonyms: [ <string>, ... ]
        description: <string>
        expr: <SQL expression>
        data_type: <data type>
        unique: <boolean>

    time_dimensions:
      - name: <name>
        synonyms: [ <string>, ... ]
        description: <string>
        expr: <SQL expression>
        data_type: <data type>

    facts:
      - name: <name>
        synonyms: [ <string>, ... ]
        description: <string>
        expr: <SQL expression>
        data_type: <data type>

    metrics:
      - name: <name>
        synonyms: [ <string>, ... ]
        description: <string>
        expr: <SQL expression>

    filters:
      - name: <name>
        synonyms: [ <string>, ... ]
        description: <string>
        expr: <SQL expression>

relationships:
  - name: <string>
    left_table: <table>
    right_table: <table>
    relationship_columns:
      - left_column: <column>
        right_column: <column>

metrics:
  - name: <name>
    synonyms: [ <string>, ... ]
    description: <string>
    expr: <SQL expression>

verified_queries:
  - name: <string>
    question: <string>
    sql: <string>
    use_as_onboarding_question: <boolean>
```

> **Valid top-level keys only:** `name`, `description`, `tables`, `relationships`, `metrics`, `verified_queries`, `module_custom_instructions`

---

#### Create the Semantic View

The SQL is the same regardless of environment. The difference is *how* it is executed.

**SQL to run:**

```sql
CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML('<database>.<schema>', $$
<yaml content here>
$$);
```

**Execution by environment:**

| Environment | Command |
|---|---|
| Cortex Code | Execute the SQL directly in the active Snowflake session |
| `snow` CLI | `snow sql -q "CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML(...)"` or write YAML to a temp file and pipe it |
| SnowSQL | `snowsql -a <account> -u <user> -f <sql_file.sql>` |
| Python | `conn.cursor().execute("<sql>")` |

> **Tip for CLI environments:** If the YAML is long, write it to a temporary `.sql` file first and execute the file rather than passing it inline — this avoids shell escaping issues with the `$$` dollar-quoting.

```bash
# snow CLI example with a file
snow sql -f /tmp/create_semantic_view.sql
```

#### Grant access

```sql
GRANT SELECT ON SEMANTIC VIEW <database>.<schema>.<name> TO ROLE <role>;
```

Execute this the same way as the `CREATE` call above, using whichever connection method was established during the Runtime Environment Detection step.

---

## Reference

- [Snowflake Semantic View YAML Spec](https://docs.snowflake.com/en/user-guide/views-semantic/semantic-view-yaml-spec)
- [SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML](https://docs.snowflake.com/en/sql-reference/stored-procedures/system_create_semantic_view_from_yaml)
