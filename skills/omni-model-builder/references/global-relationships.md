# Global Relationships

```yaml
- join_from_view: order_items
  join_to_view: users
  on_sql: ${order_items.user_id} = ${users.id}
  relationship_type: many_to_one
  join_type: always_left
```

| Type | When to Use |
|------|-------------|
| `many_to_one` | Orders → Users |
| `one_to_many` | Users → Orders |
| `one_to_one` | Users → User Settings |
| `many_to_many` | Tags ↔ Products (rare) |

Getting `relationship_type` right prevents fanout and symmetric aggregate errors.

## Join types

[`join_type`](https://docs.omni.co/modeling/relationships/parameters/join-type.md) sets which rows a join keeps, in the relationships file and in a topic's `relationships:` alike.

| `join_type` | Keeps | Use when |
|---|---|---|
| `always_left` (default) | Every row of the view the topic reaches first | Adding attributes to a fact or entity |
| `inner` | Matched rows only | Rows without a match should drop out |
| `full_outer` | Every row of both views | Rows missing from either side should show |
| `right_left` | Every `join_to_view` row | A topic starts from another view but must list every `join_to_view` row ([Directional joins](#directional-joins)) |
| `left_right` | Every `join_from_view` row | The same, when the complete list is the `join_from_view` |
| `cross` | Every pairing of rows | Listing every combination that should exist, to find the missing ones ([Cross joins](#cross-joins)) |

Omni adds a join only when the query uses a field from the joined view, so an `inner` join or a relationship's `where_sql` drops rows only from those queries.

### Directional joins

`always_left` keeps the rows of the view the topic reaches first, so the kept side changes with the topic's base view. `right_left` and `left_right` keep one named side in every topic. Use one when a topic starts from a fact but must list every row of a complete list, such as every product, including products with no sales, in a topic based on `order_items`:

```yaml
- join_from_view: order_items
  join_to_view: products
  on_sql: ${order_items.product_id} = ${products.id}
  relationship_type: many_to_one
  join_type: right_left
```

The `order_items` topic then joins `order_items RIGHT JOIN products`: every product appears, and an order line with no matching product drops out. A topic based on `products` gets `products LEFT JOIN order_items`, the same rows `always_left` gives. Write `left_right` when the relationship names the complete list as `join_from_view`. In the relationships file the join type applies to every topic that joins the two views. When the topic can start from the complete list, `always_left` from that base view gives the same rows.

### Cross joins

A `cross` join pairs every row of one view with every row of another. Use it to find what is missing: list every combination that should exist, then lay the fact against that grid, so combinations with no fact rows appear with null measures. In the example, each warehouse should be counted in every count run of its company. The `count_grid` topic lists every warehouse and run pair, and the `count_lines` topic is the fact, one row per count taken.

The grid:

- Omni drops `on_sql` from a `cross` relationship when it saves. Pair rows within a key, here the company, in the relationship's [`where_sql`](https://docs.omni.co/modeling/relationships/parameters/where-sql.md).
- `join_type: inner` with the key match in `on_sql` returns the same grid. A topic `always_where_sql` also pairs the rows, but it joins `count_runs` into every query in the topic, so a warehouse in a company with no runs drops out even of warehouse-only queries.
- Set `relationship_type: many_to_many`, on the `inner` form too. With `many_to_one`, a measure on `warehouses` counts each warehouse once per run.

```yaml
# count_grid.topic
base_view: warehouses

relationships:
  - join_from_view: warehouses
    join_to_view: count_runs
    join_type: cross
    relationship_type: many_to_many
    where_sql: ${warehouses.company_id} = ${count_runs.company_id}

joins:
  count_runs: {}
```

The fact against the grid: a composite topic over the two topics, with both keys as shared dimensions ([composite-topics.md](composite-topics.md)). Each member topic is aggregated on its own and the results are joined with a FULL OUTER JOIN on the keys, so a pair with no `count_lines` rows comes back with null measures. Set `always_join_all_topics: true`: by default a composite queries only the member topics whose fields are selected, so a query for `count_lines` measures alone would skip the grid and miss the uncounted pairs.

```yaml
# count_coverage.composite_topic
topics: [ count_grid, count_lines ]
always_join_all_topics: true

shared_dimensions:
  warehouse_id:
    mappings:
      count_grid:
        field: warehouses.warehouse_id
      count_lines:
        field: count_lines.warehouse_id
  run_id:
    mappings:
      count_grid:
        field: count_runs.run_id
      count_lines:
        field: count_lines.run_id
```
