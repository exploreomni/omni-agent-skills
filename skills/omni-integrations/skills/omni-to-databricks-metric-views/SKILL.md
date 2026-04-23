---
name: omni-to-databricks-metric-view
description: "Convert an Omni Analytics topic into a Databricks Metric View definition in Unity Catalog. Use this skill whenever someone wants to export Omni metrics to Databricks, create a Metric View from an Omni topic, harden BI metrics into Unity Catalog, or bridge Omni's semantic layer with Databricks AI/BI dashboards and Genie spaces."
---

# Omni → Databricks Metric View

Converts an Omni topic into a Databricks Metric View by exploring the Omni model via API, translating its field definitions into the Databricks Metric View embedded YAML format, and executing via the Databricks CLI.

See [FIELD-MAPPING.md](./references/FIELD-MAPPING.md) for full before/after translation examples and [YAML-REFERENCE.md](./references/YAML-REFERENCE.md) for the complete YAML structure, aggregate type, and format mapping tables.

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
```

```bash
# Databricks CLI — verify installed and check profiles
databricks --version
cat ~/.databrickscfg
```

---

> **Tip**: Use `-o json` to force structured output for programmatic parsing, or `-o human` for readable tables. The default is `auto` (human in a TTY, JSON when piped).

## Workflow

### Step 1 — Gather Requirements

Ask the user:

1. Which **Omni topic** do they want to convert? (e.g., `orders`)
2. What is the **Unity Catalog destination**? (`catalog.schema`) (e.g., `main.sales`)
3. What is the **Databricks SQL Warehouse ID**? (run `databricks sql warehouses list` to find it)
4. Is this a **new metric view** or does one already exist at `catalog.schema.[topic_name]_mv`?
5. Which **Databricks CLI profile** to use (optional — only if the user has multiple profiles)?

> ⚠️ **STOP** — Confirm all answers before proceeding. The metric view will be named `[topic_name]_mv` by default.

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

From the topic file extract: `base_view`, `joins`, `fields`, `always_filter`, `ai_context`, `sample_queries`.

#### 2c. Fetch the relationships file

```bash
omni models yaml-get <modelId> --filename relationships
```

#### 2d. Fetch each view file referenced in the topic

For every view in `base_view` and `joins`:

```bash
omni models yaml-get <modelId> --filename <view_name>.view
```

> If a view is prefixed with `omni_dbt_`, fetch the file starting with `omni_dbt_`. Skip any view backed by `derived_table.sql` — it has no physical table.

---

### Step 3 — Identify Tables and Joins

Map view names to fully-qualified Databricks table references (`catalog.schema.table`):

| Omni view name | Databricks table |
|---|---|
| `ecomm__order_items` | `catalog.ecomm.order_items` |
| `omni_dbt_ecomm__order_items` | `catalog.ecomm.order_items` (strip `omni_dbt_`) |

The `__` separator maps to schema (left) and table (right). Confirm the catalog prefix with the user.

The `joins` indentation defines the join chain — a view indented beneath another joins into its parent:

```yaml
joins:
  user_order_facts: {}          # skip — derived CTE
  ecomm__users: {}              # joins to base_view
  ecomm__inventory_items:       # joins to base_view
    ecomm__products:            # joins to inventory_items
```

Find the dimension with `primary_key: true` in each view — list it first among that table's dimensions.

> ✋ **STOP** — Confirm the full table list and join hierarchy with the user before continuing.

---

### Step 4 — Resolve the Field List

| Syntax | Meaning |
|---|---|
| *(no `fields` parameter)* | Include **all** fields from all views |
| `all_views.*` / `view.*` | Include all fields from all views / named view |
| `tag:<value>` | Include all fields with this tag |
| `view.field` | Include this specific field |
| `-view.field` | **Exclude** this field (always wins over wildcard inclusions) |

Process inclusions first, then apply exclusions. Also remove any field with `hidden: true` unless explicitly included by name.

---

### Step 5 — Build Join Definitions

Using the hierarchy from Step 3 and `relationships.yaml`, extract join columns from `on_sql` and build the `on:` clause. Use the view name as the join `name`.

**Star schema (single-level):**
```yaml
joins:
  - name: ecomm__users
    source: catalog.ecomm.users
    'on': source.user_id = ecomm__users.id
