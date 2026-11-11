# Query Views

Virtual tables defined by a saved query. A query view must have a primary key or it cannot be joined without producing fanout errors. Before writing, confirm which field uniquely identifies each row — unless the primary key can be clearly inferred from the query itself and the involved views (e.g. a query that selects `user_id` from a `users` view where `user_id` is the known primary key).

Mark exactly one dimension `primary_key: true`. When no single field is unique but a combination is, make that dimension a hidden key that concatenates the fields, `sql: ${field_a} || '-' || ${field_b}`; cast non-string fields first on dialects that don't convert them, such as BigQuery (`CAST(${field_b} AS STRING)`).

An existing model may set `custom_compound_primary_key_sql` at the view level instead. Leave it as it is; if you edit it, list `${view.field}` references, because Snowflake rewrites bare names to quoted uppercase columns, which a query view's lowercase columns don't match.

This works with either a `query:` block (field-mapped virtual table) or a `sql:` block (raw SELECT). In `sql:` blocks, use `${view_name}` to reference a view's underlying table rather than a hard-coded `CATALOG.SCHEMA.TABLE` path — it's preferred and stays correct if the table moves. See `references/query-view-examples.md` for complete YAML for each variant.

> If the user is unsure which field is unique, ask before writing the view. A query view without a primary key will trigger a "Joins fan out the data without a primary key" error when joined. See: https://community.omni.co/t/why-am-i-getting-the-error-joins-fan-out-the-data-without-a-primary-key/37

To scope a query view to one topic, see [Topic-Scoped View Definitions](topic-scoped-definitions.md#topic-scoped-view-definitions).

`sql:` versus `query:` for a rollup. Field references (`${view.field}`) work inside a `sql:` block, but Omni expands them once, when the file is saved, into alias-qualified columns, so the `FROM` must be aliased to the view's reference name (`FROM ${order_items} AS "order_items"`). Validation does not catch a missing alias; a query does. The `query:` form (`fields:` mapping view fields and measures to column names, plus `base_view` and `topic`) compiles through the model on every run, so later changes to those fields flow through. A `sql:` query view gets no automatic `count` measure; declare one if it is needed. Examples in `references/query-view-examples.md`.

Filters on a `query:` view. The inner query applies only its own `filters:` unless outer filters are bound to it. `bind_all_filters: true` under `query:` forwards outer filters on fields the inner topic can join ([bind_all_filters](https://docs.omni.co/modeling/query-views/parameters/bind-all-filters.md)); `bind:` on one inner filter forwards a named outer field ([bind](https://docs.omni.co/modeling/query-views/parameters/bind.md)). In a topic built only on query views, `bind_all_filters` forwards nothing, because every outer filter is on a query view field, which the inner topic can't join. Give the query view a filter-only field ([templated-filters.md](templated-filters.md)) and bind the inner filter to it; users filter on that field:

```yaml
query:
  fields:
    order_items.created_at[month]: created_month
    order_items.total_sale_price: sales
  base_view: order_items
  topic: order_items
  filters:
    order_items.created_at:
      bind: sales_by_month.reporting_window
dimensions:
  created_month:
    primary_key: true
  sales: {}
filters:
  reporting_window:
    type: timestamp
```

Don't base a `query:` view on a composite topic. Its `fields:` names can't be queried (`No such column with name "<name>"`), and validation reports each one as not found. Build the query view on a member topic instead.
