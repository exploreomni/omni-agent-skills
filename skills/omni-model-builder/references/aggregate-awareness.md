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
- **Leave `topic:` out.** Describe the table against the base view only.
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

Beyond an exact repeat of its defining query, an aggregate table serves the queries marked yes:

| Query, relative to the table | Served | Notes |
|---|---|---|
| Coarser timeframe | yes | Day table serves `[week]`, `[month]`, `[quarter]`, `[year]`; month table serves `[month]`, `[quarter]`, `[year]`. Week comes only from day. When several tables fit, the one with the coarser date grain wins (a month table over a day table for `[quarter]`). See "When several tables fit" below. |
| Filter on a column the table has | yes | Applied to the table's column. |
| A dimension computed from columns the table has | yes | `UPPER(${status})`, a concatenation, or a `CASE` over mapped fields is computed from the table's columns; it does not need its own column. Two exceptions are listed below. |
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

### Computed dimensions that are not served

Two shapes of computed dimension send the query to the fact table even though the table, or a join from it, supplies every input. Each has a workaround.

- **A base-view dimension that references a joined view's field.** `order_items.city_state` defined as `${users.city} || ', ' || ${users.state}` is not served from an aggregate declared on `order_items`, even when `users` joins in across an inner join. Declare the same dimension on the joined view (`users.city_state`); it is then served like any other joined-view dimension.
- **A flag whose sum the table stores.** When `is_complete` is `CASE WHEN ${status} = 'Complete' THEN 1 ELSE 0 END` and the table stores `SUM` of that expression, mapped to a `sum` measure with `sql: ${is_complete}`, a query that selects `is_complete` reads the fact table. The stored sum itself is still served. Write the measure with an equivalent expression that differs from the flag's definition, for example `sql: CASE WHEN ${status} = 'Complete' THEN 1 END` (no `ELSE`; `SUM` ignores nulls, so the total is the same). The table's SQL and mapping stay unchanged, and both the flag and the sum are served. Adding the flag as a stored `GROUP BY` column instead does not work: the flag is then served, but the sum by `status` is not.

### When several tables fit

When more than one aggregate table can serve a query, Omni prefers the table whose date grain is coarser. Among tables at the same date grain, size is not considered: a `(day, user_id)` table and a `(day, status)` table can both serve `[month]` by `count`, and either may be chosen, whatever their row counts. If the cost difference matters, keep one table per date grain, or pin same-grain tables to different filter values so that only one fits each query.

### Joined views

What the table maps decides how it treats joins. There are two kinds:

- **Base-view fields only** (the example above). Joins are added at query time on the fact-side keys the table stores, so one table serves every joined view reachable through them.
- **Joined-view fields too** (a stored join result). The table was built through a join and maps columns of the joined view. It is used only when every field in the query is mapped, and no other join is added to it.

Build an aggregate to cut the fact rows a join has to touch, not to remove the join. The first kind keeps every joined view available; the second serves one fixed set of fields.

An aggregate that carries a fact-side join key can stand in for the fact table while the joined view is read live: a query for `users.country`, `order_items.count`, and `order_items.total_sale_price` reads `order_items_daily` and joins `users` on `USER_ID`. A filter on a joined view's field is handled the same way, selected or not.

This applies when the relationship is an **inner join**. A relationship left at the default `always_left` is not served this way, and the query reads the fact table. Two ways to get a joined dimension served:

- Where every fact row has a match, set `join_type: inner` on the relationship, or override it inside the topic that needs it.
- Store the joined column in the aggregate and map it (`users.country: COUNTRY`). The table becomes a stored join result: it serves that column without a join, but a query that adds any other joined view, or a field of `users` the table does not map, reads the fact table. Build the table through the same join the model uses, with the same join type and `on_sql`.

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

No header means the fact table was used. A result served from Omni's cache shows the original SQL without the header even when a fresh run would read the table, so check with `"cache": "SkipCache"` as above, or by rerunning without the cache in the workbook.

Check the shape of the query against the tables above before changing the declaration. The usual reasons are a missing column, a non-additive measure, a join that is not an inner join, a stored join result asked for a field or join it does not hold, and the two computed dimensions under "Computed dimensions that are not served".

## Composite topics

Aggregate tables serve queries on composite topics too, at the member topic level. Nothing can currently be declared on the composite itself: there is no way to point a composite topic at a table that pre-aggregates the composite query as a whole.

- A query on a composite topic is planned as one query per member topic, and the results are joined.
- Each member's query is matched against that member topic's aggregate tables on its own, with the same rules as above, pins included.
- So declare the table on the member topic's base view, as above. It then serves both the member topic and any composite that includes it.
- The join of the members' results always runs at query time, even when every member's query is served from an aggregate table.

See [composite-topics.md](composite-topics.md).