```

**Snowflake schema (multi-hop):**
```yaml
joins:
  - name: ecomm__inventory_items
    source: catalog.ecomm.inventory_items
    'on': source.inventory_item_id = ecomm__inventory_items.id
    joins:
      - name: ecomm__products
        source: catalog.ecomm.products
        'on': ecomm__inventory_items.product_id = ecomm__products.id
```

> ⚠️ `on` is a YAML 1.1 reserved word — **always single-quote the key** as `'on':`. Columns from nested (2+ level) joins **cannot** be used in `expr` — flatten them through a denormalized direct join instead.

---

### Step 6 — Map Dimensions and Measures

For each field that survived Step 4, translate it using the rules below. See [FIELD-MAPPING.md](./references/FIELD-MAPPING.md) for full examples.

**Dimension quick reference:**

| Omni field type | Databricks translation |
|---|---|
| Standard string/number | `expr: COLUMN` |
| `type: time` (no timeframes) | Single timestamp dimension |
| `type: time` + `timeframes` | One `DATE_TRUNC(...)` dimension per timeframe |
| `groups:` | `CASE WHEN ... END` expression |
| `bin_boundaries:` | `CASE WHEN` range expression |
| `duration:` | `DATEDIFF(unit, start, end)` expression |
| `type: yesno` | BOOLEAN dimension (not a filter; omit `data_type`) |

**Measure quick reference:**

| Omni measure type | Databricks translation |
|---|---|
| `aggregate_type: sum/avg/max/min` | `SUM(col)` / `AVG(col)` / etc. |
| `aggregate_type: count` | `COUNT(*)` |
| `aggregate_type: count_distinct` | `COUNT(DISTINCT col)` |
| Derived (refs other measures) | `MEASURE(measure_a) op MEASURE(measure_b)` — define atomics first |
| `filters:` on a measure | `AGG(col) FILTER (WHERE condition)` |

Strip Omni's `${view.column}` refs to bare column names (or `join_name.column` for joined fields). Use `display_name` for the Omni `label`, `comment` for `description`, and carry `synonyms` directly. See [YAML-REFERENCE.md](./references/YAML-REFERENCE.md) for format and aggregate type mapping tables.

If the topic has `ai_context`, carry it into the metric view's top-level `comment`.

> ✋ **STOP** — Review all dimensions, measures, and join definitions with the user before generating the final output.

---

### Step 7 — Check for Existing Metric View

```bash
databricks api post /api/2.0/sql/statements \
  --json "{\"warehouse_id\": \"<WAREHOUSE_ID>\", \"statement\": \"SHOW VIEWS IN <catalog>.<schema> LIKE '%_mv'\", \"wait_timeout\": \"30s\", \"catalog\": \"<CATALOG>\", \"schema\": \"<SCHEMA>\"}"
```

- View **does not exist** → use `CREATE OR REPLACE VIEW ... WITH METRICS`
- View **already exists** → use `ALTER VIEW ... AS $$ ... $$`

---

### Step 8 — Generate and Execute the SQL

Write the SQL to a temp file:

```sql
-- CREATE (new view)
CREATE OR REPLACE VIEW catalog.schema.orders_mv
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
comment: "..."
source: catalog.ecomm.order_items

joins:
  - name: ecomm__users
    source: catalog.ecomm.users
    'on': source.user_id = ecomm__users.id

dimensions:
  - name: id
    expr: id
    display_name: "Order ID"

  - name: status
    expr: status
    display_name: "Order Status"

measures:
  - name: order_count
    expr: COUNT(*)
    display_name: "Order Count"

  - name: total_sale_price
    expr: SUM(sale_price)
    display_name: "Total Sale Price"
    format:
      type: currency
      currency_code: USD
$$
```

```sql
-- ALTER (existing view)
ALTER VIEW catalog.schema.orders_mv AS $$
version: 1.1
...
$$
```

Execute via the SQL Statements API (`databricks sql execute` does not exist in CLI v0.295.0+):

```bash
databricks api post /api/2.0/sql/statements \
  --json "{
    \"warehouse_id\": \"<WAREHOUSE_ID>\",
    \"statement\": $(cat /tmp/orders_mv.sql | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'),
    \"wait_timeout\": \"50s\",
    \"catalog\": \"<CATALOG>\",
    \"schema\": \"<SCHEMA>\"
  }"
