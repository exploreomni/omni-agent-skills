# Aggregate Awareness (`materialized_query`)

Aggregate awareness lets Omni answer a query from a pre-aggregated table instead of the fact table. You declare a view for the aggregate table and describe, as a query on the base view, what that table holds. When a query can be served from the table, Omni rewrites the SQL to read it; when it cannot, the query runs unchanged against the fact table. Results are the same either way; only the cost differs. Read [What not to declare](#what-not-to-declare) and [Known issues](#known-issues) before building a table: the patterns there return wrong results.

Docs: [materialized_query](https://docs.omni.co/modeling/views/parameters/materialized-query) · [Aggregate awareness guide](https://docs.omni.co/analyze-explore/performance/aggregate-awareness)

## Contents

- [Declaring an aggregate table](#declaring-an-aggregate-table)
  - [Pinning a table to a filter value](#pinning-a-table-to-a-filter-value)
  - [When to declare `topic:`](#when-to-declare-topic)
- [What not to declare](#what-not-to-declare)
- [What a table can serve](#what-a-table-can-serve)
  - [When several tables fit](#when-several-tables-fit)
  - [Joined views](#joined-views)
- [Confirming a query uses the table](#confirming-a-query-uses-the-table)
- [Known issues](#known-issues)
- [Composite topics](#composite-topics)

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
- **`topic:` only for a table built from a topic's query.** Otherwise leave it out and describe the table against the base view. See [When to declare `topic:`](#when-to-declare-topic).
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

A query that applies the same filter value is served from the table; a query with a different value, or no filter, is not. The pinned field does not need to be stored as a column, and the query only has to filter on it. Pin a field of the base view, or of any view it joins, including through a left join.

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

### When to declare `topic:`

Without `topic:`, the declaration describes the base view, and the table serves every topic built on it. Each topic's always conditions and access filters are applied when the table is read, so the columns they test must be stored in the table or reachable through a stored join key.

`topic:` names the topic whose query built the table. Declare it in two cases:

- **The table maps joined-view columns, built through a join that only the topic defines or overrides.** Without `topic:`, the declaration uses the model's relationships. If only the topic joins the view, validation warns ("No join path from base view") and the table is ignored. If the topic overrides the join, for example to `join_type: inner`, a table built through the override doesn't match the model's join, and its joined-view fields are not served.
- **The table holds the topic's always conditions but not the columns they test.** For example, a table of orders that aren't cancelled, with no `status` column: the topic's `status` condition can't be applied on read, so without `topic:` that topic's queries read the fact table.

When the table stores the tested columns and was built through the model's joins, leave `topic:` out, so the table serves every topic on the base view.

A table built from a composite topic's query also declares `topic:`, with rules of its own: see [Composite topics](#composite-topics).

With `topic:` declared:

- **The topic's always conditions that don't use a user attribute are assumed to be in the table.** `always_where_sql`, `always_where_filters`, `always_having_sql` and `always_having_filters` are not applied on read, and Omni does not check that the table has them. Build the table from the topic's query with exactly those conditions, and rebuild it when they change; a table built without them returns rows they should exclude.
- **A topic without those conditions reads the fact table.** The table serves the declared topic and other topics with the same always conditions.
- **Default filters are not part of the topic's query.** `default_filters` are starting values a viewer can change, so don't build them into the table; declare a table that holds one filter value with a `filters:` pin (above).
- **Nothing per user is assumed.** The table holds every user's rows.
  - The topic's access filters are applied when the table is read, as they are without `topic:`. The filtered field has to be reachable from the table: stored, computed from stored columns, or on a view joined through a stored key under the join rules below. Otherwise those queries read the fact table.
  - A user attribute anywhere in the declared query, in one of the topic's always conditions or in a mapped field's SQL, turns the table off for every query, even when the tested field is stored or reachable. Validation warns that the view will be ignored for optimization and names the attribute. For such a topic, leave `topic:` out; its user-attribute conditions are then applied on read like any other condition.

## What not to declare

Omni accepts each of these, at most with a warning, and then returns wrong results or stops using the table.

- **A window-function field.** Don't map a dimension whose SQL uses a window function (`ROW_NUMBER()`, `RANK()`, `LAG()`, a running total), and don't build a table to serve one. The table stores the value computed over every row. A query that filters out some rows, by status for example, reads that stored value without recomputing it over the rows left, so a purchase sequence or a rank is wrong, with no error. Leave the field out of `materialized_query`; queries that use it read the fact table.
- **A `*_distinct_on` measure.** Don't map `sum_distinct_on`, `average_distinct_on`, `median_distinct_on` or `percentile_distinct_on` measures. Validation warns, and Omni stops using the table for every query, including those that never ask for the measure. Queries with these measures read the fact table, so don't build a table for them.
- **`limit` or `offset` in `materialized_query`.** Validation warns, and with `limit` Omni still serves other queries from the table as if it held every row: a total, or the bottom 10, read from a top-100 table is wrong. Build the table over every row, and let the query sort and limit.
- **A table that holds part of the history without a pin.** A table that keeps a window of dates, such as the last 30 days, must declare the window with a `filters:` pin. Without it, a query over all dates that the table's fields cover reads it and returns only the window, with no error. With the pin, queries over a longer range read the fact table, and queries inside the window read the table:

  ```yaml
  materialized_query:
    fields:
      order_items.created_at[hour]: CREATED_HOUR
      order_items.count: ORDER_COUNT
    base_view: order_items
    filters:
      order_items.created_at:
        time_for_duration: [30 days ago, 30 days]
  ```

- **A base view that doesn't hold every row.** Every query that no table can serve reads the base view. If the base view holds only recent rows, or none (a placeholder that exists only to send queries to the tables), those queries return partial or empty results with no error. Make the full-history table the base view, and declare the smaller tables as aggregate tables of it.
- **A filter-only field's value in the base view's `sql:`.** When the base view's own `sql:` reads `{{ filters.<view>.<field>.value }}`, queries that set that filter stop using every aggregate table. Apply the value in a topic condition or in a dimension (the date-basis pattern above). `{{ <view>.<field>.in_query }}` checks in the base view's `sql:` don't have this effect.
- **A table whose columns no longer mean what the fields mean.** Omni trusts the mapping and does not check how the table was built. Rebuild or remap the table when a mapped field's meaning changes: the connection's query timezone (build day buckets in that timezone, or map date fields with `convert_tz: false`), a custom calendar added to the date, or the join type of a stored join (see [Joined views](#joined-views)).

## What a table can serve

Beyond an exact repeat of its defining query, an aggregate table serves the queries marked yes:

| Query, relative to the table | Served | Notes |
|---|---|---|
| Coarser timeframe | yes | Day table serves `[week]`, `[month]`, `[quarter]`, `[year]`; month table serves `[month]`, `[quarter]`, `[year]`. Week comes only from day. When several tables fit, see "When several tables fit" below. |
| Filter on a column the table has | yes | Applied to the table's column. |
| A dimension computed from columns the table has | yes | `UPPER(${status})`, a concatenation, or a `CASE` over mapped fields is computed from the table's columns; it does not need its own column. |
| Grouping by a dimension from a joined view the table lacks | yes | Needs the fact-side join key in the table. See "Joined views" below. |
| A fact column the table lacks | no | The table cannot supply it. |
| Finer timeframe than the table | no | Hour against a day table. |
| Day parts (`day_of_week_num`, `day_of_week_name`, `day_of_month`, `day_of_year`, `day_of_quarter`) | yes, from a day table | Computed from the table's day column. |
| Month parts (`month_num`, `month_name`, `quarter_of_year`) | yes, from a day or month table | |
| `week_of_year`, `hour_of_day` | not from a day table | |

Rollups depend on the aggregate type:

| Aggregate type | Rolls up to a coarser grain |
|---|---|
| `sum`, `count`, `min`, `max` | yes |
| `average`, `count_distinct`, `median`, `percentile` | no; the query runs against the fact table at any grain other than the table's own |
| Sketch measures (HyperLogLog and similar) | yes, by merging sketches; see the guide |
| `list` | not checked; assume no |
| The `_distinct_on` variants | no; never map them (see [What not to declare](#what-not-to-declare)) |

### When several tables fit

When more than one aggregate table can serve a query, Omni prefers the one with the fewest grouping columns, counting a date field once whatever its timeframe, even over a coarser date grain: a `(day, status)` table is chosen over a `(month, status, user_id)` table. Among tables with the same number of grouping columns, Omni prefers the coarser date grain, so a `(month, status)` table is chosen over a `(day, status)` table for `[quarter]`. Remaining ties go to the table defined first. Row counts are not considered, so a table with fewer columns is chosen even when it holds more rows. If the cost difference matters, keep one table per combination of columns, or pin tables to different filter values so only one fits each query.

### Joined views

What the table maps decides how it treats joins. There are two kinds:

- **Base-view fields only** (the example above). Joins are added at query time on the fact-side keys the table stores, so one table serves every joined view reachable through them.
- **Joined-view fields too** (a stored join result). The table was built through a join and maps columns of the joined view. It is used only when every field in the query is mapped, and no other join is added to it.

Prefer the first kind: it cuts the fact rows each join reads and keeps every joined view available. The second serves one fixed set of fields.

An aggregate that carries a fact-side join key can stand in for the fact table while the joined view is read live: a query for `users.country`, `order_items.count`, and `order_items.total_sale_price` reads `order_items_daily` and joins `users` on `USER_ID`. A filter on a joined view's field is handled the same way, selected or not, and so is a dimension declared on `order_items` that uses a `users` field, such as `${status} || ', ' || ${users.country}`.

This works through inner and left joins, including chains of left joins and joins on more than one column, with the same rows as the fact table. Inner and left joins are the join types aggregate awareness supports. On ClickHouse, add `sql_preamble: SET join_use_nulls = 1;` to the model file: without it, a query served from an aggregate table through a left join returns empty strings or zeros for the joined fields of rows with no match, and `IS NULL` on those fields is false.

A stored join result, such as a table that stores `COUNTRY` and maps `users.country: COUNTRY`, serves the joined columns it maps without a join. A query that also asks for another joined view, or for a `users` field the table does not map, is served by another table that fits, or reads the fact table. Build the table through the same join the model uses, with the same join type and `on_sql`, or declare the topic whose join it was built through (see [When to declare `topic:`](#when-to-declare-topic)). Omni does not check how the table was built: a table built through an inner join and declared for a left join leaves out the rows that have no match.

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

No header means the fact table was used. A result served from Omni's cache shows the original SQL without the header even when a fresh run would read the table, so always check with `"cache": "SkipCache"` as above.

Before changing the declaration, check the query against the tables above. The usual reasons are a missing column, a non-additive measure, a mapped `*_distinct_on` measure (the whole table is then unused), and a stored join result asked for a field or join it does not hold.

## Known issues

These return wrong rows from an aggregate table. Write the model to avoid them.

- **`>` or `<=` against a midnight timestamp in model SQL.** In a topic's `always_where_sql`, a relationship's `where_sql`, or a yes/no dimension, a comparison such as `${order_items.created_at} > TIMESTAMP '2025-10-01 00:00:00'` is compared with the day or month the query selects when the query is rewritten to use a day or month table. With the month selected, `>` leaves out all of October and `<=` includes all of it. With the year selected, or no date, `>` against January 1 leaves out the whole year. Write date boundaries with `>=` and `<`, which are rewritten correctly:

  ```yaml
  # "from October 1"
  always_where_sql: ${order_items.created_at} >= TIMESTAMP '2025-10-01 00:00:00'
  # "before October 1"
  always_where_sql: ${order_items.created_at} < TIMESTAMP '2025-10-01 00:00:00'
  ```

  Before declaring a table on a base view, search the topics, relationships and dimensions that use it for `>` and `<=` on date fields, and rewrite them after confirming with the user which boundary was meant. A comparison against a non-midnight timestamp, or written with a date string or `DATE` literal, reads the fact table with the right rows.
- **Per-user timezones.** On a connection that lets users choose their own timezone, and for a query that passes a timezone, a table whose dates are in the connection's timezone gives every viewer the connection's days, so day, month and date-filtered results differ from the fact table for a viewer in another timezone. Don't declare tables that map date fields on a model whose connection allows user-specific timezones, and don't pass a query timezone other than the connection's to a topic with such tables.

## Composite topics

A query on a composite topic is planned as one query per member topic, and the results are joined. Aggregate tables serve it in two ways.

**A table per member (the default).** Each member's query is matched against that member topic's aggregate tables on its own, with the same rules as above, pins included. Declare the table on the member topic's base view, as above. It then serves both the member topic and any composite that includes it, and the join of the members' results still runs at query time.

**A table built from the composite's query.** When the table holds the composite's own result, each member aggregated under its own always conditions and joined on the shared dimensions, declare the composite as the table's `topic:`. Map its fields by the names a composite query uses: `@_shared_dimensions_.<dimension>` for a shared dimension (with a timeframe on a date) and `@<member topic>.<view>.<field>` for each member's measures. `base_view:` is still required; name the members' base view.

```yaml
materialized_query:
  fields:
    "@_shared_dimensions_.reporting_date[date]": REPORTING_DATE
    "@_shared_dimensions_.status": STATUS
    "@sales_all.order_items.total_sale_price": ALL_TOTAL
    "@sales_open.order_items.total_sale_price": OPEN_TOTAL
  base_view: order_items
  topic: open_vs_all
```

- **What it serves.** An exact repeat of the composite query, and rollups and filters on the shared dimensions it stores: coarser timeframes, day parts, fewer shared dimensions. It serves queries on that composite only; a query on a member topic alone reads the fact table.
- **Every member must be in the query.** A composite query that asks for one member's measures reads the fact table.
- **Member conditions.** For a rollup or a filter, each member's part is read from the table with that member's always conditions applied, so store the shared dimensions those conditions test. A member whose condition tests a column the table lacks reads the fact table for that query, while the other members still read the table. An exact repeat reads the table as it is, so build the table with every member's conditions.
- **Use the map form of `fields:`.** A positional list serves only an exact repeat, and validation warns about it.

See [composite-topics.md](composite-topics.md).
