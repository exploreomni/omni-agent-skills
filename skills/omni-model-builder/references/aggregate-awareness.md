# Aggregate Awareness (`materialized_query`)

Aggregate awareness lets Omni answer a query from a pre-aggregated table instead of the fact table. You declare a view for the aggregate table and describe, as a topic query, what that table holds. When a query can be served from the table, Omni rewrites the SQL to read it; when it cannot, the query runs unchanged against the fact table. Results are the same either way; only the cost differs.

Docs: [materialized_query](https://docs.omni.co/modeling/views/parameters/materialized-query) · [Aggregate awareness guide](https://docs.omni.co/analyze-explore/performance/aggregate-awareness)

## Declaring an aggregate table

The aggregate table is an ordinary view with a `materialized_query` block. The block is a topic query: which fields, on which base view and topic, and optionally which filter values the table was built for. Each field maps to the column that holds it.

```yaml
# order_items_daily.view — a table built as
#   SELECT DATE_TRUNC('DAY', created_at) AS created_day, user_id, status,
#          COUNT(*) AS order_count, SUM(sale_price) AS total_sale_price
#   FROM order_items GROUP BY 1, 2, 3
schema: ANALYTICS
table_name: ORDER_ITEMS_DAILY

dimensions:
  created_day:      { sql: '"CREATED_DAY"' }
  user_id:          { sql: '"USER_ID"' }
  status:           { sql: '"STATUS"' }
  order_count:      { sql: '"ORDER_COUNT"' }
  total_sale_price: { sql: '"TOTAL_SALE_PRICE"' }

materialized_query:
  fields:
    order_items.created_at[date]: CREATED_DAY
    order_items.user_id: USER_ID
    order_items.status: STATUS
    order_items.count: ORDER_COUNT
    order_items.total_sale_price: TOTAL_SALE_PRICE
  base_view: order_items
  topic: sales
```

Rules that decide whether the declaration is usable:

- **Map form of `fields:`.** Each key is a field of the base view's topic; each value is the column name in the aggregate table. A list form (positional) also exists; prefer the map.
- **Time dimensions carry a timeframe** (`created_at[date]`, `created_at[month]`). The aggregate column must hold the expression Omni compiles that timeframe to, not a lookalike. For a timestamp column at day grain that is a day-truncated timestamp (`DATE_TRUNC('DAY', ...)`), not a `CAST(... AS DATE)`. Validation compares each mapped column's type family to the field's and reports a mismatch as a warning; a view with a warning is ignored for optimization.
- **`topic:` is the topic the table serves.** The same `materialized_query` can name any regular topic whose base view is `base_view`.
- **Join keys.** To serve a query that groups by a dimension from a joined view (say `users.country`), the aggregate must contain the fact-side join key (`order_items.user_id` above). Omni then reads the aggregate and joins `users` live.
- **One `materialized_query` per view.** Several aggregate tables means several views; two views may point at the same physical table with different declarations.
- **Testing without a warehouse table.** A view with a `sql:` block is accepted as the aggregate source, so you can prove a declaration on a branch before building the table. Replace `sql:` with `schema:`/`table_name:` once the table exists.

### Pinning a table to a filter value

`materialized_query.filters` declares that the table holds rows for one value of a field. Use it for filtered subsets (shipped items only) and for tables built under one value of a filter-only field.

```yaml
materialized_query:
  fields:
    order_items.created_at[date]: CREATED_DAY
    order_items.count: ORDER_COUNT
  base_view: order_items
  topic: sales
  filters:
    order_items.is_shipped:
      is: true
```

A query that applies the same filter value is served from the table; a query with a different value, or no filter, is not. The pinned field does not need to be stored as a column, and the query only needs to filter on it, not select it.

The date-basis pattern combines a filter-only field, a dimension that follows it, and one pinned table per value (filter-only fields are covered in [templated-filters.md](templated-filters.md)). A dashboard control on the field then routes each query to the matching table:

```yaml
# order_items.view
filters:
  date_basis:
    type: string
    suggestion_list:
      - value: created
      - value: shipped
    default_filter: { is: created }
    filter_single_select_only: true

dimensions:
  event_date:
    sql: |
      CASE {{ filters.order_items.date_basis.value }}
        WHEN 'created' THEN ${created_at}
        WHEN 'shipped' THEN ${shipped_at}
      END
```

```yaml
# order_items_daily_created.view (repeat for shipped with the shipped date and is: shipped)
materialized_query:
  fields:
    order_items.event_date[date]: EVENT_DAY
    order_items.count: ORDER_COUNT
  base_view: order_items
  topic: sales
  filters:
    order_items.date_basis: { is: created }
```

## What a table can serve

Beyond an exact repeat of its defining query, an aggregate table serves three kinds of query:

| Query, relative to the table | Served | Notes |
|---|---|---|
| Coarser timeframe | yes | Day table serves `[week]`, `[month]`, `[quarter]`, `[year]`; month table serves `[month]`, `[quarter]`, `[year]`. Week comes only from day. When several tables fit, the coarsest wins. |
| Filter on a column the table has | yes | Applied to the table's column. |
| Grouping by a dimension from a joined view the table lacks | yes, with conditions | Needs the join key in the table. Inner joins work as is; `always_left` (the default relationship join type) needs the model feature below. |
| A fact column the table lacks | no | The table cannot supply it. |
| Finer timeframe than the table | no | Hour against a day table. |
| Day-part timeframes (`day_of_week`, `day_of_month`, `day_of_year`) | no | Not served from a day table. |

Rollups depend on the aggregate type:

| Aggregate type | Rolls up to a coarser grain |
|---|---|
| `sum`, `count`, `min`, `max` | yes |
| `average`, `count_distinct`, `median`, `percentile` | no; the query runs against the fact table at any grain other than the table's own |
| Sketch measures (HyperLogLog and similar) | yes, by merging sketches; see the guide |
| `list` and the `_distinct_on` variants | not checked; assume no |

### The non-inner join feature

Swapping the fact table for an aggregate while keeping a `always_left` join live is behind a model feature. The shape that needs it: a fact-only aggregate that carries the join key, a relationship left at the default join type, and a query that groups by a column from the joined view.

```yaml
# relationships — the default join type
- join_from_view: order_items
  join_to_view: users
  on_sql: ${order_items.user_id} = ${users.id}
  relationship_type: many_to_one
  join_type: always_left
```

The aggregate is `order_items_daily` as declared at the top of this page: fact-only, with `order_items.user_id` mapped as the join key and no `users` columns stored.

A query on `sales` for `users.country`, `order_items.count`, and `order_items.total_sale_price` can be served by reading `order_items_daily` and joining `users` on `USER_ID`. Without the feature it is not, and the query scans `order_items`; with the feature it is, and the join stays a LEFT JOIN. The same query with `join_type: inner` on the relationship needs no feature, and so does a query whose aggregate already stores `users.country` as a column.

Enable it with a comment in the `model` file:

```yaml
# !enable_feature(allow_non_inner_join_mv_optimization)
```

To turn it off, write `# !disable_feature(allow_non_inner_join_mv_optimization)`. Removing the comment does not clear it: comments in the model file survive a write that omits them.

## Confirming a query uses the table

Plan the query without running it and read the SQL. A rewritten query is headed with a comment naming the view, followed by the original SQL commented out:

```bash
omni query run --body '{
  "query": {"modelId": "<modelId>", "table": "order_items",
            "fields": ["order_items.created_at[month]", "order_items.count"],
            "join_paths_from_topic_name": "sales"},
  "planOnly": true, "cache": "SkipCache", "branchId": "<branchId>"
}'
# summary.display_sql begins:
#   -- Query rewritten to use materialized view "order_items_daily".
```

No header means the fact table was used. Check the shape of the query against the table above before changing the declaration: a missing column, a non-additive measure, or a left join without the feature are the usual reasons.

## Composite topics

A query on a composite topic is planned as one query per member topic and the results are joined. Each of those per-topic queries is matched against the member topic's aggregate tables on its own, so a table declared on a member topic serves its leg with the same rules as above, pins included. A `materialized_query` whose `topic:` names the composite itself is used only for an exact repeat of its defining query. See [composite-topics.md](composite-topics.md).
