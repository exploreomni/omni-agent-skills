# Running Raw SQL (`userEditedSQL`)

> **Given SQL? Reproduce it through a topic first** (see *Known Issues & Safe Defaults* in [SKILL.md](../SKILL.md#known-issues--safe-defaults)). Express the SQL's intent through the semantic layer; reach for raw `userEditedSQL` only when no topic can express it (SQL-first migration, warehouse-specific SQL, one-off ad-hoc read) or the user asks to run it as-is. If a faithful reproduction would need a field/topic that doesn't exist but *should*, propose modeling it (`omni-model-builder`) rather than defaulting to raw SQL.
>
> **Reading `generate-query` output:** when the topic lacks a measure the metric needs, `generate-query` returns a **`${}`-templated `userEditedSQL`** (e.g. `SUM(${view.sale_price}) AS sale_price_sum FROM ${Topic}`) and lists its SQL-output aliases (like `sale_price_sum`) in `fields`. Those aliases are **not model fields** — don't strip the SQL and try to run them semantically (they won't resolve). And the `${Topic}` token resolves **only inside `generate-query`'s own execution** — the templated query is **not** directly runnable via `query run` or persistable as a dashboard tile (it errors with `No such view "Order Items"`). So don't reuse it as-is; treat it as a **signal that the topic is missing a measure**. Report it, and add the measure with `omni-model-builder` only when the user asks for a model change, so the metric becomes a clean semantic field.

`userEditedSQL` is a **non-topic query pathway** — the same family as a bare-view query (see "Fallback — non-topic query pathways" under [Build queries on a topic](../SKILL.md#build-queries-on-a-topic) in SKILL.md). It's an escape hatch for SQL the semantic layer can't express; prefer a topic or semantic fields when they fit.

```bash
omni query run --body '{
  "query": {
    "modelId": "<model-id>",
    "fields": [],
    "userEditedSQL": "select count(*) as cnt from ECOMM.ORDER_ITEMS"
  }
}'
```

- **`fields` must be present** (an array; may be empty `[]`); `table` is not needed. The SQL is authoritative — populated `fields`/`table` are ignored when `userEditedSQL` is set.
- Runs against the model's **connection** — write warehouse-dialect SQL with fully-qualified names, not field references.
- **`"rewriteSql": false`** runs your SQL verbatim (the default parses and re-emits it — re-quoting identifiers, aliasing projections into the `view.field` namespace). **`"dbtMode": true`** allows Jinja/dbt templating. (Both are camelCase; the `query` object is permissive, so a misspelled/snake_case key is silently dropped.)
- **Permission-gated:** the querier's role must permit manually-written SQL. Without it the job fails — `error_type: "FORBIDDEN"`, *"queries based on manually written SQL are restricted"* — returned as **HTTP 200 with the error in the job body**, not a 4xx.
- **Access behavior:** raw SQL bypasses **all** model controls — object-level **access grants**, row-level **access filters**, and **always_where** — and is invisible to Viewer/Restricted Querier roles in a dashboard. It's the most permissive pathway; use only for ad-hoc reads by privileged users, and **strip it from any reused/dashboard query** (see [Using Job Results in a Dashboard](job-result-to-presentation.md#using-job-results-in-a-dashboard)).
- **Row cap:** an unbounded raw query is capped at **50,000 rows** (the response returns 50,001 — the cap plus one truncation sentinel). The envelope `limit` is **not** applied to raw SQL; put `LIMIT` in the SQL itself to bound results.