```

Check the response for `"state": "SUCCEEDED"`. If `"state": "FAILED"`, read `status.error.message` and see the Troubleshooting section below.

> ✋ **STOP** — Confirm which group or user should receive access before running the GRANT. This is a permission change visible to others.

Grant access:

```bash
databricks api post /api/2.0/sql/statements \
  --json "{\"warehouse_id\": \"<WAREHOUSE_ID>\", \"statement\": \"GRANT SELECT ON VIEW catalog.schema.orders_mv TO \`group_name\`\", \"wait_timeout\": \"30s\", \"catalog\": \"<CATALOG>\", \"schema\": \"<SCHEMA>\"}"
```

---

## Troubleshooting

When the SQL Statements API returns `"state": "FAILED"`, read `status.error.message`:

| Error message contains | Likely cause | Fix |
|---|---|---|
| `METRIC_VIEW_INVALID_VIEW_DEFINITION` | Invalid YAML field or value | Check the field name against the valid keys (`name`, `expr`, `display_name`, `comment`, `synonyms`, `format`). Common mistakes: using `description` instead of `comment`, unsupported `decimal_places`. |
| `warehouse not running` / `RESOURCE_DOES_NOT_EXIST` | Warehouse is stopped or wrong ID | Start the warehouse in the Databricks UI or verify the ID with `databricks api get /api/2.0/sql/warehouses`. |
| `PERMISSION_DENIED` | The CLI profile lacks privileges | Check the profile's permissions on the catalog/schema with `databricks api get /api/2.0/unity-catalog/permissions/...`. |
| `TABLE_OR_VIEW_NOT_FOUND` | A source or join table doesn't exist in Unity Catalog | Verify each table reference with `SHOW TABLES IN <catalog>.<schema>`. |
| `on` parse error / unexpected key | `on:` not quoted | Always write `'on':` (single-quoted) — it is a YAML 1.1 reserved word. |
| `wait_timeout` value error | Timeout out of range | `wait_timeout` must be between `5s` and `50s`. |

If the error message is truncated, run the same statement with `"wait_timeout": "5s"` to get the full synchronous error response.

---

## Critical Rules

1. **Naming**: Name the metric view `[topic_name]_mv` (snake_case, lowercase)
2. **CREATE vs ALTER**: Check for existence first — `CREATE OR REPLACE` for new, `ALTER VIEW` for existing
3. **Version**: Always use `version: 1.1` (requires Databricks Runtime 17.2+)
4. **Skip derived CTEs**: Views with `derived_table.sql` have no physical table — skip and warn the user
5. **Confirm before executing**: Show the full generated SQL to the user before running
6. **Boolean fields**: Map `type: yesno` as BOOLEAN dimensions — not filters. `data_type` is not a valid field — omit it
7. **Composed measures**: Use `MEASURE()` syntax; define atomic measures before composed ones
8. **YAML quoting**: `on` is a YAML 1.1 reserved word — always write `'on':` (single-quoted)
9. **No SELECT \***: All fields must be explicitly defined
10. **MAP columns**: Skip joins to tables containing `MAP` type columns — not supported
11. **Nested join refs**: Only direct star join columns (1 level) can be used in `expr`. Flatten snowflake schema joins through a denormalized direct join
12. **Warehouse ID required**: Always confirm before execution — cannot be inferred
13. **Exclusions win**: `-view.field` always overrides any wildcard inclusion
14. **Format type values are lowercase**: `number`, `currency`, `date`, `date_time`, `percentage`, `byte`
15. **Date format required**: `type: date` and `type: date_time` both require `date_format`
16. **Currency format**: Use `currency_code: USD` not `iso_code: USD`
17. **`decimal_places` unsupported**: Omit it entirely — causes a parse error
18. **CLI execution**: Use `databricks api post /api/2.0/sql/statements`; `wait_timeout` must be `5s`–`50s`
19. **Omni CLI flag**: Use `--filename` (not `--file-name`)
20. **Field description key**: Use `comment:` not `description:` — `description` is not a recognized field and causes a parse error

---

## Reference

- [Databricks Metric Views overview](https://docs.databricks.com/aws/en/metric-views/)
- [Create a metric view with SQL](https://docs.databricks.com/aws/en/metric-views/create/sql)
- [Metric view syntax reference](https://docs.databricks.com/aws/en/metric-views/data-modeling/syntax)
- [Semantic metadata](https://docs.databricks.com/aws/en/metric-views/data-modeling/semantic-metadata)
- [Joins](https://docs.databricks.com/aws/en/metric-views/data-modeling/joins)
- [Composability](https://docs.databricks.com/aws/en/metric-views/data-modeling/composability)
