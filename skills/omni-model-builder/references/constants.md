# Constants: one SQL definition shared across files

Use model constants when the same SQL has to live in more than one file. The usual case
is a rule that a modeled dimension and a raw-SQL query view both need, such as a bot
filter, a host exclusion or a status mapping. A `sql:` query view can't reuse the
dimension safely: `${view.field}` inside a `sql:` block is expanded once, when the file
is saved ([query-views.md](query-views.md)), so a later change to the dimension doesn't
reach it. Constants are substituted when the query runs.

Define them in the `model` file and reference them with `@{name}` ([docs](https://docs.omni.co/modeling/models/constants)):

```yaml
# model file
constants:
  junk_traffic_filter:
    value: |
      (geo.country = 'Hong Kong' AND device.operating_system = 'Windows')
      OR REGEXP_CONTAINS(user_agent, r'(?i)HeadlessChrome|python-requests')
```

```yaml
# a view
dimensions:
  is_junk_traffic:
    sql: |
      @{junk_traffic_filter}
```

```yaml
# a raw-SQL query view: works here too, including inside Mustache filter blocks
sql: |
  SELECT ...
  FROM ${events}
  WHERE {{# my_view.exclude_junk.filter }} NOT (@{junk_traffic_filter}) {{/ my_view.exclude_junk.filter }}{{^ my_view.exclude_junk.filter }} TRUE {{/ my_view.exclude_junk.filter }}
```

## Behaviour

Tested on BigQuery, on a branch of a git-connected shared model:

| Behaviour | Result |
|---|---|
| Multi-line value (`value: \|`) | Works |
| `@{name}` in a dimension's `sql` | Works |
| `@{name}` in a raw `sql:` query view, including inside `{{# … }}` filter blocks | Works |
| When it's substituted | **At query time.** Changing the constant changes every query that uses it, with no re-save of the views that reference it. |
| `@{other}` inside a constant's `value` | **Not expanded.** The literal `@{other}` reaches the SQL, and validation reports `unparseable_sql` on the views that use it. |

## Rules of thumb

- **Constants don't nest.** If several constants share a piece of SQL, inline that piece
  into each one. When the shared piece is large or generated, build the constants with a
  script. Mark the block as generated and keep the script in the repo, not hand-edited YAML.
- **Use raw columns in a constant that a raw-SQL query view uses.** For example
  `geo.country`, `event_params`, `device.operating_system`, not `${view.field}`. Both a
  table view's dimensions and a `sql:` view reading the same table can then use it unchanged.
- **Quote or block-scalar it in YAML.** `@` can't start a plain YAML scalar, so write
  `sql: |` on its own line followed by `@{name}`, or `sql: "@{name}"`.
- **Test that changes propagate.** On a branch, temporarily set the constant to something
  that changes the result (for example a filter that removes every row), query a view that
  uses it, then restore the constant and compare.
