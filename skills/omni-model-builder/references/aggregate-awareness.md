# Aggregate Awareness (`materialized_query`)

Aggregate awareness lets Omni answer a query from a pre-aggregated table instead of the fact table. You declare a view for the aggregate table and describe, as a query on the base view, what that table holds. When a query can be served from the table, Omni rewrites the SQL to read it; when it cannot, the query runs unchanged against the fact table. Results are the same either way; only the cost differs.

Docs: [materialized_query](https://docs.omni.co/modeling/views/parameters/materialized-query) · [Aggregate awareness guide](https://docs.omni.co/analyze-explore/performance/aggregate-awareness)

## Declaring an aggregate table

The aggregate table is an ordinary view with a `materialized_query` block. The block is a query on the base view: which fields, and optionally which filter values the table was built for. Each field maps to the column that holds it.

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
```

Rules that decide whether the declaration is usable:

- **Map form of `fields:`.** Each key is a field of the base view, or of a view it joins to when the table stores that column; each value is the column name in the aggregate table. A list form (positional) also exists; prefer the map.
- **Time dimensions carry a timeframe** (`created_at[date]`, `created_at[month]`). The aggregate column must hold the expression Omni compiles that timeframe to, not a lookalike. For a timestamp column at day grain that is a day-truncated timestamp (`DATE_TRUNC('DAY', ...)`), not a `CAST(... AS DATE)`. Validation compares each mapped column's type family to the field's and reports a mismatch as a warning; a view with a warning is ignored for optimization.
- **Leave `topic:` out.** The block accepts one, but a declaration describes the base view, not a topic. Without it, the table serves every topic built on that base view, composites included, and each topic's own access filters and `always_where` conditions are applied on top of the table. With it, the table is read as the result of that topic's query, those conditions included, so they are not applied again.
- **Join keys.** To serve a query that groups by a dimension from a joined view (say `users.country`), the aggregate must contain the fact-side join key (`order_items.user_id` above). Omni then reads the aggregate and joins `users` live. Map the key as the **fact-side** field. Mapping the joined view's key instead (`users.id`), or as well, marks the table as a stored join result, and only the joined fields it lists are served.
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
  filters:
    order_items.date_basis: { is: created }
```

## What a table can serve

Beyond an exact repeat of its defining query, an aggregate table serves three kinds of query:

| Query, relative to the table | Served | Notes |
|---|---|---|
| Coarser timeframe | yes | Day table serves `[week]`, `[month]`, `[quarter]`, `[year]`; month table serves `[month]`, `[quarter]`, `[year]`. Week comes only from day. When several tables fit, the coarsest wins. |
| Filter on a column the table has | yes | Applied to the table's column. |
| Grouping by a dimension from a joined view the table lacks | yes, across an inner join | Needs the fact-side join key in the table. See "Joined views" below. |
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

### Joined views

An aggregate that carries a fact-side join key can stand in for the fact table while the joined view is read live: a query for `users.country`, `order_items.count`, and `order_items.total_sale_price` reads `order_items_daily` and joins `users` on `USER_ID`. A filter on a joined view's field is handled the same way, selected or not.

This applies when the relationship is an **inner join**. A relationship left at the default `always_left` is not served this way, and the query reads the fact table. Two ways to get a joined dimension served:

- Where every fact row has a match, set `join_type: inner` on the relationship, or override it inside the topic that needs it.
- Store the joined column in the aggregate and map it (`users.country: COUNTRY`). The table then serves that column without a join, and only the joined fields it lists.

If a left-join relationship has to be served from an aggregate table, ask Omni support.

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

No header means the fact table was used. Check the shape of the query against the table above before changing the declaration: a missing column, a non-additive measure, or a join that is not an inner join are the usual reasons.

## Composite topics

A query on a composite topic is planned as one query per member topic and the results are joined. Each of those per-topic queries is matched against the member topic's aggregate tables on its own, so a table declared on a member topic serves that member's query with the same rules as above, pins included. Declare the table on the base view as above; there is nothing to declare on the composite. See [composite-topics.md](composite-topics.md).
