# Window Measures

Docs: [window](https://docs.omni.co/modeling/measures/parameters/window)

A measure with a `window:` block is a window function over other measures. Each aggregate call in its `sql` (`SUM`, `AVG`, `MIN`, `MAX`) runs as a window function over the query's aggregated rows, and so do `RANK()` and `LAG()`. Nothing is aggregated for the window measure itself: define the aggregate as its own measure first, then window over it.

When to use one instead of a table calculation: *Window measures* in [SKILL.md](../SKILL.md#window-measures).

## Contents

- [Shape](#shape)
- [Validation](#validation)
- [Querying](#querying)
- [History a filter removes](#history-a-filter-removes)

## Shape

```yaml
measures:
  count:
    aggregate_type: count

  total_revenue:
    sql: ${sale_price}
    aggregate_type: sum

  cumulative_revenue:              # running total along the selected date grain
    sql: SUM(${total_revenue})
    window:
      order_by:
        - field: order_items.created_at

  trailing_3_period_avg_revenue:   # the current row and the two before it
    sql: AVG(${total_revenue})
    window:
      order_by:
        - field: order_items.created_at
      offset_start: -2

  revenue_rank_in_country:         # rank within each country by another measure
    sql: RANK()
    window:
      partition_by: [users.country]
      order_by:
        - field: total_revenue
          desc: true

  previous_period_revenue:         # the previous row's value
    sql: LAG(${total_revenue}, 1)
    window:
      order_by:
        - field: order_items.created_at

  share_of_revenue:                # an empty window is OVER ()
    sql: ${total_revenue} / SUM(${total_revenue})
    window: {}

  cumulative_avg_sale_price:       # a cumulative average is a ratio of windowed sums
    sql: SUM(${total_revenue}) / SUM(${count})
    window:
      order_by:
        - field: order_items.created_at
```

| Key | Meaning |
|---|---|
| `partition_by` | List of dimensions. The window restarts for each value. |
| `order_by` | List of sort entries: `field` (a dimension or a measure), optional `desc: true`, optional `null_sort` (`nulls_first` or `nulls_last`). |
| `offset_start` | Frame start, an integer counted from the current row: negative before it, `0` the current row. Omitted: the partition's first row. |
| `offset_end` | Frame end, counted the same way. Omitted: the current row under an `order_by`, the partition's last row without one. |
| `offset_type` | `rows` or `range`. With no offset keys the frame is SQL's default, a range up to the current row, so rows with the same `order_by` value share a value. Once `offset_start` or `offset_end` is set, the default is `rows`; keep it for "the last N periods". A `range` offset over a date `order_by` validates but fails on Snowflake. |

A measure from a joined view (`${users.count}`) keeps its fanout protection.

## Validation

`omni models validate` names each of these mistakes: a dimension or column in the `sql`, a nested aggregate, `DISTINCT`, an offset key on `RANK()` or `LAG()`, and a `window` whose `sql` has no window function. One limit shapes the design: no other measure, window measure or not, can reference a window measure, so build a ratio from the input measures, as `cumulative_avg_sale_price` does.

## Querying

- Every `partition_by` and `order_by` dimension must be in the query: selected, pivoted, or filtered to one value with an equality filter. Otherwise the query fails and names the missing field.
- The `order_by` dimension can't be pivoted. A pivot splits the window per pivot column, whether or not `partition_by` names it.
- A selected row dimension that `partition_by` doesn't name does not split the window. Under the default frame, rows with the same `order_by` value then show the same value. Add the dimension to `partition_by` or pivot it.
- The window runs at the query's timeframe (`created_at[month]` gives a monthly running total) and in its own `order_by`, not the query's sort. It starts at the first row the query's filters keep and covers every kept row, including rows past the row limit. A table calculation covers only the returned rows, in their order.
- A filter on a window measure removes rows after the window is computed; the rows left keep their values. A sort on a window measure needs it selected.
- In a totals row, `SUM`, `MIN` and `MAX` calls show the input measure's total. `AVG`, `RANK` and `LAG` windows show nothing.
- A composite topic refuses a query that selects a window measure.
- In `omni models get-topic`, a window measure has `"type": "window"` and its `window` block.

To test one, select it with its `order_by` and `partition_by` dimensions and check that a running total's last row equals the plain measure over the same filters.

## History a filter removes

To keep history a tile's filters remove, select the window measure in a query view at a fixed grain and give the view its own topic (`base_view: monthly_revenue`). The view's query has no filters, so its window runs over every row; a tile's filters only remove rows from the view's result.

```yaml
# monthly_revenue.view
query:
  fields:
    order_items.created_at[month]: month_start
    order_items.total_revenue: revenue
    order_items.cumulative_revenue: cumulative_revenue
  base_view: order_items
  topic: order_items

dimensions:
  month_start:
    primary_key: true
  revenue: {}
  cumulative_revenue: {}
```

Query the view at its own grain, month here. At year, a `sum` of the running-total column overcounts; a `max` measure gives each year's closing value while the total never decreases.
