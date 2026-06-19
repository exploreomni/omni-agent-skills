# Query View Examples

> **Note for contributors:** This file is a YAML example gallery for human reference. It is not loaded at agent runtime. Procedural guidance and directives live in `SKILL.md` under "Query Views."

## Option 1 — Single Primary Key (query: block)

```yaml
schema: PUBLIC
query:
  fields:
    order_items.user_id: user_id
    order_items.count: order_count
    order_items.total_revenue: lifetime_value
  base_view: order_items
  topic: order_items

dimensions:
  user_id:
    primary_key: true
  order_count: {}
  lifetime_value:
    format: currency_2
```

## Option 2 — Compound Primary Key (query: block)

```yaml
schema: PUBLIC
query:
  fields:
    order_items.order_id: order_id
    order_items.product_id: product_id
    order_items.sale_price: sale_price
  base_view: order_items
  topic: order_items

custom_compound_primary_key_sql: [order_id, product_id]

dimensions:
  order_id: {}
  product_id: {}
  sale_price:
    format: currency_2
```

## Raw SQL Variant

The `sql:` block can be used in place of `query:`. The same primary key options apply.

Use `${view_name}` to reference a view's underlying table rather than a manual `CATALOG.SCHEMA.TABLE` reference — this is the preferred form as it stays correct if the underlying table is renamed or moved.

```yaml
schema: PUBLIC
sql: |
  SELECT user_id, COUNT(*) AS order_count, SUM(sale_price) AS lifetime_value
  FROM ${order_items}
  GROUP BY 1

dimensions:
  user_id:
    primary_key: true
  order_count: {}
  lifetime_value:
    format: currency_2
```

## Mapping / lookup view (CLI stand-in for an Omni Input Table)

To rebuild a **hardcoded key→label lookup** — e.g. a Looker `calculation_type: group_by` dynamic dimension that remaps `region_name` → a rep name, or any mapping that lives only in a dashboard (not in the database) — model it as **data joined on the key**, not a `CASE`. The maintainable ideal is an **Omni Input Table** (a writable table created/edited in the Omni UI — there is **no CLI command** for input tables under `connections`/`models`/`documents`). The **CLI-buildable equivalent** is a hardcoded `VALUES`/`UNION ALL` **query view** joined on the key:

```yaml
# region_rep_map.query.view  — Reference this view as region_rep_map
sql: |
  SELECT 'East' AS "region_name", 'Mike Parker'        AS "employee_name"
  UNION ALL SELECT 'West',          'Alexandra Peterson'
  UNION ALL SELECT 'Great Lakes',   'Jennifer Trevino'
  -- ...one row per source value; repeat the label across rows for many-to-one (Looker's comma filter)

dimensions:
  region_name: {}
  employee_name: {}

custom_compound_primary_key_sql: [ '"region_name"' ]   # single-col PK is fine
```

Then join it on the key (topic-scoped relationship):

```yaml
relationships:
  - join_from_view: <territory/base view>
    join_to_view: region_rep_map
    join_type: always_left
    relationship_type: many_to_one
    on_sql: ${<territory/base view>.region_name} = ${region_rep_map.region_name}
```

`employee_name` is now a real **dimension** — group, filter, and query by it like any field. Notes:
- **Quote the SELECT aliases** (`AS "region_name"`) on Snowflake/BigQuery/Databricks or they uppercase and the join key won't match.
- `always_left` → unmatched keys render as `∅`/null. Add an `'Other'` catch-all (a final `UNION ALL SELECT <unmatched>, 'Other'` is impractical for open domains — instead `COALESCE(${map.label}, 'Other')` in a derived dim, or accept nulls) to mirror Looker's `group_by` fallback.
- Verified end-to-end: validates clean, grouped query runs COMPLETE, mapped labels flow into results.
- Prefer a true **UI Input Table** when the mapping changes over time (reps reassigned) — it's editable in-app; the query view requires a YAML edit to change.
