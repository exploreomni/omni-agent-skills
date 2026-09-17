# Filter-Only Fields and Dynamic Fields (Templated Filters)

A filter-only field is a parameter on a view: it appears in the field picker and as a dashboard control, but it has no column. Its value is read inside other fields' SQL through Mustache, so one control can switch which column a dimension uses, which measure a KPI shows, or what threshold a filtered measure applies. Omni resolves the template at query time and constant-folds the result, so the executed SQL reads as if the chosen branch had been written by hand.

Docs: [Templated filters](https://docs.omni.co/modeling/templated-filters) · [Parameters](https://docs.omni.co/modeling/templated-filters/parameters) · Guide: [Improving date flexibility with templated filters](https://docs.omni.co/guides/modeling/date-flexibility-templated-filters)

## Declaring one

Filter-only fields live under a top-level `filters:` block in the view, beside `dimensions:` and `measures:`.

```yaml
filters:
  date_basis:
    type: string
    suggestion_list:
      - value: created
      - value: shipped
    default_filter: { is: created }
    filter_single_select_only: true
```

| Parameter | Meaning |
|---|---|
| `type` | `string`, `number`, `timestamp`, `boolean`, or `column` |
| `suggestion_list` | The allowed values, each `value:` with an optional `label:` |
| `suggest_from_field` | Populate suggestions from another field's values instead |
| `default_filter` | The value used when the query sends none, in filter syntax (`is: created`) |
| `filter_single_select_only` | Force a single value. Set it whenever the field drives a `CASE`; a multi-value pick has no single value to render |
| `label`, `description`, `group_label`, `hidden`, `display_order` | As on a dimension |

A filter-only field can also be declared inside a topic's `views:` block, scoped to that topic, and the dimension that reads it may reference topic-scoped aliases (a second role of a date view, for instance). The token path is unchanged: `filters.<view>.<field>` names the view the block sits under, not the topic.

## Reading it in SQL

| Token | Renders |
|---|---|
| `{{ filters.<view>.<field>.value }}` | The chosen value as a literal: a string arrives quoted, a number bare. Do not add quotes around it. |
| `{{ filters.<view>.<field>.range_start }}` / `.range_end` | The bounds of a timestamp filter |
| `{{# <view>.<field>.filter }} <expr> {{/ <view>.<field>.filter }}` | A whole condition: the filter applied to `<expr>` |
| `{{^ <view>.<field>.filter }} <sql> {{/ <view>.<field>.filter }}` | Runs only when the filter is empty; the "no value" default for the section form |

Use value injection for a `CASE` on the value. Use the section form when the filter contributes a whole condition, such as a range.

## Worked shapes

### Switch which date a dimension uses

```yaml
dimensions:
  event_date:
    sql: |
      CASE {{ filters.order_items.date_basis.value }}
        WHEN 'created' THEN ${created_at}
        WHEN 'shipped' THEN ${shipped_at}
      END
```

`event_date` is a timestamp, so it gets the full timeframe family (`event_date[date]`, `[month]`, `[year]`) and other fields can reference `${event_date[date]}`. Pair it with one pinned aggregate table per basis to keep the switch fast; see [aggregate-awareness.md](aggregate-awareness.md).

### Switch which measure a KPI shows

```yaml
filters:
  metric:
    type: string
    suggestion_list:
      - value: Revenue
      - value: Orders
    default_filter: { is: Revenue }
    filter_single_select_only: true

measures:
  selected_metric:
    sql: |
      CASE {{ filters.order_items.metric.value }}
        WHEN 'Revenue' THEN ${total_sale_price}
        WHEN 'Orders' THEN ${count}
      END
```

No `aggregate_type`: the measure is a `CASE` between measures, so each branch keeps its own aggregation and symmetric-aggregate handling. `format` is static, one format for every branch.

### A numeric threshold

```yaml
filters:
  ship_window_days:
    type: number
    default_filter: { is: 3 }

dimensions:
  shipped_within_window:
    sql: ${time_to_ship} <= {{ filters.order_items.ship_window_days.value }}

measures:
  orders_shipped_within_window:
    aggregate_type: count
    filters:
      shipped_within_window:
        is: true
```

A number renders bare (`<= 3`), so the token sits anywhere a numeric literal can; keep it in SQL rather than in a YAML filter value.

### A condition with a default when the control is empty

```yaml
measures:
  matching_orders:
    sql: |
      COUNT(CASE WHEN
        {{# order_items.status_pick.filter }} ${status} {{/ order_items.status_pick.filter }}
        {{^ order_items.status_pick.filter }} 1 = 1 {{/ order_items.status_pick.filter }}
      THEN ${id} END)
```

With the control empty the inverted section renders `1 = 1` and Omni folds the count to a plain `COUNT("ID")`; with a value it renders the equality.

## Using it from a query or dashboard

The field is filtered like any other, keyed `<view>.<field>`. Query API:

```json
"filters": {
  "order_items.date_basis": {"type": "string", "kind": "EQUALS", "values": ["shipped"]},
  "order_items.ship_window_days": {"type": "number", "kind": "EQUALS", "values": [10]}
}
```

A dashboard control binds to it with `fieldName` set to the filter-only field; one control drives every tile that uses the field. When no value is sent, `default_filter` applies. A filter-only field cannot be selected as a column, and it cannot be listed in an aggregate table's `fields:` map; use `materialized_query.filters` to pin a table to one of its values instead.

## Validating a templated field

Run the query on the branch and read the **executed** SQL (`stage_summaries[0].execution_sql`), not `omni_sql`: the latter still shows the Mustache, the former shows what ran. Run once per value the control can take and confirm each branch appears, then once with no filter to confirm the default. Common misses:

- `'{{ filters.v.f.value }}'` with a string value: the value already arrives quoted, so this is a syntax error. Drop the quotes.
- A `CASE` on a field without `filter_single_select_only`: a multi-value selection has no single value to render.
- `filters.v.f.value` versus `v.f.filter`: `.value` is for injection, `.filter` is for the section form. They are not interchangeable.
