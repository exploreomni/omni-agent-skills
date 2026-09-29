# Determine SQL Dialect

Before writing any SQL expressions, confirm the dialect from the connection — don't guess from the connection name:

```bash
# 1. List models to find connectionId
omni models list

# 2. Look up the connection's dialect
omni connections list
# → find your connectionId and read the "dialect" field
# → e.g. "bigquery", "postgres", "snowflake", "databricks"
```

Use dialect-appropriate functions in your SQL (e.g. `SAFE_DIVIDE` for BigQuery, `NULLIF(a/b)` for Postgres/Snowflake).

> **Creating a *new* SHARED model (rare).** Most work is on an existing model — but if you do create one with `omni models create`, the body is `{ modelKind: "SHARED", connectionId }` (no `baseModelId`; it inherits the connection's schema views + assumed relationships — run `omni models create --schema` for the full field list). **Footgun: create takes `modelName`, update takes `name`.** Passing `name` on create is silently ignored and the model is named from the connection — then you'd have to `omni models update <id> --body '{"name":"…"}'` to fix it. Pass **`modelName`** on create and skip the rename.

> **Deleting a model (CLI ≥ 1.2.2).** `omni models delete <modelId>` trashes a SHARED or shared-extension model **together with the workbooks, dashboards, and child extension models built on it** — confirm that blast radius with the user before running it. Requires **Connection Admin**. It does not delete branches: use `omni models delete-branch` for those.
