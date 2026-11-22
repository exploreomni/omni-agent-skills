# Query Views

Virtual tables defined by a saved query. A query view must have a primary key or it cannot be joined without producing fanout errors. Before writing, confirm which field uniquely identifies each row — unless the primary key can be clearly inferred from the query itself and the involved views (e.g. a query that selects `user_id` from a `users` view where `user_id` is the known primary key).

Mark exactly one dimension `primary_key: true`. When no single field is unique but a combination is, make that dimension a hidden key that concatenates the fields, `sql: ${field_a} || '-' || ${field_b}`; cast non-string fields first on dialects that don't convert them, such as BigQuery (`CAST(${field_b} AS STRING)`).

An existing model may set `custom_compound_primary_key_sql` at the view level instead. Leave it as it is; if you edit it, list `${view.field}` references, because Snowflake rewrites bare names to quoted uppercase columns, which a query view's lowercase columns don't match.

This works with either a `query:` block (field-mapped virtual table) or a `sql:` block (raw SELECT). In `sql:` blocks, use `${view_name}` to reference a view's underlying table rather than a hard-coded `CATALOG.SCHEMA.TABLE` path — it's preferred and stays correct if the table moves. See `references/query-view-examples.md` for complete YAML for each variant.

> If the user is unsure which field is unique, ask before writing the view. A query view without a primary key will trigger a "Joins fan out the data without a primary key" error when joined. See: https://community.omni.co/t/why-am-i-getting-the-error-joins-fan-out-the-data-without-a-primary-key/37

To scope a query view to one topic, see [Topic-Scoped View Definitions](topic-scoped-definitions.md#topic-scoped-view-definitions).

`sql:` versus `query:` for a rollup. Field references (`${view.field}`) work inside a `sql:` block, but Omni expands them once, when the file is saved, into alias-qualified columns, so the `FROM` must be aliased to the view's reference name (`FROM ${order_items} AS "order_items"`). Validation does not catch a missing alias; a query does. The `query:` form (`fields:` mapping view fields and measures to column names, plus `base_view` and an optional `topic`) compiles through the model on every run, so later changes to those fields flow through. A `sql:` query view gets no automatic `count` measure; declare one if it is needed. Examples in `references/query-view-examples.md`.

Filters on a `query:` view. The inner query applies only its own `filters:` unless outer filters are bound to it. `bind_all_filters: true` under `query:` forwards outer filters on fields the inner topic can join ([bind_all_filters](https://docs.omni.co/modeling/query-views/parameters/bind-all-filters.md)); `bind:` on one inner filter forwards a named outer field ([bind](https://docs.omni.co/modeling/query-views/parameters/bind.md)). In a topic built only on query views, `bind_all_filters` forwards nothing: it skips filters on the query view's own fields, and the inner topic can't join another query view's fields. Give the query view a filter-only field ([templated-filters.md](templated-filters.md)) and bind the inner filter to it; users filter on that field:

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

## `topic:` and where the view lives

- Shared model: `topic:` is optional. Without it, the inner query starts from `base_view` and joins other views through the model's relationships. With it, the query also takes that topic's joins and always-on conditions, such as its `always_where_sql`; set it when the query needs them. Restricted queriers can query a topic built on either form.
- Workbook model: set `topic:` to a shared topic or composite topic. A workbook `query:` view without `topic:`, and any workbook `sql:` view, stop restricted queriers from running any query on that workbook model, shared topics included ("WORKBOOK models with changes to Topics are restricted").

## Before writing a `sql:` view

A `sql:` view is SQL kept outside the model's fields and relationships. Write one only after ruling out the modeled form for its shape:

- A grid of every member of two lists: a `cross` join ([Cross joins](global-relationships.md#cross-joins)).
- A delimited list or array in a column: a dimension with `nested_on_field` on the base view.
- "Is this row in set X" tests, such as UNION arms applied in order of precedence: one shared `query:` view per test, one row per key, each joined `one_to_one` to the base view, and a CASE dimension that applies the precedence.
- An aggregate over an aggregate: a `query:` view.

## Dimensions

A file that includes `sql:` or `query:` also sets which columns are dimensions:
- With a `dimensions:` section, only the columns listed there are. Omni stores every other column as `ignored: true`, and `dimensions: {}` ignores them all.
- With no section, a new view gets one dimension per column, none of them a primary key.

Create a query view with every column it should expose listed, the primary key included.

To change one, read it with `--mode combined`, which lists every dimension and, on a `sql:` view, each column's `sql:` (`'"ID"'` on Snowflake). Edit that read, write the whole file back with `"mode": "combined"`, and query the changed fields.
- New column: add it to the SQL or `fields:` and add its dimension. A column the section doesn't list is ignored.
- `sql:` view: give every dimension you add a `sql:` in the form the read shows. A dimension sent without its `sql:` loses it, and the column no longer resolves.
- On a branch, a column the shared model ignores can't be exposed by a `combined` or `extension` write. Read the file with `--mode merged`, add the dimension, and write it with `"mode": "merged"`. A later `combined` save of that file on the branch hides it again; once the branch is merged, it stays.
