# Query Views

Virtual tables defined by a saved query. A query view must have a primary key or it cannot be joined without producing fanout errors. **Before writing, confirm which field uniquely identifies each row — unless the primary key can be clearly inferred from the query itself and the involved views** (e.g. a query that selects `user_id` from a `users` view where `user_id` is the known primary key).

There are two ways to define the primary key:

**Option 1 — Single unique field:** Mark exactly one dimension `primary_key: true` in the `dimensions:` block.

**Option 2 — Compound key:** When no single field is unique but a combination is, set `custom_compound_primary_key_sql: [field_a, field_b]` at the view level — no `primary_key: true` dimension needed.

Both options work with either a `query:` block (field-mapped virtual table) or a `sql:` block (raw SELECT). In `sql:` blocks, use `${view_name}` to reference a view's underlying table rather than a hard-coded `CATALOG.SCHEMA.TABLE` path — it's preferred and stays correct if the table moves. See `references/query-view-examples.md` for complete YAML for each variant.

> If the user is unsure which field is unique, ask before writing the view. A query view without a primary key will trigger a "Joins fan out the data without a primary key" error when joined. See: https://community.omni.co/t/why-am-i-getting-the-error-joins-fan-out-the-data-without-a-primary-key/37

Query views can also be defined inline within a topic's `views:` block, scoping the virtual table to that topic only. See `references/topic-scoped-views.md` for an example.

**`sql:` versus `query:` for a rollup.** Field references (`${view.field}`) work inside a `sql:` block, but Omni expands them once, when the file is saved, into alias-qualified columns, so the `FROM` must be aliased to the view's reference name (`FROM ${order_items} AS "order_items"`). Validation does not catch a missing alias; a query does. The `query:` form (`fields:` mapping view fields and measures to column names, plus `base_view` and `topic`) compiles through the model on every run, so later changes to those fields flow through. A `sql:` query view gets no automatic `count` measure; declare one if it is needed. Examples in `references/query-view-examples.md`.
