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

```yaml
schema: PUBLIC
sql: |
  SELECT user_id, COUNT(*) AS order_count, SUM(sale_price) AS lifetime_value
  FROM order_items GROUP BY 1

dimensions:
  user_id:
    primary_key: true
  order_count: {}
  lifetime_value:
    format: currency_2
```
