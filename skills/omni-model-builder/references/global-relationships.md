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
| `always_left` (default) | Every row of the view the join starts from | Adding attributes to a fact or entity |
| `inner` | Matched rows only | Rows without a match should drop out |
| `full_outer` | Every row of both views | Rows missing from either side should show |
| `left_right` | Every `join_from_view` row, whichever view the topic starts from | Topics start from either view, and the same view's rows must all stay |
| `right_left` | Every `join_to_view` row, whichever view the topic starts from | As `left_right`, keeping the other view |
| `cross` | Every pairing of rows | Building a grid of two lists ([Cross joins](#cross-joins)) |

Omni adds a join only when the query uses a field from the joined view, so an `inner` join or a relationship's `where_sql` drops rows only from those queries.

### Cross joins

A `cross` join pairs every row of one view with every row of another. Use it for a grid of two lists, so a fact laid against the grid also shows the combinations it has no rows for: every warehouse against every count run in its company, including warehouses missing from a run.

- Omni drops `on_sql` from a `cross` relationship when it saves. Pair rows within a key in the relationship's [`where_sql`](https://docs.omni.co/modeling/relationships/parameters/where-sql.md), as below.
- Alternatives that return the same grid: `join_type: inner` with the key match in `on_sql`; or a topic `always_where_sql`, which joins `count_runs` into every query in the topic, so a warehouse in a company with no runs drops out even of warehouse-only queries.
- Set `relationship_type: many_to_many`, on the `inner` form too. With `many_to_one`, a measure on `warehouses` counts each warehouse once per run.
- Lay the fact against the grid with a composite topic that maps both keys as shared dimensions ([composite-topics.md](composite-topics.md)). Set `always_join_all_topics: true`: without it, a query that selects only the fact's measures leaves the grid out and returns only the combinations that have rows. Missing combinations come back with null measures.

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
